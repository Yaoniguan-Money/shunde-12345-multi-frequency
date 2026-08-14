from backend.app.infrastructure.db.models import Base


def test_required_phase_one_tables_are_declared() -> None:
    required = {
        "import_batches",
        "work_orders",
        "complaint_segments",
        "entity_mentions",
        "canonical_entities",
        "entity_aliases_runtime",
        "event_instances",
        "work_order_embeddings",
        "event_candidates",
        "event_match_edges",
        "event_clusters",
        "event_cluster_members",
        "analysis_jobs",
        "analysis_runs",
        "human_corrections",
        "event_handling_records",
        "audit_logs",
        "knowledge_snapshots",
    }
    assert required <= set(Base.metadata.tables)
