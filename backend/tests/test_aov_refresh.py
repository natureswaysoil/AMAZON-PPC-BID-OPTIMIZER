import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from jobs.ingestion.aov_refresh import (
    _build_keyword_performance_query,
    _build_placement_fallback_query,
)


def test_fallback_casts_string_keyword_ids_to_int64():
    query = _build_placement_fallback_query()

    assert "k.keyword_id = SAFE_CAST(p.keyword_id AS INT64)" in query
    assert "CAST(p.keyword_id AS STRING)" not in query


def test_queries_preserve_tenant_scope():
    primary = _build_keyword_performance_query()
    fallback = _build_placement_fallback_query()

    assert "GROUP BY tenant_id, campaign_id" in primary
    assert "USING (tenant_id, campaign_id)" in primary
    assert "COALESCE(k.tenant_id, '') = COALESCE(p.tenant_id, '')" in fallback
    assert "USING (tenant_id, campaign_id)" in fallback
