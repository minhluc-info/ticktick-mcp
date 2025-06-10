"""
Cross-platform timezone utilities with fallback for Windows compatibility.
Designed for global MCP usage with automatic timezone detection.
"""
import os
import logging
import time
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
    # Expanded for global coverage
    timezone_offsets = {
        # UTC
        "UTC": 0,
        
        # Americas
        "America/New_York": -5,        # EST (adjust for DST manually if needed)
        "America/Chicago": -6,         # CST
        "America/Denver": -7,          # MST
        "America/Los_Angeles": -8,     # PST
        "America/Toronto": -5,         # EST
        "America/Vancouver": -8,       # PST
        "America/Mexico_City": -6,     # CST
        "America/Sao_Paulo": -3,       # BRT
        "America/Argentina/Buenos_Aires": -3,  # ART
        
        # Europe
        "Europe/London": 0,            # GMT (adjust for DST manually if needed)
        "Europe/Berlin": 1,            # CET
        "Europe/Paris": 1,             # CET
        "Europe/Rome": 1,              # CET
        "Europe/Amsterdam": 1,         # CET
        "Europe/Madrid": 1,            # CET
        "Europe/Stockholm": 1,         # CET
        "Europe/Moscow": 3,            # MSK
        "Europe/Kiev": 2,              # EET
        
        # Asia-Pacific
        "Asia/Tokyo": 9,               # JST
        "Asia/Shanghai": 8,            # CST
        "Asia/Hong_Kong": 8,           # HKT
        "Asia/Singapore": 8,           # SGT
        "Asia/Bangkok": 7,             # ICT
        "Asia/Jakarta": 7,             # WIB
        "Asia/Manila": 8,              # PHT
        "Asia/Seoul": 9,               # KST
        "Asia/Taipei": 8,              # CST
        "Asia/Kuala_Lumpur": 8,        # MYT
        "Asia/Ho_Chi_Minh": 7,         # ICT
        "Asia/Kolkata": 5.5,           # IST (5:30)
        "Asia/Mumbai": 5.5,            # IST (5:30)
        "Asia/Dubai": 4,               # GST
        "Asia/Riyadh": 3,              # AST
        
        # Australia/New Zealand
        "Australia/Sydney": 10,        # AEST (adjust for DST manually if needed)
        "Australia/Melbourne": 10,     # AEST
        "Australia/Perth": 8,          # AWST
        "Pacific/Auckland": 12,        # NZST (adjust for DST manually if needed)
        
        # Africa
        "Africa/Cairo": 2,             # EET
        "Africa/Johannesburg": 2,      # SAST
        "Africa/Lagos": 1,             # WAT
        "Africa/Nairobi": 3,           # EAT
    }
    
    offset_hours = timezone_offsets.get(tz_name, 0)
    if offset_hours == 0:
        return timezone.utc
    elif isinstance(offset_hours, float):
        # Handle timezones with 30-minute offsets (like India)
        hours = int(offset_hours)
        minutes = int((offset_hours - hours) * 60)
        return timezone(timedelta(hours=hours, minutes=minutes))
    else:
        return timezone(timedelta(hours=offset_hours))

def detect_system_timezone() -> str:
    """
    Try to detect the system timezone automatically.
    
    Returns:
        IANA timezone name or None if detection fails
    """
    try:
        # Method 1: Try to get timezone from system time module
        if hasattr(time, 'tzname') and time.tzname:
            # This gives timezone abbreviations like 'EST', 'PST'
            # We need to map these to IANA names
            tz_abbrev = time.tzname[0] if time.daylight == 0 else time.tzname[1]
            logger.debug(f"Detected timezone abbreviation: {tz_abbrev}")
            
        # Method 2: Try to get timezone offset and map to common zones
        local_time = datetime.now()
        utc_time = datetime.utcnow()
        offset = local_time - utc_time
        offset_hours = offset.total_seconds() / 3600
        
        # Map common offsets to likely timezones
        offset_to_timezone = {
            0: "UTC",
            1: "Europe/Berlin",     # Most common for +1
            -5: "America/New_York", # Most common for -5
            -8: "America/Los_Angeles", # Most common for -8
            8: "Asia/Shanghai",     # Most common for +8
            9: "Asia/Tokyo",        # Most common for +9
            7: "Asia/Bangkok",      # Most common for +7
            5.5: "Asia/Kolkata",    # India Standard Time
            -3: "America/Sao_Paulo", # Most common for -3
            2: "Europe/Kiev",       # Most common for +2
            3: "Europe/Moscow",     # Most common for +3
        }
        
        detected_tz = offset_to_timezone.get(offset_hours)
        if detected_tz:
            logger.info(f"Auto-detected timezone: {detected_tz} (offset: {offset_hours:+.1f}h)")
            return detected_tz
            
    except Exception as e:
        logger.debug(f"Failed to auto-detect system timezone: {e}")
    
    return None

def get_user_timezone():
    """
    Get user timezone from environment with intelligent fallbacks.
    
    Priority:
    1. TICKTICK_USER_TIMEZONE environment variable
    2. Auto-detected system timezone
    3. UTC (universal fallback)
    """
    # 1. Check environment variable first
    env_tz = os.getenv("TICKTICK_USER_TIMEZONE")
    if env_tz:
        logger.info(f"Using timezone from environment: {env_tz}")
        return get_timezone_safe(env_tz)
    
    # 2. Try to auto-detect system timezone
    detected_tz = detect_system_timezone()
    if detected_tz:
        logger.info(f"Using auto-detected timezone: {detected_tz}")
        return get_timezone_safe(detected_tz)
    
    # 3. Fallback to UTC (most universal)
    logger.info("Using UTC timezone as fallback")
    return get_timezone_safe("UTC")

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
