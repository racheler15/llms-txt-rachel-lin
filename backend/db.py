import json
import os
import sqlite3
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from changes import detect_changes
from models import Page
from readiness import ReadinessCategory, ReadinessResult
from url_utils import normalize_url

DEFAULT_DB_PATH = Path(__file__).parent / "data" / "scans.db"


def _db_path() -> Path:
    return Path(os.getenv("SCAN_DB_PATH", DEFAULT_DB_PATH))


def _connect() -> sqlite3.Connection:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS domains (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL UNIQUE,
                display_domain TEXT NOT NULL UNIQUE,
                last_scanned_at TEXT NOT NULL,
                has_updates INTEGER NOT NULL DEFAULT 0,
                llms_txt TEXT,
                readiness_json TEXT,
                pages_crawled INTEGER NOT NULL DEFAULT 0,
                pages_included INTEGER NOT NULL DEFAULT 0,
                generation_hashes_json TEXT,
                has_unviewed_changes INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS pages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                domain_id INTEGER NOT NULL,
                url TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                title TEXT NOT NULL DEFAULT '',
                meta_description TEXT NOT NULL DEFAULT '',
                word_count INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (domain_id) REFERENCES domains(id) ON DELETE CASCADE,
                UNIQUE(domain_id, url)
            );
            """
        )
        _migrate_schema(conn)


def _migrate_schema(conn: sqlite3.Connection) -> None:
    columns = {row[1] for row in conn.execute("PRAGMA table_info(domains)")}
    if "generation_hashes_json" not in columns:
        conn.execute("ALTER TABLE domains ADD COLUMN generation_hashes_json TEXT")
    if "has_unviewed_changes" not in columns:
        conn.execute("ALTER TABLE domains ADD COLUMN has_unviewed_changes INTEGER NOT NULL DEFAULT 0")

    rows = conn.execute(
        """
        SELECT id FROM domains
        WHERE llms_txt IS NOT NULL
          AND (generation_hashes_json IS NULL OR generation_hashes_json = '')
        """
    ).fetchall()
    for row in rows:
        domain_id = row["id"]
        page_hashes = conn.execute(
            "SELECT url, content_hash FROM pages WHERE domain_id = ?",
            (domain_id,),
        ).fetchall()
        if page_hashes:
            hashes = {page["url"]: page["content_hash"] for page in page_hashes}
            conn.execute(
                "UPDATE domains SET generation_hashes_json = ? WHERE id = ?",
                (json.dumps(hashes), domain_id),
            )


def _readiness_to_json(readiness: ReadinessResult) -> str:
    return json.dumps(
        {
            "total": readiness.total,
            "max_total": readiness.max_total,
            "categories": [asdict(category) for category in readiness.categories],
            "recommendations": readiness.recommendations,
            "js_rendering_likely": readiness.js_rendering_likely,
        }
    )


def load_page_hashes(domain_id: int) -> dict[str, str]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT url, content_hash FROM pages WHERE domain_id = ?",
            (domain_id,),
        ).fetchall()
    return {row["url"]: row["content_hash"] for row in rows}


def load_generation_hashes(domain_id: int) -> dict[str, str]:
    with _connect() as conn:
        row = conn.execute(
            "SELECT generation_hashes_json FROM domains WHERE id = ?",
            (domain_id,),
        ).fetchone()
    if not row or not row["generation_hashes_json"]:
        return {}

    parsed = json.loads(row["generation_hashes_json"])
    return {str(url): str(content_hash) for url, content_hash in parsed.items()}


def get_domain_id(display_name: str) -> int | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT id FROM domains WHERE display_domain = ?",
            (display_name,),
        ).fetchone()
    return row["id"] if row else None


def get_domain(display_name: str) -> sqlite3.Row | None:
    with _connect() as conn:
        return conn.execute(
            "SELECT * FROM domains WHERE display_domain = ?",
            (display_name,),
        ).fetchone()


def _readiness_from_json(readiness_json: str) -> ReadinessResult:
    parsed = json.loads(readiness_json)
    return ReadinessResult(
        total=parsed["total"],
        categories=[
            ReadinessCategory(
                id=category["id"],
                score=category["score"],
                max_score=category["max_score"],
                label=category["label"],
            )
            for category in parsed["categories"]
        ],
        recommendations=parsed["recommendations"],
        max_total=parsed.get("max_total", 100),
        js_rendering_likely=parsed.get("js_rendering_likely", False),
    )


def _has_content_changes(domain_id: int, row: sqlite3.Row) -> bool:
    if not row["llms_txt"]:
        return False
    baseline = load_generation_hashes(domain_id)
    if not baseline:
        return False
    current = load_page_hashes(domain_id)
    return detect_changes(baseline, current)


def _scan_dict_from_row(row: sqlite3.Row, domain_id: int) -> dict:
    return {
        "domain": row["display_domain"],
        "url": row["url"],
        "llms_txt": row["llms_txt"],
        "pages_crawled": row["pages_crawled"],
        "pages_included": row["pages_included"],
        "readiness": _readiness_from_json(row["readiness_json"]),
        "has_unviewed_changes": bool(row["has_unviewed_changes"]),
        "has_content_changes": _has_content_changes(domain_id, row),
        "last_scanned_at": row["last_scanned_at"],
    }


def get_stored_scan(display_name: str) -> dict | None:
    row = get_domain(display_name)
    if not row or not row["readiness_json"]:
        return None
    return _scan_dict_from_row(row, row["id"])


def list_recent_scans(*, limit: int = 50) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT id, display_domain, url, last_scanned_at, has_unviewed_changes,
                   pages_crawled, pages_included, llms_txt, readiness_json,
                   generation_hashes_json
            FROM domains
            WHERE readiness_json IS NOT NULL
            ORDER BY last_scanned_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    scans: list[dict] = []
    for row in rows:
        readiness = _readiness_from_json(row["readiness_json"])
        scans.append(
            {
                "domain": row["display_domain"],
                "url": row["url"],
                "pages_crawled": row["pages_crawled"],
                "pages_included": row["pages_included"],
                "readiness_total": readiness.total,
                "has_unviewed_changes": bool(row["has_unviewed_changes"]),
                "has_content_changes": _has_content_changes(row["id"], row),
                "last_scanned_at": row["last_scanned_at"],
                "generated": row["llms_txt"] is not None,
            }
        )

    return scans


def list_domains_due_for_rescan(*, interval_hours: float = 24) -> list[dict[str, str]]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=interval_hours)

    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT display_domain, url, last_scanned_at
            FROM domains
            WHERE readiness_json IS NOT NULL
            ORDER BY last_scanned_at ASC
            """
        ).fetchall()

    due: list[dict[str, str]] = []
    for row in rows:
        scanned_at = datetime.fromisoformat(row["last_scanned_at"].replace("Z", "+00:00"))
        if scanned_at.tzinfo is None:
            scanned_at = scanned_at.replace(tzinfo=timezone.utc)
        if scanned_at <= cutoff:
            due.append(
                {
                    "display_domain": row["display_domain"],
                    "url": row["url"],
                }
            )

    return due


def page_hash_map(pages: list[Page]) -> dict[str, str]:
    return {normalize_url(page.url): page.content_hash for page in pages}


def save_scan(
    *,
    url: str,
    display_name: str,
    pages: list[Page],
    readiness: ReadinessResult,
) -> int:
    now = datetime.now(timezone.utc).isoformat()
    readiness_json = _readiness_to_json(readiness)
    normalized_url = normalize_url(url)

    with _connect() as conn:
        existing = conn.execute(
            "SELECT id FROM domains WHERE display_domain = ?",
            (display_name,),
        ).fetchone()

        if existing:
            domain_id = existing["id"]
            conn.execute(
                """
                UPDATE domains
                SET url = ?, last_scanned_at = ?, readiness_json = ?, pages_crawled = ?
                WHERE id = ?
                """,
                (normalized_url, now, readiness_json, len(pages), domain_id),
            )
            conn.execute("DELETE FROM pages WHERE domain_id = ?", (domain_id,))
        else:
            cursor = conn.execute(
                """
                INSERT INTO domains (
                    url, display_domain, last_scanned_at, readiness_json, pages_crawled
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (normalized_url, display_name, now, readiness_json, len(pages)),
            )
            domain_id = cursor.lastrowid

        conn.executemany(
            """
            INSERT INTO pages (domain_id, url, content_hash, title, meta_description, word_count)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    domain_id,
                    normalize_url(page.url),
                    page.content_hash,
                    page.title,
                    page.meta_description,
                    page.word_count,
                )
                for page in pages
            ],
        )

    return domain_id


def set_unviewed_changes(display_name: str, *, unviewed: bool) -> None:
    with _connect() as conn:
        conn.execute(
            """
            UPDATE domains
            SET has_unviewed_changes = ?
            WHERE display_domain = ?
            """,
            (int(unviewed), display_name),
        )


def mark_viewed(display_name: str) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE domains SET has_unviewed_changes = 0 WHERE display_domain = ?",
            (display_name,),
        )


def finalize_generation(
    display_name: str,
    *,
    llms_txt: str,
    pages_included: int,
) -> None:
    domain_id = get_domain_id(display_name)
    if domain_id is None:
        return

    generation_hashes_json = json.dumps(load_page_hashes(domain_id))

    with _connect() as conn:
        conn.execute(
            """
            UPDATE domains
            SET llms_txt = ?, pages_included = ?, has_updates = 0,
                generation_hashes_json = ?, has_unviewed_changes = 0
            WHERE display_domain = ?
            """,
            (llms_txt, pages_included, generation_hashes_json, display_name),
        )
