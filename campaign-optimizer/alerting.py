"""Slack alerting for safety-critical events (ACOS circuit breaker trips,
budget pacing alarms). Deliberately fails soft: a missing/broken webhook
must never block the circuit breaker itself from tripping and floor-bidding
- the bid protection matters more than the notification.
"""
import logging
import os

import requests

logger = logging.getLogger(__name__)


def send_slack_alert(message: str) -> bool:
    """Post message to the SLACK_WEBHOOK_URL incoming webhook. Returns True
    if sent, False otherwise (missing config or request failure) - callers
    should log the return value but never raise on it."""
    webhook_url = os.getenv("SLACK_WEBHOOK_URL", "").strip()
    if not webhook_url:
        logger.warning(f"SLACK_WEBHOOK_URL not configured, alert not sent: {message}")
        return False

    try:
        response = requests.post(webhook_url, json={"text": message}, timeout=10)
        response.raise_for_status()
        return True
    except Exception as exc:
        logger.error(f"Failed to send Slack alert: {exc} | message was: {message}")
        return False
