def detect_changes(
    stored_hashes: dict[str, str],
    current_hashes: dict[str, str],
) -> bool:
    """Return True when page URLs or content hashes differ from the stored baseline."""
    if not stored_hashes:
        return False

    if set(stored_hashes) != set(current_hashes):
        return True

    return any(
        stored_hashes[url] != current_hashes[url]
        for url in current_hashes
        if url in stored_hashes
    )
