import re


def parse_duration(value):
    """Parse descending h/m/s terms into at most one day of seconds."""
    if not isinstance(value, str):
        raise TypeError("duration must be a string")

    value = value.strip(" ")
    if not value:
        raise ValueError("duration must contain at least one term")

    factors = {"h": 3600, "m": 60, "s": 1}
    previous_factor = 3601
    total = 0
    position = 0
    while position < len(value):
        match = re.match(r"([0-9]+)([hms]) *", value[position:])
        if match is None:
            raise ValueError("invalid duration term")
        digits, unit = match.groups()
        factor = factors[unit]
        if factor >= previous_factor:
            raise ValueError("units must be in strictly descending order")
        previous_factor = factor

        # Bound conversion so arbitrarily many leading zeros remain valid.
        digits = digits.lstrip("0") or "0"
        if len(digits) > 5:
            raise ValueError("duration exceeds 86400 seconds")
        total += int(digits) * factor
        if total > 86400:
            raise ValueError("duration exceeds 86400 seconds")
        position += match.end()

    return total
