from __future__ import annotations

import dataclasses
import functools
import importlib
import inspect
import json
import os
import pkgutil
from pathlib import Path
from typing import Any, Iterable

from src.collectors.public_sources import build_new_collectors


NEW_SOURCE_NAMES = frozenset(
    {"softwarerecs", "webapps", "hackernews", "devto"}
)
_PATCHED_CLASSES: set[type[Any]] = set()


def _source_name(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("source") or "").strip().casefold()
    return str(
        getattr(value, "source", "")
        or getattr(value, "name", "")
        or ""
    ).strip().casefold()


def _items_sources(items: Iterable[Any]) -> set[str]:
    return {
        source
        for source in (_source_name(item) for item in items)
        if source
    }


def _find_value(
    value: Any,
    keys: tuple[str, ...],
    *,
    depth: int = 0,
) -> Any:
    if depth > 5:
        return None
    if isinstance(value, dict):
        for key in keys:
            candidate = value.get(key)
            if candidate not in (None, "", [], {}):
                return candidate
        for nested in value.values():
            candidate = _find_value(nested, keys, depth=depth + 1)
            if candidate not in (None, "", [], {}):
                return candidate
    elif isinstance(value, (list, tuple)):
        for nested in value:
            candidate = _find_value(nested, keys, depth=depth + 1)
            if candidate not in (None, "", [], {}):
                return candidate
    return None


def extract_call_context(
    method: Any,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> tuple[str, int]:
    values: dict[str, Any] = dict(kwargs)
    try:
        bound = inspect.signature(method).bind_partial(*args, **kwargs)
        values.update(bound.arguments)
    except (TypeError, ValueError):
        pass

    query_value = _find_value(
        values,
        ("query", "search_term", "q", "term", "keyword", "intitle"),
    )
    limit_value = _find_value(
        values,
        ("limit", "per_page", "page_size", "pagesize", "max_results"),
    )

    query = str(query_value or "").strip()
    try:
        limit = max(1, int(limit_value or 30))
    except (TypeError, ValueError):
        limit = 30
    return query, limit


def _merge_errors(
    current: Any,
    additional: dict[str, str],
) -> Any:
    if not additional:
        return current
    if current is None:
        return dict(additional)
    if isinstance(current, dict):
        merged = dict(current)
        merged.update(additional)
        return merged
    if isinstance(current, list):
        merged_list = list(current)
        merged_list.extend(
            {"source": source, "error": message}
            for source, message in additional.items()
        )
        return merged_list
    return current


def extend_collection_result(
    result: Any,
    new_items: list[dict[str, Any]],
    new_errors: dict[str, str],
) -> Any:
    if not new_items and not new_errors:
        return result

    if isinstance(result, list):
        return [*result, *new_items]

    if isinstance(result, tuple):
        values = list(result)
        if values and isinstance(values[0], list):
            values[0] = [*values[0], *new_items]
            if len(values) > 1:
                values[1] = _merge_errors(values[1], new_errors)
            elif new_errors:
                values.append(dict(new_errors))
            return tuple(values)

    if isinstance(result, dict):
        merged = dict(result)
        for key in ("items", "collected_items", "opportunities"):
            if isinstance(merged.get(key), list):
                merged[key] = [*merged[key], *new_items]
                error_key = (
                    "errors"
                    if "errors" in merged
                    else "source_errors"
                    if "source_errors" in merged
                    else "errors"
                )
                merged[error_key] = _merge_errors(
                    merged.get(error_key),
                    new_errors,
                )
                return merged

        if isinstance(merged.get("results"), list):
            merged["results"] = [*merged["results"], *new_items]
            merged["errors"] = _merge_errors(
                merged.get("errors"),
                new_errors,
            )
            return merged

        if isinstance(merged.get("results"), dict):
            source_results = dict(merged["results"])
            for item in new_items:
                source_results.setdefault(_source_name(item), []).append(item)
            merged["results"] = source_results
            merged["errors"] = _merge_errors(
                merged.get("errors"),
                new_errors,
            )
            return merged

        if all(
            isinstance(value, list)
            for key, value in merged.items()
            if key not in {"errors", "source_errors"}
        ):
            for item in new_items:
                merged.setdefault(_source_name(item), []).append(item)
            error_key = (
                "errors"
                if "errors" in merged
                else "source_errors"
                if "source_errors" in merged
                else "errors"
            )
            merged[error_key] = _merge_errors(
                merged.get(error_key),
                new_errors,
            )
            return merged

    if dataclasses.is_dataclass(result) and not isinstance(result, type):
        changes: dict[str, Any] = {}
        for key in ("items", "collected_items", "opportunities", "results"):
            current = getattr(result, key, None)
            if isinstance(current, list):
                changes[key] = [*current, *new_items]
                break
        for key in ("errors", "source_errors"):
            if hasattr(result, key):
                changes[key] = _merge_errors(
                    getattr(result, key),
                    new_errors,
                )
                break
        if changes:
            return dataclasses.replace(result, **changes)

    for key in ("items", "collected_items", "opportunities", "results"):
        current = getattr(result, key, None)
        if isinstance(current, list):
            try:
                setattr(result, key, [*current, *new_items])
                for error_key in ("errors", "source_errors"):
                    if hasattr(result, error_key):
                        setattr(
                            result,
                            error_key,
                            _merge_errors(
                                getattr(result, error_key),
                                new_errors,
                            ),
                        )
                        break
                return result
            except (AttributeError, TypeError):
                break

    raise TypeError(
        "O CollectorManager retornou um formato ainda não suportado pela "
        "extensão multifonte. Tipo: "
        f"{type(result).__module__}.{type(result).__qualname__}"
    )


def _audit(
    *,
    source: str,
    query: str,
    item_count: int,
    status: str,
    error: str = "",
) -> None:
    path_value = os.getenv("OPPORTUNITY_RADAR_SOURCE_AUDIT_PATH", "").strip()
    if not path_value:
        return
    path = Path(path_value)
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "source": source,
        "query": query,
        "item_count": item_count,
        "status": status,
        "error": error,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _registered_collectors(instance: Any) -> list[Any]:
    found: list[Any] = []
    for name in ("collectors", "_collectors", "sources", "_sources"):
        value = getattr(instance, name, None)
        if isinstance(value, dict):
            found.extend(value.values())
        elif isinstance(value, (list, tuple, set)):
            found.extend(value)
    return [item for item in found if callable(getattr(item, "collect", None))]


def _inject_collectors(instance: Any, collectors: list[Any]) -> bool:
    existing_names = {
        _source_name(collector)
        for collector in _registered_collectors(instance)
    }
    pending = [
        collector
        for collector in collectors
        if _source_name(collector) not in existing_names
    ]
    if not pending:
        return True

    for method_name in ("register_collector", "register", "add_collector"):
        method = getattr(instance, method_name, None)
        if callable(method):
            for collector in pending:
                try:
                    method(collector)
                except TypeError:
                    method(_source_name(collector), collector)
            return True

    for name in ("collectors", "_collectors", "sources", "_sources"):
        value = getattr(instance, name, None)
        if isinstance(value, list):
            value.extend(pending)
            return True
        if isinstance(value, tuple):
            setattr(instance, name, (*value, *pending))
            return True
        if isinstance(value, set):
            value.update(pending)
            return True
        if isinstance(value, dict):
            for collector in pending:
                value[_source_name(collector)] = collector
            return True

    return False


def _collect_missing_sources(
    *,
    query: str,
    limit: int,
    already_present: set[str],
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    items: list[dict[str, Any]] = []
    errors: dict[str, str] = {}
    for collector in build_new_collectors():
        source = _source_name(collector)
        if source in already_present:
            continue
        try:
            collected = collector.collect(limit=limit, query=query)
            items.extend(collected)
            _audit(
                source=source,
                query=query,
                item_count=len(collected),
                status="SUCCESS",
            )
        except Exception as error:  # manager must preserve partial-success semantics
            message = f"{type(error).__name__}: {error}"
            errors[source] = message
            _audit(
                source=source,
                query=query,
                item_count=0,
                status="FAILED",
                error=message,
            )
    return items, errors


def _result_items(result: Any) -> list[Any]:
    if isinstance(result, list):
        return result
    if isinstance(result, tuple) and result and isinstance(result[0], list):
        return result[0]
    if isinstance(result, dict):
        for key in ("items", "collected_items", "opportunities"):
            if isinstance(result.get(key), list):
                return result[key]
        if isinstance(result.get("results"), list):
            return result["results"]
        if isinstance(result.get("results"), dict):
            return [
                item
                for values in result["results"].values()
                if isinstance(values, list)
                for item in values
            ]
        return [
            item
            for key, values in result.items()
            if key not in {"errors", "source_errors"} and isinstance(values, list)
            for item in values
        ]
    for key in ("items", "collected_items", "opportunities", "results"):
        value = getattr(result, key, None)
        if isinstance(value, list):
            return value
    return []


def _uses_explicit_collectors(
    original_init: Any,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> bool:
    """
    Preserve dependency injection used by tests and custom callers.

    When a caller explicitly supplies a collector registry, the multisource
    extension must not mutate that registry or execute external APIs.
    """
    explicit_names = ("collectors", "sources")

    for name in explicit_names:
        if name in kwargs and kwargs[name] is not None:
            return True

    try:
        bound = inspect.signature(original_init).bind_partial(
            None,
            *args,
            **kwargs,
        )
    except (TypeError, ValueError):
        return False

    return any(
        name in bound.arguments and bound.arguments[name] is not None
        for name in explicit_names
    )


def patch_manager_class(manager_class: type[Any]) -> bool:
    if manager_class in _PATCHED_CLASSES:
        return False

    original_init = manager_class.__init__

    @functools.wraps(original_init)
    def patched_init(self: Any, *args: Any, **kwargs: Any) -> None:
        explicit_collectors = _uses_explicit_collectors(
            original_init,
            args,
            kwargs,
        )
        original_init(self, *args, **kwargs)

        if explicit_collectors:
            collectors: list[Any] = []
            injected = False
        else:
            collectors = build_new_collectors()
            injected = _inject_collectors(self, collectors)

        setattr(
            self,
            "_opportunity_radar_explicit_collectors",
            explicit_collectors,
        )
        setattr(self, "_opportunity_radar_collectors", collectors)
        setattr(self, "_opportunity_radar_registry_injected", injected)

    manager_class.__init__ = patched_init  # type: ignore[method-assign]

    method_name = next(
        (
            name
            for name in ("collect_all", "collect", "run")
            if callable(getattr(manager_class, name, None))
        ),
        None,
    )
    if method_name is None:
        raise RuntimeError(
            f"{manager_class.__module__}.{manager_class.__qualname__} "
            "não possui collect_all(), collect() ou run()."
        )

    original_method = getattr(manager_class, method_name)

    @functools.wraps(original_method)
    def patched_method(self: Any, *args: Any, **kwargs: Any) -> Any:
        if getattr(
            self,
            "_opportunity_radar_explicit_collectors",
            False,
        ):
            return original_method(self, *args, **kwargs)

        query, limit = extract_call_context(
            original_method,
            (self, *args),
            kwargs,
        )
        injected_collectors = getattr(
            self,
            "_opportunity_radar_collectors",
            [],
        )
        for collector in injected_collectors:
            setattr(collector, "_runtime_query", query)

        result = original_method(self, *args, **kwargs)
        current_items = _result_items(result)
        present_sources = _items_sources(current_items)

        # Audita coletores novos que o manager original executou.
        for source in sorted(NEW_SOURCE_NAMES & present_sources):
            count = sum(
                1 for item in current_items if _source_name(item) == source
            )
            _audit(
                source=source,
                query=query,
                item_count=count,
                status="SUCCESS",
            )

        missing_items, missing_errors = _collect_missing_sources(
            query=query,
            limit=limit,
            already_present=present_sources,
        )
        return extend_collection_result(
            result,
            missing_items,
            missing_errors,
        )

    setattr(manager_class, method_name, patched_method)
    _PATCHED_CLASSES.add(manager_class)
    return True


def _manager_classes() -> list[type[Any]]:
    import src.collectors as collectors_package

    classes: list[type[Any]] = []
    modules = [collectors_package]
    package_path = getattr(collectors_package, "__path__", None)
    if package_path:
        for module_info in pkgutil.iter_modules(
            package_path,
            prefix=f"{collectors_package.__name__}.",
        ):
            if module_info.name.endswith(
                ("public_sources", "multisource_patch")
            ):
                continue
            try:
                modules.append(importlib.import_module(module_info.name))
            except Exception:
                continue

    for module in modules:
        candidate = getattr(module, "CollectorManager", None)
        if inspect.isclass(candidate):
            classes.append(candidate)

    unique: list[type[Any]] = []
    for manager_class in classes:
        if manager_class not in unique:
            unique.append(manager_class)
    return unique


def install_multisource_collectors() -> tuple[str, ...]:
    patched: list[str] = []
    for manager_class in _manager_classes():
        if patch_manager_class(manager_class):
            patched.append(
                f"{manager_class.__module__}.{manager_class.__qualname__}"
            )
    if not patched and not _PATCHED_CLASSES:
        raise RuntimeError(
            "CollectorManager não localizado em src.collectors. "
            "A integração multifonte não foi aplicada."
        )
    return tuple(patched)


__all__ = [
    "NEW_SOURCE_NAMES",
    "extend_collection_result",
    "extract_call_context",
    "install_multisource_collectors",
    "_uses_explicit_collectors",
    "patch_manager_class",
]
