from collections.abc import Callable
from typing import Any

ProgressCallback = Callable[[str, dict[str, Any]], None] | None

STAGE_CHECKING_ACCESS = "checking_access"
STAGE_DISCOVERING_PAGES = "discovering_pages"
STAGE_CRAWLING = "crawling"
STAGE_ANALYZING_READINESS = "analyzing_readiness"
STAGE_GENERATING = "generating"


def emit_stage(callback: ProgressCallback, step: str) -> None:
    if callback:
        callback("stage", {"step": step})


def emit_progress(callback: ProgressCallback, step: str, **data: Any) -> None:
    if callback:
        callback("progress", {"step": step, **data})
