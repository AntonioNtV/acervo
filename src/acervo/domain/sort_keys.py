DIGITS = "0123456789abcdefghijklmnopqrstuvwxyz"


def key_between(before: str | None, after: str | None) -> str:
    """A sort key strictly between two neighbours' keys (None is an open end), so placing an item writes one row."""
    return _midpoint(before or "", after)


def _midpoint(low: str, high: str | None) -> str:
    if high is not None:
        shared = 0
        while (low[shared] if shared < len(low) else "0") == high[shared]:
            shared += 1
        if shared:
            return high[:shared] + _midpoint(low[shared:], high[shared:])
    low_digit = DIGITS.index(low[0]) if low else 0
    high_digit = DIGITS.index(high[0]) if high is not None else len(DIGITS)
    if high_digit - low_digit > 1:
        return DIGITS[(low_digit + high_digit) // 2]
    if high is not None and len(high) > 1:
        return high[0]
    return DIGITS[low_digit] + _midpoint(low[1:], None)
