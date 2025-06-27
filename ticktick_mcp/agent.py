import asyncio
import json
from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, StdioServerParameters


async def run_agent() -> str:
    
    ticktick =MCPToolset(
        connection_params=StdioServerParameters(
        command='/opt/homebrew/bin/uv',
        args=["run", "--directory",
              "/Users/luc.nguyen/workspaces/github.com/minhluc-info/ticktick-mcp/ticktick_mcp",
              "-m", "ticktick_mcp.cli", "run"],
        
        ),
        ) 
    root_agent = LlmAgent(
        name="TickTick Agent",
        description="An agent that interacts with TickTick using MCP tools.",
        model="gemini-2.0-flash",
        tools=[ticktick],
    )
    return root_agent


root_agent = run_agent()