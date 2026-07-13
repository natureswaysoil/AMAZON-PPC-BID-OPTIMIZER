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
_POLL_INTERVAL_SECONDS = 30
# If a report stays at PENDING/PROCESSING without any status change for this
# many seconds, Amazon has likely stalled on its side (common when reusing a
# 425 duplicate ID whose underlying job was already completed in a prior run).
# Fail fast so the scheduler retries once Amazon's dedup window expires.
_STUCK_STATUS_TIMEOUT_SECONDS = 900  # 15 minutes without a status change


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


def _sleep_until_next_poll(start_time: float, max_wait: int) -> None:
    """Sleep no longer than the remaining report wait budget."""
    remaining = max_wait - (time.time() - start_time)
    if remaining > 0:
        time.sleep(min(_POLL_INTERVAL_SECONDS, remaining))


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
        reused_id = False
    except requests.exceptions.HTTPError as exc:
        report_id = _duplicate_report_id(exc)
        if not report_id:
            raise
        reused_id = True
        logger.info("Reusing duplicate Amazon report: %s", report_id)

    if not report_id:
        raise RuntimeError("Amazon report request returned no reportId")

    status_endpoint = f"/reporting/reports/{report_id}"
    start_time = time.time()
    last_status = None
    last_status_change_time = time.time()

    while time.time() - start_time < max_wait:
        try:
            status = amazon_client._make_request("GET", status_endpoint)
        except requests.exceptions.RequestException as exc:
            logger.warning(
                "Transient error polling Amazon report %s: %s; retrying",
                report_id,
                exc,
            )
            _sleep_until_next_poll(start_time, max_wait)
            continue
        except Exception as exc:
            logger.warning(
                "Error polling Amazon report %s: %s; retrying until timeout",
                report_id,
                exc,
            )
            _sleep_until_next_poll(start_time, max_wait)
            continue

        current_status = status.get("status")
        if current_status != last_status:
            logger.info("Amazon report %s status: %s", report_id, current_status)
            last_status = current_status
            last_status_change_time = time.time()
        elif reused_id and current_status in {"PENDING", "PROCESSING"}:
            # A 425-reused report that hasn't changed status in a long time is
            # likely stalled on Amazon's side (the original job already ran and
            # Amazon re-queued it under the same ID but deprioritised it).
            # Fail fast so the scheduler can retry after the dedup window expires.
            stuck_for = time.time() - last_status_change_time
            if stuck_for >= _STUCK_STATUS_TIMEOUT_SECONDS:
                raise TimeoutError(
                    f"Reused report {report_id} stuck at {current_status} for "
                    f"{stuck_for:.0f}s — Amazon likely stalled on a re-queued "
                    "duplicate. Will retry on the next scheduled run."
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
            report_text = decompressed.decode("utf-8").strip()

            if not report_text:
                rows = []
            else:
                try:
                    parsed = json.loads(report_text)
                except json.JSONDecodeError:
                    rows = [
                        json.loads(line)
                        for line in report_text.splitlines()
                        if line.strip()
                    ]
                else:
                    if isinstance(parsed, list):
                        rows = parsed
                    elif isinstance(parsed, dict):
                        rows = [parsed]
                    else:
                        raise RuntimeError(
                            "Unexpected Amazon report data type: "
                            f"{type(parsed).__name__}"
                        )

            if not all(isinstance(row, dict) for row in rows):
                raise RuntimeError(
                    "Amazon report contained non-object rows"
                )
            logger.info(
                "Downloaded %s rows from report %s",
                len(rows),
                report_id,
            )
            return rows

        if current_status in {"FAILURE", "FAILED", "CANCELLED"}:
            reason = status.get("failureReason", "Unknown error")
            raise RuntimeError(f"Report generation failed: {reason}")

        if current_status not in {
            "IN_PROGRESS",
            "PENDING",
            "PROCESSING",
        }:
            logger.warning("Unknown report status: %s", current_status)

        _sleep_until_next_poll(start_time, max_wait)

    raise TimeoutError(
        f"Report {report_id} not ready after {max_wait}s; last status={last_status}"
    )
