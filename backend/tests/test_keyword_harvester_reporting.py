import sys
from pathlib import Path
from unittest.mock import Mock, patch

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from jobs.optimization.keyword_harvester import _get_search_term_report


def test_keyword_harvester_uses_shared_reporting_v3_helper():
    client = Mock()
    expected = [{"searchTerm": "liquid fertilizer"}]

    with patch(
        "shared.reporting_v3.request_and_download_report_v3",
        return_value=expected,
    ) as request_report:
        rows = _get_search_term_report(client)

    assert rows == expected
    request_report.assert_called_once()
    args, kwargs = request_report.call_args
    assert args[0] is client
    assert args[1]["configuration"]["reportTypeId"] == "spSearchTerm"
    assert kwargs["max_wait"] == 300
