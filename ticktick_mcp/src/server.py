import asyncio
import json
import os
import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

# Timezone support with fallback
try:
    from zoneinfo import ZoneInfo
except ImportError:
    # Fallback for Python < 3.9
    from datetime import timezone, timedelta
    class ZoneInfo:
        @staticmethod
        def __new__(cls, key):
            if key == "Asia/Bangkok":
                return timezone(timedelta(hours=7))
            elif key == "UTC":
                return timezone.utc
            else:
                return timezone.utc

from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

from .ticktick_client import TickTickClient

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# User timezone configuration
UTC_TIMEZONE = ZoneInfo("UTC")

def get_user_timezone():
    """Get user timezone from env variable, system, or fallback to UTC."""
    # 1. Check .env file first
    env_tz = os.getenv("TICKTICK_USER_TIMEZONE")
    if env_tz:
        try:
            return ZoneInfo(env_tz)
        except Exception:
            logger.warning(f"Invalid timezone in .env: {env_tz}, falling back to system timezone")
    
    # 2. Try to detect system timezone
    try:
        import time
        system_tz = time.tzname[0] if time.daylight == 0 else time.tzname[1]
        return ZoneInfo(system_tz)
    except Exception:
        logger.warning("Could not detect system timezone, using UTC")
        # 3. Fallback to UTC
        return ZoneInfo("UTC")

# Get user timezone
USER_TIMEZONE = get_user_timezone()

# Create FastMCP server
mcp = FastMCP("ticktick")

# Create TickTick client
ticktick = None

def normalize_datetime_for_user(date_str: str) -> str:
    """
    Convert datetime string to user's timezone.
    Handles various input formats and ensures proper timezone conversion.
    
    Args:
        date_str: ISO format datetime string
        
    Returns:
        Properly formatted datetime string in user's timezone
    """
    if not date_str:
        return date_str
        
    try:
        # Parse the datetime
        if date_str.endswith('Z'):
            # UTC format
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        elif '+' in date_str or date_str.count('-') > 2:
            # Already has timezone info
            dt = datetime.fromisoformat(date_str)
        else:
            # No timezone info - assume user's timezone
            dt = datetime.fromisoformat(date_str)
            dt = dt.replace(tzinfo=USER_TIMEZONE)
            
        # Convert to user timezone if needed
        if dt.tzinfo != USER_TIMEZONE:
            dt = dt.astimezone(USER_TIMEZONE)
            
        # Return in ISO format with timezone
        return dt.isoformat()
        
    except ValueError as e:
        logger.warning(f"Failed to parse datetime '{date_str}': {e}")
        # Return original string if parsing fails
        return date_str

def validate_datetime_string(date_str: str, field_name: str) -> Optional[str]:
    """
    Validate and normalize datetime string.
    
    Args:
        date_str: Input datetime string
        field_name: Name of the field for error messages
        
    Returns:
        Error message if invalid, None if valid
    """
    if not date_str:
        return None
        
    try:
        normalized = normalize_datetime_for_user(date_str)
        return None
    except Exception as e:
        return f"Invalid {field_name} format. Use ISO format: YYYY-MM-DDTHH:mm:ss+07:00 or YYYY-MM-DDTHH:mm:ss"

def initialize_client():
    global ticktick
    try:
        # Check if .env file exists with access token
        load_dotenv()
        
        # Check if we have valid credentials
        if os.getenv("TICKTICK_ACCESS_TOKEN") is None:
            logger.error("No access token found in .env file. Please run 'uv run -m ticktick_mcp.cli auth' to authenticate.")
            return False
        
        # Initialize the client
        ticktick = TickTickClient()
        logger.info("TickTick client initialized successfully")
        
        # Test API connectivity
        projects = ticktick.get_projects()
        if 'error' in projects:
            logger.error(f"Failed to access TickTick API: {projects['error']}")
            logger.error("Your access token may have expired. Please run 'uv run -m ticktick_mcp.cli auth' to refresh it.")
            return False
            
        logger.info(f"Successfully connected to TickTick API with {len(projects)} projects")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize TickTick client: {e}")
        return False

# Format a task object from TickTick for better display
def format_task(task: Dict) -> str:
    """Format a task into a human-readable string."""
    formatted = f"ID: {task.get('id', 'No ID')}\n"
    formatted += f"Title: {task.get('title', 'No title')}\n"
    
    # Add project ID
    formatted += f"Project ID: {task.get('projectId', 'None')}\n"
    
    # Add dates if available - now with proper timezone display
    if task.get('startDate'):
        # Normalize to user timezone for display
        normalized_start = normalize_datetime_for_user(task.get('startDate'))
        formatted += f"Start Date: {normalized_start}\n"
    if task.get('dueDate'):
        # Normalize to user timezone for display
        normalized_due = normalize_datetime_for_user(task.get('dueDate'))
        formatted += f"Due Date: {normalized_due}\n"
    
    # Add priority if available
    priority_map = {0: "None", 1: "Low", 3: "Medium", 5: "High"}
    priority = task.get('priority', 0)
    formatted += f"Priority: {priority_map.get(priority, str(priority))}\n"
    
    # Add status if available
    status = "Completed" if task.get('status') == 2 else "Active"
    formatted += f"Status: {status}\n"
    
    # Add content if available
    if task.get('content'):
        formatted += f"\nContent:\n{task.get('content')}\n"
    
    # Add subtasks if available
    items = task.get('items', [])
    if items:
        formatted += f"\nSubtasks ({len(items)}):\n"
        for i, item in enumerate(items, 1):
            status = "✓" if item.get('status') == 1 else "◇"
            formatted += f"{i}. [{status}] {item.get('title', 'No title')}\n"
    
    return formatted

# Format a project object from TickTick for better display
def format_project(project: Dict) -> str:
    """Format a project into a human-readable string."""
    formatted = f"Name: {project.get('name', 'No name')}\n"
    formatted += f"ID: {project.get('id', 'No ID')}\n"
    
    # Add color if available
    if project.get('color'):
        formatted += f"Color: {project.get('color')}\n"
    
    # Add view mode if available
    if project.get('viewMode'):
        formatted += f"View Mode: {project.get('viewMode')}\n"
    
    # Add closed status if available
    if 'closed' in project:
        formatted += f"Closed: {'Yes' if project.get('closed') else 'No'}\n"
    
    # Add kind if available
    if project.get('kind'):
        formatted += f"Kind: {project.get('kind')}\n"
    
    return formatted

# MCP Tools

@mcp.tool()
async def get_projects() -> str:
    """Get all projects from TickTick."""
    if not ticktick:
        if not initialize_client():
            return "Failed to initialize TickTick client. Please check your API credentials."
    
    try:
        projects = ticktick.get_projects()
        if 'error' in projects:
            return f"Error fetching projects: {projects['error']}"
        
        if not projects:
            return "No projects found."
        
        result = f"Found {len(projects)} projects:\n\n"
        for i, project in enumerate(projects, 1):
            result += f"Project {i}:\n" + format_project(project) + "\n"
        
        return result
    except Exception as e:
        logger.error(f"Error in get_projects: {e}")
        return f"Error retrieving projects: {str(e)}"

@mcp.tool()
async def get_project(project_id: str) -> str:
    """
    Get details about a specific project.
    
    Args:
        project_id: ID of the project
    """
    if not ticktick:
        if not initialize_client():
            return "Failed to initialize TickTick client. Please check your API credentials."
    
    try:
        project = ticktick.get_project(project_id)
        if 'error' in project:
            return f"Error fetching project: {project['error']}"
        
        return format_project(project)
    except Exception as e:
        logger.error(f"Error in get_project: {e}")
        return f"Error retrieving project: {str(e)}"

@mcp.tool()
async def get_project_tasks(project_id: str) -> str:
    """
    Get all tasks in a specific project.
    
    Args:
        project_id: ID of the project
    """
    if not ticktick:
        if not initialize_client():
            return "Failed to initialize TickTick client. Please check your API credentials."
    
    try:
        project_data = ticktick.get_project_with_data(project_id)
        if 'error' in project_data:
            return f"Error fetching project data: {project_data['error']}"
        
        tasks = project_data.get('tasks', [])
        if not tasks:
            return f"No tasks found in project '{project_data.get('project', {}).get('name', project_id)}'."
        
        result = f"Found {len(tasks)} tasks in project '{project_data.get('project', {}).get('name', project_id)}':\n\n"
        for i, task in enumerate(tasks, 1):
            result += f"Task {i}:\n" + format_task(task) + "\n"
        
        return result
    except Exception as e:
        logger.error(f"Error in get_project_tasks: {e}")
        return f"Error retrieving project tasks: {str(e)}"

@mcp.tool()
async def get_task(project_id: str, task_id: str) -> str:
    """
    Get details about a specific task.
    
    Args:
        project_id: ID of the project
        task_id: ID of the task
    """
    if not ticktick:
        if not initialize_client():
            return "Failed to initialize TickTick client. Please check your API credentials."
    
    try:
        task = ticktick.get_task(project_id, task_id)
        if 'error' in task:
            return f"Error fetching task: {task['error']}"
        
        return format_task(task)
    except Exception as e:
        logger.error(f"Error in get_task: {e}")
        return f"Error retrieving task: {str(e)}"

@mcp.tool()
async def create_task(
    title: str, 
    project_id: str, 
    content: str = None, 
    start_date: str = None, 
    due_date: str = None, 
    priority: int = 0
) -> str:
    """
    Create a new task in TickTick.
    
    Args:
        title: Task title
        project_id: ID of the project to add the task to
        content: Task description/content (optional)
        start_date: Start date in Asia/Bangkok timezone. Formats: YYYY-MM-DDTHH:mm:ss or YYYY-MM-DDTHH:mm:ss+07:00 (optional)
        due_date: Due date in Asia/Bangkok timezone. Formats: YYYY-MM-DDTHH:mm:ss or YYYY-MM-DDTHH:mm:ss+07:00 (optional)
        priority: Priority level (0: None, 1: Low, 3: Medium, 5: High) (optional)
    """
    if not ticktick:
        if not initialize_client():
            return "Failed to initialize TickTick client. Please check your API credentials."
    
    # Validate priority
    if priority not in [0, 1, 3, 5]:
        return "Invalid priority. Must be 0 (None), 1 (Low), 3 (Medium), or 5 (High)."
    
    try:
        # Validate and normalize dates if provided
        normalized_start_date = None
        normalized_due_date = None
        
        if start_date:
            validation_error = validate_datetime_string(start_date, "start_date")
            if validation_error:
                return validation_error
            normalized_start_date = normalize_datetime_for_user(start_date)
        
        if due_date:
            validation_error = validate_datetime_string(due_date, "due_date")
            if validation_error:
                return validation_error
            normalized_due_date = normalize_datetime_for_user(due_date)
        
        task = ticktick.create_task(
            title=title,
            project_id=project_id,
            content=content,
            start_date=normalized_start_date,
            due_date=normalized_due_date,
            priority=priority
        )
        
        if 'error' in task:
            return f"Error creating task: {task['error']}"
        
        return f"Task created successfully:\n\n" + format_task(task)
    except Exception as e:
        logger.error(f"Error in create_task: {e}")
        return f"Error creating task: {str(e)}"

@mcp.tool()
async def update_task(
    task_id: str,
    project_id: str,
    title: str = None,
    content: str = None,
    start_date: str = None,
    due_date: str = None,
    priority: int = None
) -> str:
    """
    Update an existing task in TickTick.
    
    Args:
        task_id: ID of the task to update
        project_id: ID of the project the task belongs to
        title: New task title (optional)
        content: New task description/content (optional)
        start_date: New start date in Asia/Bangkok timezone. Formats: YYYY-MM-DDTHH:mm:ss or YYYY-MM-DDTHH:mm:ss+07:00 (optional)
        due_date: New due date in Asia/Bangkok timezone. Formats: YYYY-MM-DDTHH:mm:ss or YYYY-MM-DDTHH:mm:ss+07:00 (optional)
        priority: New priority level (0: None, 1: Low, 3: Medium, 5: High) (optional)
    """
    if not ticktick:
        if not initialize_client():
            return "Failed to initialize TickTick client. Please check your API credentials."
    
    # Validate priority if provided
    if priority is not None and priority not in [0, 1, 3, 5]:
        return "Invalid priority. Must be 0 (None), 1 (Low), 3 (Medium), or 5 (High)."
    
    try:
        # Validate and normalize dates if provided
        normalized_start_date = None
        normalized_due_date = None
        
        if start_date:
            validation_error = validate_datetime_string(start_date, "start_date")
            if validation_error:
                return validation_error
            normalized_start_date = normalize_datetime_for_user(start_date)
        
        if due_date:
            validation_error = validate_datetime_string(due_date, "due_date")
            if validation_error:
                return validation_error
            normalized_due_date = normalize_datetime_for_user(due_date)
        
        task = ticktick.update_task(
           task_id=task_id,
            project_id=project_id,
            title=title,
            content=content,
            start_date=normalized_start_date,
            due_date=normalized_due_date,
            priority=priority
        )
        
        if 'error' in task:
            return f"Error updating task: {task['error']}"
        
        return f"Task updated successfully:\n\n" + format_task(task)
    except Exception as e:
        logger.error(f"Error in update_task: {e}")
        return f"Error updating task: {str(e)}"

@mcp.tool()
async def complete_task(project_id: str, task_id: str) -> str:
    """
    Mark a task as complete.
    
    Args:
        project_id: ID of the project
        task_id: ID of the task
    """
    if not ticktick:
        if not initialize_client():
            return "Failed to initialize TickTick client. Please check your API credentials."
    
    try:
        result = ticktick.complete_task(project_id, task_id)
        if 'error' in result:
            return f"Error completing task: {result['error']}"
        
        return f"Task {task_id} marked as complete."
    except Exception as e:
        logger.error(f"Error in complete_task: {e}")
        return f"Error completing task: {str(e)}"

@mcp.tool()
async def delete_task(project_id: str, task_id: str) -> str:
    """
    Delete a task.
    
    Args:
        project_id: ID of the project
        task_id: ID of the task
    """
    if not ticktick:
        if not initialize_client():
            return "Failed to initialize TickTick client. Please check your API credentials."
    
    try:
        result = ticktick.delete_task(project_id, task_id)
        if 'error' in result:
            return f"Error deleting task: {result['error']}"
        
        return f"Task {task_id} deleted successfully."
    except Exception as e:
        logger.error(f"Error in delete_task: {e}")
        return f"Error deleting task: {str(e)}"

@mcp.tool()
async def create_project(
    name: str,
    color: str = "#F18181",
    view_mode: str = "list"
) -> str:
    """
    Create a new project in TickTick.
    
    Args:
        name: Project name
        color: Color code (hex format) (optional)
        view_mode: View mode - one of list, kanban, or timeline (optional)
    """
    if not ticktick:
        if not initialize_client():
            return "Failed to initialize TickTick client. Please check your API credentials."
    
    # Validate view_mode
    if view_mode not in ["list", "kanban", "timeline"]:
        return "Invalid view_mode. Must be one of: list, kanban, timeline."
    
    try:
        project = ticktick.create_project(
            name=name,
            color=color,
            view_mode=view_mode
        )
        
        if 'error' in project:
            return f"Error creating project: {project['error']}"
        
        return f"Project created successfully:\n\n" + format_project(project)
    except Exception as e:
        logger.error(f"Error in create_project: {e}")
        return f"Error creating project: {str(e)}"

@mcp.tool()
async def delete_project(project_id: str) -> str:
    """
    Delete a project.
    
    Args:
        project_id: ID of the project
    """
    if not ticktick:
        if not initialize_client():
            return "Failed to initialize TickTick client. Please check your API credentials."
    
    try:
        result = ticktick.delete_project(project_id)
        if 'error' in result:
            return f"Error deleting project: {result['error']}"
        
        return f"Project {project_id} deleted successfully."
    except Exception as e:
        logger.error(f"Error in delete_project: {e}")
        return f"Error deleting project: {str(e)}"

def main():
    """Main entry point for the MCP server."""
    # Initialize the TickTick client
    if not initialize_client():
        logger.error("Failed to initialize TickTick client. Please check your API credentials.")
        return
    
    # Run the server
    mcp.run(transport='stdio')

if __name__ == "__main__":
    main()
