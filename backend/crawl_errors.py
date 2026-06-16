from enum import Enum


class ScanErrorType(str, Enum):
    TIMEOUT = "timeout"
    ROBOTS_BLOCKED = "robots_blocked"
    NO_PAGES = "no_pages"


ERROR_MESSAGES: dict[ScanErrorType, str] = {
    ScanErrorType.TIMEOUT: "This site took too long to respond. Try again later.",
    ScanErrorType.ROBOTS_BLOCKED: "This site's robots.txt blocks automated crawlers.",
    ScanErrorType.NO_PAGES: "No pages could be retrieved from this site.",
}

HTTP_STATUS: dict[ScanErrorType, int] = {
    ScanErrorType.TIMEOUT: 504,
    ScanErrorType.ROBOTS_BLOCKED: 403,
    ScanErrorType.NO_PAGES: 422,
}


class ScanError(Exception):
    def __init__(self, error_type: ScanErrorType):
        self.error_type = error_type
        super().__init__(ERROR_MESSAGES[error_type])


def error_detail(exc: ScanError) -> dict[str, str]:
    return {
        "error_type": exc.error_type.value,
        "message": ERROR_MESSAGES[exc.error_type],
    }
