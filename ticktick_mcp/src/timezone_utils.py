"""
Cross-platform timezone utilities with fallback for Windows compatibility.
"""
import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
import re

logger = logging.getLogger(__name__)

def get_timezone_safe(tz_name: str = "UTC"):
    """
    Get timezone object with cross-platform compatibility.
    
    Args:
        tz_name: IANA timezone name (e.g., "UTC", "Asia/Bangkok")
        
    Returns:
        timezone object
    """
    # Try zoneinfo first (Python 3.9+)
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(tz_name)
    except ImportError:
        logger.warning("zoneinfo not available, falling back to basic timezone")
    except Exception as e:
        logger.warning(f"Failed to load timezone {tz_name}: {e}")
    
    # Fallback to basic timezone offsets for common timezones
    timezone_offsets = {
        "UTC": 0,
        "Asia/Bangkok": 7,
        "America/New_York": -5,  # EST (adjust for DST manually if needed)
        "America/Los_Angeles": -8,  # PST
        "Europe/London": 0,  # GMT (adjust for DST manually if needed)
        "Europe/Berlin": 1,  # CET
        "Asia/Tokyo": 9,
        "Asia/Shanghai": 8,
        "Australia/Sydney": 10,  # AEST (adjust for DST manually if needed)
    }
    
    offset_hours = timezone_offsets.get(tz_name, 0)
    if offset_hours == 0:
        return timezone.utc
    else:
        return timezone(timedelta(hours=offset_hours))

def get_user_timezone():
    """Get user timezone from environment with fallback."""
    tz_name = os.getenv("USER_TIMEZONE", "Asia/Bangkok")  # Default to Bangkok for backward compatibility
    return get_timezone_safe(tz_name)

def normalize_datetime_for_user(date_str: str) -> str:
    """
    Convert date string to user timezone if no timezone specified.
    
    Args:
        date_str: Date string in various formats
        
    Returns:
        ISO formatted date string with user timezone
    """
    if not date_str:
        return date_str
    
    # If no timezone info, assume user timezone
    if not re.search(r'[+-]\d{2}:?\d{2}|Z$', date_str):
        user_tz = get_user_timezone()
        
        # Get current UTC offset for user timezone
        now_in_user_tz = datetime.now(user_tz)
        offset = now_in_user_tz.strftime('%z')
        
        # Format offset as +HH:MM
        if offset:
            formatted_offset = f"{offset[:3]}:{offset[3:]}"
        else:
            # Fallback for basic timezone objects
            total_seconds = user_tz.utcoffset(datetime.now()).total_seconds()
            hours, remainder = divmod(int(total_seconds), 3600)
            minutes = remainder // 60
            formatted_offset = f"{hours:+03d}:{minutes:02d}"
        
        if 'T' in date_str:
            return date_str + formatted_offset
        else:
            return date_str + f'T00:00:00{formatted_offset}'
    
    return date_str

def get_current_user_time() -> datetime:
    """Get current time in user timezone."""
    user_tz = get_user_timezone()
    return datetime.now(user_tz)

def validate_datetime_string(date_str: str, field_name: str) -> Optional[str]:
    """
    Validate datetime string format.
    
    Args:
        date_str: Date string to validate
        field_name: Name of field for error message
        
    Returns:
        None if valid, error message if invalid
    """
    if not date_str:
        return None
    
    try:
        # Try to parse the date to validate it
        # Handle Z suffix by replacing with +00:00
        test_date = date_str.replace("Z", "+00:00")
        datetime.fromisoformat(test_date)
        return None
    except ValueError:
        return f"Invalid {field_name} format. Use ISO format: YYYY-MM-DDTHH:mm:ss+HH:MM or YYYY-MM-DD"
