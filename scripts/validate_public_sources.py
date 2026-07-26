from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.collectors.public_sources import build_new_collectors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--query", default="")
    args = parser.parse_args()

    failures: list[str] = []

    print("=" * 78)
    print("VALIDAÇÃO DIRETA DAS NOVAS FONTES")
    print("=" * 78)

    for collector in build_new_collectors():
        source = str(
            getattr(
                collector,
                "source",
                collector.__class__.__name__,
            )
        )

        try:
            items = collector.collect(
                limit=args.limit,
                query=args.query,
            )
            print(f"✅ {source}: {len(items)} itens recebidos")

            for item in items[:2]:
                print(
                    f"   - {item.get('title', '')} | "
                    f"{item.get('url', '')}"
                )

            if not items:
                failures.append(
                    f"{source}: API respondeu sem itens"
                )
        except Exception as error:
            failure = (
                f"{source}: {type(error).__name__}: {error}"
            )
            failures.append(failure)
            print(f"❌ {failure}")

    if failures:
        print("\nFALHAS")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("\n✅ Quatro novas fontes responderam com dados reais.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
