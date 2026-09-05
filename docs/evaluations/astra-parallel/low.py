"""Parse ordered hour, minute, and second duration terms."""

import re


def parse_duration(value):
    """Return duration seconds, accepting totals from zero through 86400."""
    if not isinstance(value, str):
        raise TypeError("duration must be a str")

    value = value.strip(" ")
    if not value:
        raise ValueError("duration must contain at least one term")

    units = {"h": 3600, "m": 60, "s": 1}
    position = 0
    previous_unit = 3601
    total = 0
    while position < len(value):
        match = re.match(r"([0-9]+)([hms]) *", value[position:])
        if match is None:
            raise ValueError("invalid duration term")
        multiplier = units[match.group(2)]
        if multiplier >= previous_unit:
            raise ValueError("units must be strictly descending")
        previous_unit = multiplier

        # Strip leading zeros before conversion to support arbitrarily padded
        # values without depending on Python's integer-string length limit.
        digits = match.group(1).lstrip("0") or "0"
        if len(digits) > 5:
            raise ValueError("duration exceeds 86400 seconds")
        total += int(digits) * multiplier
        if total > 86400:
            raise ValueError("duration exceeds 86400 seconds")
        position += match.end()

    return total
