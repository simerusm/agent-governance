from __future__ import annotations


def luhn_valid(digits: str) -> bool:
    """Return True if digit string passes Luhn check (typical PAN length 13-19)."""
    d = [int(c) for c in digits if c.isdigit()]
    if len(d) < 13 or len(d) > 19:
        return False
    s = 0
    # From right: double every second digit (index 1,3,5,... from the right)
    for i, x in enumerate(reversed(d)):
        if i % 2 == 1:
            x *= 2
            if x > 9:
                x -= 9
        s += x
    return s % 10 == 0


def ssn_plausible(text: str) -> bool:
    """Lightweight SSN sanity check for ###-##-#### match."""
    parts = text.replace(" ", "").split("-")
    if len(parts) != 3:
        return False
    if not all(p.isdigit() for p in parts):
        return False
    if len(parts[0]) != 3 or len(parts[1]) != 2 or len(parts[2]) != 4:
        return False
    area = int(parts[0])
    group = int(parts[1])
    serial = int(parts[2])
    if area == 0 or area == 666 or area >= 900:
        return False
    if group == 0:
        return False
    if serial == 0:
        return False
    return True
