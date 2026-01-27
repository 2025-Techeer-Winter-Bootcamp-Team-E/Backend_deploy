"""
Shared utility functions.
"""
import re
import uuid
from datetime import datetime
from typing import Optional


def generate_uuid() -> str:
    """Generate a new UUID string."""
    return str(uuid.uuid4())


def is_valid_uuid(value: str) -> bool:
    """Check if string is a valid UUID."""
    try:
        uuid.UUID(str(value))
        return True
    except ValueError:
        return False


def is_valid_email(email: str) -> bool:
    """Validate email format."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def is_valid_phone_number(phone: str) -> bool:
    """Validate Korean phone number format."""
    # Remove hyphens and spaces
    cleaned = re.sub(r'[-\s]', '', phone)
    # Korean phone patterns
    patterns = [
        r'^01[016789]\d{7,8}$',  # Mobile: 010-xxxx-xxxx
        r'^02\d{7,8}$',          # Seoul: 02-xxx-xxxx
        r'^0[3-6]\d{8}$',        # Regional
    ]
    return any(re.match(p, cleaned) for p in patterns)


def format_currency(amount: float, currency: str = 'KRW') -> str:
    """Format amount as currency string."""
    if currency == 'KRW':
        return f"₩{amount:,.0f}"
    elif currency == 'USD':
        return f"${amount:,.2f}"
    else:
        return f"{amount:,.2f} {currency}"


def slugify(text: str) -> str:
    """Convert text to URL-safe slug."""
    import unicodedata
    # Normalize unicode characters
    text = unicodedata.normalize('NFKD', text)
    # Convert to lowercase and replace spaces with hyphens
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    return text


def truncate_string(text: str, max_length: int, suffix: str = '...') -> str:
    """Truncate string to max length with suffix."""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def mask_email(email: str) -> str:
    """Mask email address for privacy."""
    if '@' not in email:
        return email
    local, domain = email.split('@', 1)
    if len(local) <= 2:
        masked_local = '*' * len(local)
    else:
        masked_local = local[0] + '*' * (len(local) - 2) + local[-1]
    return f"{masked_local}@{domain}"


def mask_phone(phone: str) -> str:
    """Mask phone number for privacy."""
    cleaned = re.sub(r'[-\s]', '', phone)
    if len(cleaned) >= 7:
        return cleaned[:3] + '*' * (len(cleaned) - 6) + cleaned[-3:]
    return '*' * len(cleaned)
