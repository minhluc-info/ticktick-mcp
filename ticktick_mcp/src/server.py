import asyncio
import json
import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional
import time
import re

from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

from .ticktick_client import TickTickClient

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastMCP server
mcp = FastMCP("ticktick")

# Create TickTick client
ticktick = None

# Bangkok timezone for proper date handling
BANGKOK_TZ = timezone(timedelta(hours=7))

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

# Helper function to convert date to Bangkok timezone
def to_bangkok_time(date_str: str) -> str:
    """Convert date string to Bangkok timezone if no timezone specified."""
    if not date_str:
        return date_str
    
    # If no timezone info, assume Bangkok time
    if not re.search(r'[+-]\d{2}:?\d{2}|Z$', date_str):
        # Add Bangkok timezone (+07:00)
        if 'T' in date_str:
            return date_str + '+07:00'
        else:
            return date_str + 'T00:00:00+07:00'
    
    return date_str

# Rate limiting helper
def rate_limit(calls_per_second: int = 10):
    """Simple rate limiting decorator."""
    last_called = [0.0]
    min_interval = 1.0 / calls_per_second
    
    def decorator(func):
        def wrapper(*args, **kwargs):
            elapsed = time.time() - last_called[0]
            left_to_wait = min_interval - elapsed
            if left_to_wait > 0:
                time.sleep(left_to_wait)
            ret = func(*args, **kwargs)
            last_called[0] = time.time()
            return ret
        return wrapper
    return decorator

# Format a task object from TickTick for better display
def format_task(task: Dict) -> str:
    """Format a task into a human-readable string."""
    formatted = f"ID: {task.get('id', 'No ID')}\n"
    formatted += f"Title: {task.get('title', 'No title')}\n"
    
    # Add project ID
    formatted += f"Project ID: {task.get('projectId', 'None')}\n"
    
    # Add dates if available
    if task.get('startDate'):
        formatted += f"Start Date: {task.get('startDate')}\n"
    if task.get('dueDate'):
        formatted += f"Due Date: {task.get('dueDate')}\n"
    
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
            status = "✓" if item.get('status') == 1 else "○"
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
    Create a new task in TickTick with improved timezone support.
    
    Args:
        title: Task title
        project_id: ID of the project to add the task to
        content: Task description/content (optional)
        start_date: Start date in ISO format or 'YYYY-MM-DD' (Bangkok timezone) (optional)
        due_date: Due date in ISO format or 'YYYY-MM-DD' (Bangkok timezone) (optional)
        priority: Priority level (0: None, 1: Low, 3: Medium, 5: High) (optional)
    """
    if not ticktick:
        if not initialize_client():
            return "Failed to initialize TickTick client. Please check your API credentials."
    
    # Validate priority
    if priority not in [0, 1, 3, 5]:
        return "Invalid priority. Must be 0 (None), 1 (Low), 3 (Medium), or 5 (High)."
    
    try:
        # Convert dates to Bangkok timezone if needed
        if start_date:
            start_date = to_bangkok_time(start_date)
        if due_date:
            due_date = to_bangkok_time(due_date)
            
        # Validate dates if provided
        for date_str, date_name in [(start_date, "start_date"), (due_date, "due_date")]:
            if date_str:
                try:
                    # Try to parse the date to validate it
                    datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                except ValueError:
                    return f"Invalid {date_name} format. Use ISO format: YYYY-MM-DDTHH:mm:ss+07:00 or YYYY-MM-DD"
        
        task = ticktick.create_task(
            title=title,
            project_id=project_id,
            content=content,
            start_date=start_date,
            due_date=due_date,
            priority=priority
        )
        
        if 'error' in task:
            return f"Error creating task: {task['error']}"
        
        return f"Task created successfully:\n\n" + format_task(task)
    except Exception as e:
        logger.error(f"Error in create_task: {e}")
        return f"Error creating task: {str(e)}"

# NEW: Batch create multiple tasks
@mcp.tool()
async def create_multiple_tasks(tasks_data: str) -> str:
    """
    Create multiple tasks at once. Much faster than creating them one by one.
    
    Args:
        tasks_data: JSON string containing list of task objects. Each task should have:
                   {
                     "title": "Task title",
                     "project_id": "project_id", 
                     "content": "description (optional)",
                     "due_date": "YYYY-MM-DD or ISO format (optional)",
                     "priority": 0-5 (optional)
                   }
    
    Example: '[{"title": "Task 1", "project_id": "123"}, {"title": "Task 2", "project_id": "123", "priority": 5}]'
    """
    if not ticktick:
        if not initialize_client():
            return "Failed to initialize TickTick client. Please check your API credentials."
    
    try:
        # Parse JSON data
        tasks = json.loads(tasks_data)
        if not isinstance(tasks, list):
            return "Error: tasks_data must be a JSON array of task objects."
        
        if len(tasks) > 50:  # Reasonable limit
            return "Error: Maximum 50 tasks allowed per batch operation."
        
        created_tasks = []
        failed_tasks = []
        
        for i, task_data in enumerate(tasks):
            try:
                # Validate required fields
                if 'title' not in task_data or 'project_id' not in task_data:
                    failed_tasks.append(f"Task {i+1}: Missing title or project_id")
                    continue
                
                # Extract and validate data
                title = task_data['title']
                project_id = task_data['project_id'] 
                content = task_data.get('content')
                start_date = task_data.get('start_date')
                due_date = task_data.get('due_date')
                priority = task_data.get('priority', 0)
                
                # Convert dates to Bangkok timezone
                if start_date:
                    start_date = to_bangkok_time(start_date)
                if due_date:
                    due_date = to_bangkok_time(due_date)
                
                # Create task with rate limiting
                task = ticktick.create_task(
                    title=title,
                    project_id=project_id,
                    content=content,
                    start_date=start_date,
                    due_date=due_date,
                    priority=priority
                )
                
                if 'error' in task:
                    failed_tasks.append(f"Task '{title}': {task['error']}")
                else:
                    created_tasks.append(task)
                    
                # Brief pause to avoid rate limits
                await asyncio.sleep(0.1)
                
            except Exception as e:
                failed_tasks.append(f"Task {i+1}: {str(e)}")
        
        # Format results
        result = f"Batch task creation completed:\n"
        result += f"✅ Successfully created: {len(created_tasks)} tasks\n"
        
        if failed_tasks:
            result += f"❌ Failed: {len(failed_tasks)} tasks\n\nErrors:\n"
            for error in failed_tasks:
                result += f"- {error}\n"
        
        if created_tasks:
            result += f"\nCreated tasks:\n"
            for i, task in enumerate(created_tasks[:5], 1):  # Show first 5
                result += f"{i}. {task.get('title', 'No title')} (ID: {task.get('id')})\n"
            
            if len(created_tasks) > 5:
                result += f"... and {len(created_tasks) - 5} more tasks\n"
        
        return result
        
    except json.JSONDecodeError:
        return "Error: Invalid JSON format in tasks_data. Please provide a valid JSON array."
    except Exception as e:
        logger.error(f"Error in create_multiple_tasks: {e}")
        return f"Error creating multiple tasks: {str(e)}"

# NEW: Search tasks by text
@mcp.tool()
async def search_tasks(
    query: str, 
    project_id: str = None,
    include_completed: bool = False
) -> str:
    """
    Search for tasks by title or content text.
    
    Args:
        query: Text to search for in task titles and content
        project_id: Optional project ID to limit search scope
        include_completed: Whether to include completed tasks (default: False)
    """
    if not ticktick:
        if not initialize_client():
            return "Failed to initialize TickTick client. Please check your API credentials."
    
    try:
        # Get all projects or specific project
        if project_id:
            project_data = ticktick.get_project_with_data(project_id)
            if 'error' in project_data:
                return f"Error fetching project: {project_data['error']}"
            all_tasks = project_data.get('tasks', [])
            search_scope = f"project '{project_data.get('project', {}).get('name', project_id)}'"
        else:
            # Get tasks from all projects
            projects = ticktick.get_projects()
            if 'error' in projects:
                return f"Error fetching projects: {projects['error']}"
            
            all_tasks = []
            for project in projects:
                project_data = ticktick.get_project_with_data(project['id'])
                if 'error' not in project_data:
                    all_tasks.extend(project_data.get('tasks', []))
            search_scope = "all projects"
        
        # Filter tasks based on search criteria
        matching_tasks = []
        query_lower = query.lower()
        
        for task in all_tasks:
            # Skip completed tasks unless requested
            if not include_completed and task.get('status') == 2:
                continue
                
            # Search in title and content
            title = task.get('title', '').lower()
            content = task.get('content', '').lower()
            
            if query_lower in title or query_lower in content:
                matching_tasks.append(task)
        
        # Format results
        if not matching_tasks:
            return f"No tasks found matching '{query}' in {search_scope}."
        
        result = f"Found {len(matching_tasks)} tasks matching '{query}' in {search_scope}:\n\n"
        
        for i, task in enumerate(matching_tasks[:10], 1):  # Limit to first 10
            result += f"Task {i}:\n" + format_task(task) + "\n"
        
        if len(matching_tasks) > 10:
            result += f"... and {len(matching_tasks) - 10} more matching tasks\n"
        
        return result
        
    except Exception as e:
        logger.error(f"Error in search_tasks: {e}")
        return f"Error searching tasks: {str(e)}"

# NEW: Get overdue tasks
@mcp.tool()
async def get_overdue_tasks(project_id: str = None) -> str:
    """
    Get all overdue tasks (tasks with due dates in the past).
    
    Args:
        project_id: Optional project ID to limit scope (default: all projects)
    """
    if not ticktick:
        if not initialize_client():
            return "Failed to initialize TickTick client. Please check your API credentials."
    
    try:
        # Get current time in Bangkok timezone
        now = datetime.now(BANGKOK_TZ)
        
        # Get tasks
        if project_id:
            project_data = ticktick.get_project_with_data(project_id)
            if 'error' in project_data:
                return f"Error fetching project: {project_data['error']}"
            all_tasks = project_data.get('tasks', [])
            scope = f"project '{project_data.get('project', {}).get('name', project_id)}'"
        else:
            # Get from all projects  
            projects = ticktick.get_projects()
            if 'error' in projects:
                return f"Error fetching projects: {projects['error']}"
            
            all_tasks = []
            for project in projects:
                project_data = ticktick.get_project_with_data(project['id'])
                if 'error' not in project_data:
                    all_tasks.extend(project_data.get('tasks', []))
            scope = "all projects"
        
        # Find overdue tasks
        overdue_tasks = []
        for task in all_tasks:
            # Skip completed tasks
            if task.get('status') == 2:
                continue
                
            due_date_str = task.get('dueDate')
            if due_date_str:
                try:
                    # Parse due date
                    due_date = datetime.fromisoformat(due_date_str.replace('Z', '+00:00'))
                    
                    # Convert to Bangkok timezone for comparison
                    if due_date.tzinfo is None:
                        due_date = due_date.replace(tzinfo=BANGKOK_TZ)
                    else:
                        due_date = due_date.astimezone(BANGKOK_TZ)
                    
                    # Check if overdue
                    if due_date < now:
                        overdue_tasks.append((task, due_date))
                        
                except (ValueError, TypeError):
                    continue  # Skip invalid dates
        
        # Sort by due date (most overdue first)
        overdue_tasks.sort(key=lambda x: x[1])
        
        if not overdue_tasks:
            return f"🎉 No overdue tasks found in {scope}!"
        
        result = f"⚠️ Found {len(overdue_tasks)} overdue tasks in {scope}:\n\n"
        
        for i, (task, due_date) in enumerate(overdue_tasks, 1):
            days_overdue = (now - due_date).days
            result += f"Task {i} (⏰ {days_overdue} days overdue):\n" + format_task(task) + "\n"
        
        return result
        
    except Exception as e:
        logger.error(f"Error in get_overdue_tasks: {e}")
        return f"Error getting overdue tasks: {str(e)}"

# NEW: Get today's tasks
@mcp.tool()
async def get_today_tasks(project_id: str = None) -> str:
    """
    Get all tasks due today (Bangkok timezone).
    
    Args:
        project_id: Optional project ID to limit scope (default: all projects)
    """
    if not ticktick:
        if not initialize_client():
            return "Failed to initialize TickTick client. Please check your API credentials."
    
    try:
        # Get current date in Bangkok timezone
        today = datetime.now(BANGKOK_TZ).date()
        
        # Get tasks
        if project_id:
            project_data = ticktick.get_project_with_data(project_id)
            if 'error' in project_data:
                return f"Error fetching project: {project_data['error']}"
            all_tasks = project_data.get('tasks', [])
            scope = f"project '{project_data.get('project', {}).get('name', project_id)}'"
        else:
            # Get from all projects
            projects = ticktick.get_projects()
            if 'error' in projects:
                return f"Error fetching projects: {projects['error']}"
            
            all_tasks = []
            for project in projects:
                project_data = ticktick.get_project_with_data(project['id'])
                if 'error' not in project_data:
                    all_tasks.extend(project_data.get('tasks', []))
            scope = "all projects"
        
        # Find today's tasks
        today_tasks = []
        for task in all_tasks:
            # Skip completed tasks
            if task.get('status') == 2:
                continue
                
            due_date_str = task.get('dueDate')
            if due_date_str:
                try:
                    # Parse due date
                    due_date = datetime.fromisoformat(due_date_str.replace('Z', '+00:00'))
                    
                    # Convert to Bangkok timezone
                    if due_date.tzinfo is None:
                        due_date = due_date.replace(tzinfo=BANGKOK_TZ)
                    else:
                        due_date = due_date.astimezone(BANGKOK_TZ)
                    
                    # Check if due today
                    if due_date.date() == today:
                        today_tasks.append(task)
                        
                except (ValueError, TypeError):
                    continue  # Skip invalid dates
        
        if not today_tasks:
            return f"📅 No tasks due today in {scope}."
        
        result = f"📅 Found {len(today_tasks)} tasks due today in {scope}:\n\n"
        
        for i, task in enumerate(today_tasks, 1):
            result += f"Task {i}:\n" + format_task(task) + "\n"
        
        return result
        
    except Exception as e:
        logger.error(f"Error in get_today_tasks: {e}")
        return f"Error getting today's tasks: {str(e)}"

# NEW: Get project statistics
@mcp.tool() 
async def get_project_stats(project_id: str) -> str:
    """
    Get detailed statistics for a project.
    
    Args:
        project_id: ID of the project to analyze
    """
    if not ticktick:
        if not initialize_client():
            return "Failed to initialize TickTick client. Please check your API credentials."
    
    try:
        project_data = ticktick.get_project_with_data(project_id)
        if 'error' in project_data:
            return f"Error fetching project: {project_data['error']}"
        
        project = project_data.get('project', {})
        tasks = project_data.get('tasks', [])
        
        if not tasks:
            return f"📊 Project '{project.get('name', project_id)}' has no tasks."
        
        # Calculate statistics
        total_tasks = len(tasks)
        completed_tasks = len([t for t in tasks if t.get('status') == 2])
        active_tasks = total_tasks - completed_tasks
        
        # Priority breakdown
        priority_counts = {0: 0, 1: 0, 3: 0, 5: 0}  # None, Low, Medium, High
        for task in tasks:
            if task.get('status') != 2:  # Only active tasks
                priority = task.get('priority', 0)
                if priority in priority_counts:
                    priority_counts[priority] += 1
        
        # Overdue count
        now = datetime.now(BANGKOK_TZ)
        overdue_count = 0
        for task in tasks:
            if task.get('status') == 2:  # Skip completed
                continue
            due_date_str = task.get('dueDate')
            if due_date_str:
                try:
                    due_date = datetime.fromisoformat(due_date_str.replace('Z', '+00:00'))
                    if due_date.tzinfo is None:
                        due_date = due_date.replace(tzinfo=BANGKOK_TZ)
                    else:
                        due_date = due_date.astimezone(BANGKOK_TZ)
                    if due_date < now:
                        overdue_count += 1
                except:
                    continue
        
        # Completion rate
        completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
        
        # Format results
        result = f"📊 Statistics for project '{project.get('name', project_id)}':\n\n"
        result += f"📈 **Overall Progress:**\n"
        result += f"   Total tasks: {total_tasks}\n"
        result += f"   Completed: {completed_tasks} ({completion_rate:.1f}%)\n"
        result += f"   Active: {active_tasks}\n"
        result += f"   Overdue: {overdue_count}\n\n"
        
        result += f"🎯 **Active Tasks by Priority:**\n"
        result += f"   🔴 High (5): {priority_counts[5]}\n"
        result += f"   🟡 Medium (3): {priority_counts[3]}\n"
        result += f"   🔵 Low (1): {priority_counts[1]}\n"
        result += f"   ⚪ None (0): {priority_counts[0]}\n\n"
        
        # Recommendations
        if overdue_count > 0:
            result += f"⚠️ **Recommendations:**\n"
            result += f"   - You have {overdue_count} overdue tasks. Consider reviewing deadlines.\n"
        
        if priority_counts[5] > 5:
            result += f"   - {priority_counts[5]} high-priority tasks. Focus on these first.\n"
        
        if completion_rate < 50:
            result += f"   - Low completion rate ({completion_rate:.1f}%). Consider breaking down large tasks.\n"
        
        return result
        
    except Exception as e:
        logger.error(f"Error in get_project_stats: {e}")
        return f"Error getting project statistics: {str(e)}"

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
    Update an existing task in TickTick with improved timezone support.
    
    Args:
        task_id: ID of the task to update
        project_id: ID of the project the task belongs to
        title: New task title (optional)
        content: New task description/content (optional)
        start_date: New start date in ISO format or 'YYYY-MM-DD' (Bangkok timezone) (optional)
        due_date: New due date in ISO format or 'YYYY-MM-DD' (Bangkok timezone) (optional)
        priority: New priority level (0: None, 1: Low, 3: Medium, 5: High) (optional)
    """
    if not ticktick:
        if not initialize_client():
            return "Failed to initialize TickTick client. Please check your API credentials."
    
    # Validate priority if provided
    if priority is not None and priority not in [0, 1, 3, 5]:
        return "Invalid priority. Must be 0 (None), 1 (Low), 3 (Medium), or 5 (High)."
    
    try:
        # Convert dates to Bangkok timezone if needed
        if start_date:
            start_date = to_bangkok_time(start_date)
        if due_date:
            due_date = to_bangkok_time(due_date)
            
        # Validate dates if provided
        for date_str, date_name in [(start_date, "start_date"), (due_date, "due_date")]:
            if date_str:
                try:
                    # Try to parse the date to validate it
                    datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                except ValueError:
                    return f"Invalid {date_name} format. Use ISO format: YYYY-MM-DDTHH:mm:ss+07:00 or YYYY-MM-DD"
        
        task = ticktick.update_task(
           task_id=task_id,
            project_id=project_id,
            title=title,
            content=content,
            start_date=start_date,
            due_date=due_date,
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
