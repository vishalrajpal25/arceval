"""Alert routing: dispatch alerts to configured sinks on threshold breaches."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from arceval.core.protocols import ScoreResult

logger = logging.getLogger(__name__)


class LogAlertSink:
    """Logs alerts to the Python logger. Default sink when nothing else is configured."""

    def send(self, alert: dict[str, Any]) -> None:
        logger.warning("ALERT: %s", json.dumps(alert, default=str))


class WebhookAlertSink:
    """Sends alerts to an HTTP webhook endpoint.

    Config:
        url: webhook URL
        headers: optional HTTP headers
    """

    def __init__(self, url: str, headers: dict[str, str] | None = None) -> None:
        self._url = url
        self._headers = headers or {}

    def send(self, alert: dict[str, Any]) -> None:
        try:
            import urllib.request

            data = json.dumps(alert, default=str).encode()
            req = urllib.request.Request(
                self._url,
                data=data,
                headers={**self._headers, "Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=10)
        except Exception as exc:
            logger.error("Failed to send webhook alert to %s: %s", self._url, exc)


class SlackAlertSink:
    """Sends alerts to a Slack channel via incoming webhook.

    Config:
        webhook_url: Slack incoming webhook URL
        channel: channel name (informational, webhook determines actual channel)
    """

    def __init__(self, webhook_url: str, channel: str = "") -> None:
        self._webhook_url = webhook_url
        self._channel = channel

    def send(self, alert: dict[str, Any]) -> None:
        scorer = alert.get("scorer_name", "unknown")
        tier = alert.get("tier", "?")
        score = alert.get("score", "N/A")
        threshold = alert.get("threshold", "N/A")

        text = (
            f":warning: *ArcEval Alert* [{tier.upper()}]\n"
            f"Scorer `{scorer}` breached threshold: "
            f"score={score}, threshold={threshold}"
        )

        payload = {"text": text}
        try:
            import urllib.request

            data = json.dumps(payload).encode()
            req = urllib.request.Request(
                self._webhook_url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=10)
        except Exception as exc:
            logger.error("Failed to send Slack alert: %s", exc)


class AlertRouter:
    """Routes alerts to the appropriate sinks based on tier and event type.

    Each alert rule maps event patterns (e.g. "t1.fail") to a sink.
    """

    def __init__(self) -> None:
        self._rules: list[tuple[list[str], Any]] = []  # (event_patterns, sink)

    def add_rule(self, on: list[str], sink: Any) -> None:
        """Add an alert routing rule.

        Args:
            on: list of event patterns like "t1.fail", "t2.threshold_breach"
            sink: AlertSink instance
        """
        self._rules.append((on, sink))

    def check_and_alert(self, results: list[ScoreResult]) -> list[dict[str, Any]]:
        """Check results against thresholds and fire alerts for breaches.

        Returns list of alerts that were fired.
        """
        fired: list[dict[str, Any]] = []

        for result in results:
            if result.passed:
                continue

            alert = {
                "scorer_name": result.scorer_name,
                "tier": result.tier.value,
                "score": result.score,
                "threshold": result.threshold,
                "trace_id": result.trace_id,
                "details": result.details,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            event = f"{result.tier.value}.fail"

            for patterns, sink in self._rules:
                if self._matches(event, patterns):
                    sink.send(alert)
                    fired.append(alert)
                    break  # only fire once per result per matching rule

        return fired

    @staticmethod
    def _matches(event: str, patterns: list[str]) -> bool:
        """Check if an event matches any of the patterns."""
        for pattern in patterns:
            if pattern == event:
                return True
            # Support partial match: "t1.fail" matches "t1.*" or just "t1"
            if event.startswith(pattern.rstrip(".*")):
                return True
        return False
