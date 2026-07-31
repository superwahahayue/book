"""Deprecated: scheduled auto-continue removed in galgame director mode.

Kept as a no-op module so any leftover imports do not crash.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def start() -> None:
    logger.info("Scheduler disabled (director mode).")


def shutdown() -> None:
    pass


def sync_novel_job(novel_id: int, auto_continue: bool, interval_minutes: int) -> None:
    pass


def remove_novel_job(novel_id: int) -> None:
    pass
