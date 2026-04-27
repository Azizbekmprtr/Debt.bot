# utils/helpers.py
import re
from datetime import datetime, timedelta
from typing import Optional, Tuple, List, Dict

def validate_phone(phone: str) -> Tuple[bool, Optional[str]]:
    """Validate and clean phone number"""
    # Remove all non-digit characters except +
    cleaned = re.sub(r'[^\d+]', '', phone)

    # Check if it's a valid Uzbek phone number
    if re.match(r'^\+998\d{9}$', cleaned):
        return True, cleaned
    elif re.match(r'^998\d{9}$', cleaned):
        return True, '+' + cleaned
    elif re.match(r'^\d{9}$', cleaned):
        return True, '+998' + cleaned

    return False, None

def format_price(price: int) -> str:
    """Format price with spaces as thousand separators"""
    if price is None:
        return "0"
    return f"{int(price):,}".replace(",", " ")

def validate_email(email: str) -> bool:
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def get_time_remaining(deadline: datetime) -> str:
    """Get human-readable time remaining"""
    now = datetime.now()

    if deadline < now:
        return "⚠️ Overdue"

    delta = deadline - now

    if delta.days > 30:
        months = delta.days // 30
        return f"{months} month{'s' if months > 1 else ''} left"
    elif delta.days > 0:
        return f"{delta.days} day{'s' if delta.days > 1 else ''} left"
    elif delta.seconds > 3600:
        hours = delta.seconds // 3600
        return f"{hours} hour{'s' if hours > 1 else ''} left"
    elif delta.seconds > 60:
        minutes = delta.seconds // 60
        return f"{minutes} minute{'s' if minutes > 1 else ''} left"
    else:
        return "Less than a minute left"

def split_message(text: str, max_length: int = 4000) -> List[str]:
    """Split long message into Telegram-compatible chunks"""
    if len(text) <= max_length:
        return [text]

    chunks = []
    while len(text) > max_length:
        # Find last newline or space before max_length
        split_at = text.rfind('\n', 0, max_length)
        if split_at == -1:
            split_at = text.rfind(' ', 0, max_length)
        if split_at == -1:
            split_at = max_length

        chunks.append(text[:split_at])
        text = text[split_at:].lstrip()

    if text:
        chunks.append(text)

    return chunks

def generate_unique_code(prefix: str = "", length: int = 8) -> str:
    """Generate a unique code"""
    import random
    import string
    chars = string.ascii_uppercase + string.digits
    code = ''.join(random.choices(chars, k=length))
    return f"{prefix}{code}" if prefix else code

def parse_date_range(text: str) -> Tuple[Optional[datetime], Optional[datetime]]:
    """Parse date range from text input"""
    # Try formats: "2024-01-01 to 2024-01-31", "2024-01-01", "today", "this week"
    text = text.strip().lower()

    if text == "today":
        today = datetime.now().replace(hour=0, minute=0, second=0)
        return today, today + timedelta(days=1)

    if text == "this week":
        today = datetime.now()
        start = today - timedelta(days=today.weekday())
        return start.replace(hour=0, minute=0, second=0), None

    if text == "this month":
        today = datetime.now()
        start = today.replace(day=1, hour=0, minute=0, second=0)
        return start, None

    if " to " in text:
        parts = text.split(" to ")
        try:
            start = datetime.strptime(parts[0].strip(), "%Y-%m-%d")
            end = datetime.strptime(parts[1].strip(), "%Y-%m-%d")
            return start, end
        except ValueError:
            pass

    try:
        date = datetime.strptime(text, "%Y-%m-%d")
        return date, date + timedelta(days=1)
    except ValueError:
        pass

    return None, None

def truncate_text(text: str, max_length: int = 100) -> str:
    """Truncate text with ellipsis"""
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + "..."

def get_level_emoji(level: str) -> str:
    """Get emoji for language level"""
    emojis = {
        'A1': '🌱',
        'A2': '🌿',
        'B1': '🌳',
        'B2': '🏗️',
        'C1': '🏢',
    }
    return emojis.get(level, '📚')

def get_status_emoji(status: str) -> str:
    """Get emoji for various statuses"""
    status_emojis = {
        'active': '🟢',
        'inactive': '🔴',
        'pending': '🟡',
        'completed': '✅',
        'cancelled': '❌',
        'suspended': '⏸️',
        'archived': '📦',
        'open': '📬',
        'in_progress': '🔄',
        'resolved': '✅',
        'closed': '🔒',
        'urgent': '🔴',
        'high': '🟠',
        'normal': '🟡',
        'low': '🟢',
    }
    return status_emojis.get(status, '❓')

def format_datetime(dt: datetime, format_type: str = 'full') -> str:
    """Format datetime in various styles"""
    if not dt:
        return "N/A"

    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt)
        except ValueError:
            return dt

    formats = {
        'full': dt.strftime('%Y-%m-%d %H:%M:%S'),
        'date': dt.strftime('%Y-%m-%d'),
        'time': dt.strftime('%H:%M'),
        'friendly': dt.strftime('%d %B %Y, %H:%M'),
        'short_date': dt.strftime('%d.%m.%Y'),
        'relative': get_relative_time(dt),
    }

    return formats.get(format_type, formats['full'])

def get_relative_time(dt: datetime) -> str:
    """Get relative time string (e.g., '2 hours ago')"""
    now = datetime.now()
    diff = now - dt

    if diff.days > 365:
        years = diff.days // 365
        return f"{years} year{'s' if years > 1 else ''} ago"
    elif diff.days > 30:
        months = diff.days // 30
        return f"{months} month{'s' if months > 1 else ''} ago"
    elif diff.days > 0:
        return f"{diff.days} day{'s' if diff.days > 1 else ''} ago"
    elif diff.seconds > 3600:
        hours = diff.seconds // 3600
        return f"{hours} hour{'s' if hours > 1 else ''} ago"
    elif diff.seconds > 60:
        minutes = diff.seconds // 60
        return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
    else:
        return "Just now"

def calculate_percentage(part: int, total: int) -> float:
    """Calculate percentage safely"""
    if total == 0:
        return 0.0
    return round((part / total) * 100, 1)

def generate_progress_bar(percentage: float, length: int = 10) -> str:
    """Generate a text-based progress bar"""
    filled = int(percentage / 100 * length)
    empty = length - filled
    return "▓" * filled + "░" * empty

def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe saving"""
    # Remove or replace unsafe characters
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # Remove leading/trailing spaces and dots
    sanitized = sanitized.strip('. ')
    # Limit length
    if len(sanitized) > 200:
        name, ext = os.path.splitext(sanitized)
        sanitized = name[:200-len(ext)] + ext
    return sanitized if sanitized else 'unnamed'

def parse_user_info_from_text(text: str) -> Dict[str, str]:
    """Parse user information from text input"""
    info = {
        'full_name': '',
        'username': None,
        'phone': None,
        'telegram_id': None
    }

    parts = text.strip().split()

    # Extract Telegram ID (last numeric part)
    if parts and parts[-1].isdigit() and len(parts[-1]) >= 5:
        info['telegram_id'] = parts[-1]
        parts = parts[:-1]

    # Extract phone number
    for i, part in enumerate(parts):
        cleaned = re.sub(r'[^\d+]', '', part)
        if cleaned.startswith('+') or (cleaned.isdigit() and len(cleaned) >= 9):
            is_valid, phone = validate_phone(cleaned)
            if is_valid:
                info['phone'] = phone
                parts.pop(i)
                break

    # Extract username
    for i, part in enumerate(parts):
        if part.startswith('@'):
            info['username'] = part.lstrip('@')
            parts.pop(i)
            break

    # Remaining parts are the name
    info['full_name'] = ' '.join(parts).strip()

    return info
