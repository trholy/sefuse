EU_STATUS_FORTHCOMING = "31094501"
EU_STATUS_OPEN = "31094502"
EU_ACTIVE_STATUS_CODES = {EU_STATUS_FORTHCOMING, EU_STATUS_OPEN}


def is_allowed_status(status_code: str | None) -> bool:
    """Return ``True`` when `status_code` is OPEN or FORTHCOMING."""
    return status_code in EU_ACTIVE_STATUS_CODES
