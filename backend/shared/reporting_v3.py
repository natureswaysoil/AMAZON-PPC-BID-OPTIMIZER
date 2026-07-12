"""Amazon Ads Reporting v3 duplicate-report recovery.

This module is the sync-specific adapter for HTTP 425 responses. It submits a
single report request, reuses Amazon's existing report ID when the request is a
duplicate, and tolerates transient status-poll failures until the timeout.
"""
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
    """Request once, recover HTTP 425 duplicates, then poll and download."""
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
        try:
            status = amazon_client._make_request("GET", status_endpoint)
        except requests.exceptions.RequestException as exc:
            logger.warning(
                "Transient error polling Amazon report %s: %s; retrying",
                report_id,
                exc,
            )
            time.sleep(10)
            continue
        except Exception as exc:
            logger.warning(
                "Error polling Amazon report %s: %s; retrying until timeout",
                report_id,
                exc,
            )
            time.sleep(10)
            continue

        current_status = status.get("status")

        logger.info(
            "Amazon report %s status: %s",
            report_id,
            current_status,
        )

        if current_status in {"COMPLETED", "SUCCESS"}:
            download_url = status.get("url")
            if not download_url:
                raise RuntimeError(
                    f"No download URL in successful report status: {status}"
                )

            parsed_url = urlparse(download_url)
            if not parsed_url.hostname or not parsed_url.hostname.endswith(
                ".amazonaws.com"
            ):
                raise RuntimeError(
                    f"Invalid download URL domain: {parsed_url.hostname}"
                )

            report_response = requests.get(download_url, timeout=60)
            report_response.raise_for_status()
            decompressed = gzip.decompress(report_response.content)
            rows = [
                json.loads(line)
                for line in decompressed.decode("utf-8").splitlines()
                if line.strip()
            ]
            logger.info(
                "Downloaded %s rows from report %s",
                len(rows),
                report_id,
            )
            return rows

        if current_status in {"FAILURE", "FAILED"}:
            reason = status.get("failureReason", "Unknown error")
            raise RuntimeError(f"Report generation failed: {reason}")

        if current_status not in {
            "IN_PROGRESS",
            "PENDING",
            "PROCESSING",
        }:
            logger.warning("Unknown report status: %s", current_status)

        time.sleep(10)

    raise TimeoutError(
        f"Report {report_id} not ready after {max_wait}s"
    )