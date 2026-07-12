"""Amazon Ads reporting v3 request, duplicate recovery, polling, and download."""
import gzip
import json
import logging
import re
import time
from typing import Dict, List
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)

_REPORT_ID_PATTERN = re.compile(
    r"duplicate of\s*:\s*([0-9a-fA-F-]{36})",
    re.IGNORECASE,
)


def _duplicate_report_id(exc: Exception) -> str | None:
    """Extract Amazon's existing report ID from an HTTP 425 response."""
    response = getattr(exc, "response", None)
    if response is None or getattr(response, "status_code", None) != 425:
        return None

    detail = ""
    try:
        payload = response.json()
        detail = str(payload.get("detail", ""))
    except (TypeError, ValueError, AttributeError):
        detail = str(getattr(response, "text", "") or "")

    match = _REPORT_ID_PATTERN.search(detail)
    return match.group(1) if match else None


def request_and_download_report_v3(
    amazon_client,
    report_config: Dict,
    max_wait: int = 300,
) -> List[Dict]:
    """Request a report, reuse duplicate reports, poll, download, and parse rows."""
    endpoint = "/reporting/reports"
    logger.info("Requesting report: %s", report_config.get("name", "Unnamed Report"))

    try:
        response = amazon_client._make_request(
            "POST",
            endpoint,
            max_retries=1,
            json=report_config,
        )
        report_id = response.get("reportId")
    except requests.exceptions.HTTPError as exc:
        report_id = _duplicate_report_id(exc)
        if not report_id:
            raise
        logger.info("Reusing duplicate Amazon report: %s", report_id)

    if not report_id:
        raise RuntimeError("Amazon report request returned no reportId")

    status_endpoint = f"/reporting/reports/{report_id}"
    start_time = time.time()

    while time.time() - start_time < max_wait:
        status = amazon_client._make_request("GET", status_endpoint)
        current_status = status.get("status")

        if current_status == "SUCCESS":
            download_url = status.get("url")
            if not download_url:
                raise RuntimeError(
                    f"No download URL in successful report status: {status}"
                )

            parsed_url = urlparse(download_url)
            if not parsed_url.hostname or not parsed_url.hostname.endswith(".amazonaws.com"):
                raise RuntimeError(f"Invalid download URL domain: {parsed_url.hostname}")

            report_response = requests.get(download_url, timeout=60)
            report_response.raise_for_status()
            decompressed = gzip.decompress(report_response.content)
            return [
                json.loads(line)
                for line in decompressed.decode("utf-8").splitlines()
                if line.strip()
            ]

        if current_status == "FAILURE":
            reason = status.get("failureReason", "Unknown error")
            raise RuntimeError(f"Report generation failed: {reason}")

        if current_status not in {"IN_PROGRESS", "PENDING"}:
            logger.warning("Unknown report status: %s", current_status)

        time.sleep(10)

    raise TimeoutError(f"Report {report_id} not ready after {max_wait}s")
