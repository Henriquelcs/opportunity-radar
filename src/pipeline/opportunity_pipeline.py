from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Any
from src.collectors.manager import CollectorManager
from src.processors.opportunity_scorer import score_opportunities
from src.storage.database import DEFAULT_DATABASE_PATH
from src.storage.opportunity_repository import CollectionRunRepository
from src.storage.opportunity_repository import OpportunityRepository

def _collect_all_compatible(collector_manager, query: str, limit_per_source: int):
    import inspect
    method = collector_manager.collect_all
    parameters = inspect.signature(method).parameters
    kwargs = {}
    query_aliases = ('query', 'search_query', 'search_term', 'term', 'keyword', 'keywords')
    limit_aliases = ('limit_per_source', 'limit', 'per_source_limit', 'max_results', 'max_items')
    for name in query_aliases:
        if name in parameters:
            kwargs[name] = query
            break
    for name in limit_aliases:
        if name in parameters:
            kwargs[name] = limit_per_source
            break
    if 'sources' in parameters:
        kwargs['sources'] = ['github', 'stackoverflow']
    if 'source_options' in parameters:
        kwargs['source_options'] = {'github': {'query': query}, 'stackoverflow': {'query': query}}
    if 'fail_fast' in parameters:
        kwargs['fail_fast'] = False
    return method(**kwargs)

def utc_now_iso() -> str:
    """
    Retorna a data atual em UTC.
    """
    return datetime.now(timezone.utc).isoformat()

@dataclass(slots=True)
class PipelineResult:
    """
    Resultado completo da execução do pipeline.
    """
    collected_count: int
    pain_count: int
    opportunity_count: int
    persisted_count: int
    opportunities: list[dict[str, Any]]
    collection_errors: dict[str, str]
    execution_status: str
    run_id: int | None = None

class OpportunityPipeline:
    """
    Coordena coleta, análise, ranking e persistência.
    """

    def __init__(self, collector_manager: CollectorManager | None=None, repository: OpportunityRepository | None=None, run_repository: CollectionRunRepository | None=None, database_path: str | Path=DEFAULT_DATABASE_PATH) -> None:
        self.collector_manager = collector_manager or CollectorManager()
        self.repository = repository or OpportunityRepository(database_path=database_path)
        self.run_repository = run_repository or CollectionRunRepository(database_path=database_path)

    @staticmethod
    def _analyze_pain(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Executa o detector de sinais de dor.
        """
        from src.processors.pain_detector import filter_items_with_pain
        return filter_items_with_pain(items)

    def run(self, query: str, limit_per_source: int=20, minimum_score: float=0.0, persist: bool=True) -> PipelineResult:
        """
        Executa todas as etapas do Opportunity Radar.
        """
        started_at = utc_now_iso()
        collected_count = 0
        pain_count = 0
        opportunity_count = 0
        persisted_count = 0
        opportunities: list[dict[str, Any]] = []
        collection_errors: dict[str, str] = {}
        execution_status = 'SUCCESS'
        try:
            collection_result = _collect_all_compatible(self.collector_manager, query, limit_per_source)
            collected_items = collection_result.items
            collection_errors = collection_result.errors
            collected_count = len(collected_items)
            pain_items = self._analyze_pain(collected_items)
            pain_count = len(pain_items)
            ranked_items = score_opportunities(pain_items)
            opportunities = [item for item in ranked_items if item.get('opportunity_score', 0.0) >= minimum_score]
            opportunity_count = len(opportunities)
            if persist:
                persisted_count = self.repository.upsert_many(opportunities)
            if collection_errors:
                execution_status = 'PARTIAL_SUCCESS'
        except Exception:
            execution_status = 'FAILED'
            raise
        finally:
            finished_at = utc_now_iso()
            run_id = self.run_repository.create(query=query, limit_per_source=limit_per_source, collected_count=collected_count, pain_count=pain_count, opportunity_count=opportunity_count, persisted_count=persisted_count, collection_errors=collection_errors, started_at=started_at, finished_at=finished_at, execution_status=execution_status)
        return PipelineResult(collected_count=collected_count, pain_count=pain_count, opportunity_count=opportunity_count, persisted_count=persisted_count, opportunities=opportunities, collection_errors=collection_errors, execution_status=execution_status, run_id=run_id)
