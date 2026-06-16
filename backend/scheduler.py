import asyncio
import logging
import os

from db import list_domains_due_for_rescan
from regenerate import recrawl_domain

logger = logging.getLogger(__name__)

DEFAULT_INTERVAL_HOURS = 24
DEFAULT_TICK_SECONDS = 900


def _scheduler_enabled() -> bool:
    return os.getenv("SCAN_SCHEDULER_ENABLED", "true").lower() not in ("0", "false", "no")


def _interval_hours() -> float:
    return float(os.getenv("SCAN_INTERVAL_HOURS", DEFAULT_INTERVAL_HOURS))


def _tick_seconds() -> int:
    return int(os.getenv("SCAN_SCHEDULER_TICK_SECONDS", DEFAULT_TICK_SECONDS))


async def _rescan_domain(url: str, display_domain: str) -> None:
    try:
        result = await recrawl_domain(display_domain, url, mark_unviewed=True)
        logger.info(
            "Scheduled rescan for %s: content_changed=%s regenerated=%s",
            display_domain,
            result.content_changed,
            result.regenerated,
        )
    except Exception:
        logger.exception("Scheduled rescan failed for %s", display_domain)


async def run_due_scans() -> None:
    due = list_domains_due_for_rescan(interval_hours=_interval_hours())
    if not due:
        return

    logger.info("Running scheduled rescans for %d domain(s)", len(due))
    for row in due:
        await _rescan_domain(row["url"], row["display_domain"])


async def scheduler_loop(stop_event: asyncio.Event) -> None:
    tick_seconds = _tick_seconds()
    logger.info(
        "Scan scheduler started (interval=%sh, tick=%ss)",
        _interval_hours(),
        tick_seconds,
    )

    while not stop_event.is_set():
        try:
            await run_due_scans()
        except Exception:
            logger.exception("Scheduled scan tick failed")

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=tick_seconds)
        except asyncio.TimeoutError:
            pass


def start_scheduler() -> tuple[asyncio.Task | None, asyncio.Event | None]:
    if not _scheduler_enabled():
        logger.info("Scan scheduler disabled")
        return None, None

    stop_event = asyncio.Event()
    task = asyncio.create_task(scheduler_loop(stop_event))
    return task, stop_event


async def stop_scheduler(
    task: asyncio.Task | None,
    stop_event: asyncio.Event | None,
) -> None:
    if task is None or stop_event is None:
        return

    stop_event.set()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    logger.info("Scan scheduler stopped")
