from django.contrib.auth.hashers import check_password, identify_hasher
from django.utils.crypto import constant_time_compare


def verify_account_password(raw, stored):
    """Return (valid, needs_hashing) while allowing legacy users to sign in."""
    if not isinstance(stored, str) or not stored:
        return False, False
    try:
        identify_hasher(stored)
    except ValueError:
        return constant_time_compare(raw, stored), True
    try:
        return check_password(raw, stored), False
    except (ValueError, TypeError):
        return False, False
