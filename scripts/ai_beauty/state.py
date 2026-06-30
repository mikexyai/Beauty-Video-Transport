from __future__ import annotations

NEW_STATUS = "new"
ARCHIVED_STATUS = "archived"
BATCH_SELECTED_STATUS = "batch_selected"
SCREENED_OUT_STATUS = "screened_out"
UPLOADED_STATUS = "uploaded"
ARCHIVE_PRUNED_STATUS = "archive_pruned"
FAILED_STATUS = "failed"
DOWNLOADED_STATUS = "downloaded"
APPROVED_STATUS = "approved"

ACTIVE_STATUSES = (NEW_STATUS, ARCHIVED_STATUS)
PROCESSABLE_STATUSES = (BATCH_SELECTED_STATUS, FAILED_STATUS)
TERMINAL_STATUSES = (SCREENED_OUT_STATUS, UPLOADED_STATUS, ARCHIVE_PRUNED_STATUS)
ALL_CANDIDATE_STATUSES = (
    NEW_STATUS,
    ARCHIVED_STATUS,
    BATCH_SELECTED_STATUS,
    SCREENED_OUT_STATUS,
    UPLOADED_STATUS,
    ARCHIVE_PRUNED_STATUS,
    FAILED_STATUS,
    DOWNLOADED_STATUS,
    APPROVED_STATUS,
)

# Conservative transition map for explicit state changes. It allows normal
# retries/re-ranking but prevents terminal rejected/uploaded rows from being
# silently reactivated.
ALLOWED_TRANSITIONS: dict[str, tuple[str, ...]] = {
    NEW_STATUS: (ARCHIVED_STATUS, BATCH_SELECTED_STATUS, FAILED_STATUS),
    ARCHIVED_STATUS: (BATCH_SELECTED_STATUS, ARCHIVE_PRUNED_STATUS, FAILED_STATUS),
    BATCH_SELECTED_STATUS: (ARCHIVED_STATUS, SCREENED_OUT_STATUS, UPLOADED_STATUS, FAILED_STATUS),
    FAILED_STATUS: (BATCH_SELECTED_STATUS, SCREENED_OUT_STATUS, ARCHIVED_STATUS),
    SCREENED_OUT_STATUS: (),
    UPLOADED_STATUS: (),
    ARCHIVE_PRUNED_STATUS: (),
}


def is_active_status(status: str | None) -> bool:
    return str(status or "") in ACTIVE_STATUSES


def is_processable_status(status: str | None) -> bool:
    return str(status or "") in PROCESSABLE_STATUSES


def is_terminal_status(status: str | None) -> bool:
    return str(status or "") in TERMINAL_STATUSES


def assert_known_status(status: str | None) -> bool:
    value = str(status or "")
    if value not in ALL_CANDIDATE_STATUSES:
        raise ValueError(f"Unknown AI Beauty candidate status: {value!r}")
    return True


def assert_transition_allowed(current_status: str | None, next_status: str | None) -> bool:
    current = str(current_status or "")
    next_value = str(next_status or "")
    assert_known_status(current)
    assert_known_status(next_value)
    if current == next_value:
        return True
    allowed = ALLOWED_TRANSITIONS.get(current, ())
    if next_value not in allowed:
        raise ValueError(f"Illegal AI Beauty candidate status transition: {current!r} -> {next_value!r}")
    return True
