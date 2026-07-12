import sys
from pathlib import Path
from unittest.mock import Mock

import pytest
from google.api_core.exceptions import Forbidden, NotFound
from google.cloud import bigquery

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import main


def test_optimizer_preflight_reports_only_missing_tables(monkeypatch):
    client = Mock()

    def get_table(table_id):
        if table_id.endswith(".keyword_performance"):
            raise NotFound("missing")
        return Mock()

    client.get_table.side_effect = get_table
    monkeypatch.setattr(bigquery, "Client", Mock(return_value=client))

    with pytest.raises(RuntimeError, match="keyword_performance"):
        main._validate_optimizer_data()


def test_optimizer_preflight_propagates_permission_errors(monkeypatch):
    client = Mock()
    client.get_table.side_effect = Forbidden("permission denied")
    monkeypatch.setattr(bigquery, "Client", Mock(return_value=client))

    with pytest.raises(Forbidden, match="permission denied"):
        main._validate_optimizer_data()
