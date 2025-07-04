#!/usr/bin/env python3
"""
Command-line interface for TickTick MCP server.
"""

import sys
import os
import argparse
import logging
from pathlib import Path
from dotenv import load_dotenv

from .src.server import main as server_main
from .authenticate import main as auth_main


def check_auth_setup() -> bool:
    """Check if authentication is set up properly."""
    # First check if environment variables are directly set
    if os.getenv("TICKTICK_ACCESS_TOKEN"):
        return True
        
    # If not, check if .env file exists with the required credentials
    env_path = Path('.env')
    if not env_path.exists():
        return False
    
    # Check if the .env file contains the access token
    with open(env_path, 'r') as f:
        content = f.read()
        return 'TICKTICK_ACCESS_TOKEN' in content

def main():
    """Entry point for the CLI."""
    parser = argparse.ArgumentParser(description="TickTick MCP Server")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # 'run' command for running the server
    run_parser = subparsers.add_parser("run", help="Run the TickTick MCP server")
    run_parser.add_argument(
        "--debug", 
        action="store_true", 
        help="Enable debug logging"
    )
    run_parser.add_argument(
        "--transport", 
        default="stdio", 
        choices=["stdio", "sse"], 
        help="Transport type (stdio or sse - use sse for Docker environments)"
    )
    run_parser.add_argument(
        "--host",
        default="0.0.0.0", 
        help="Host to bind to when using SSE transport (default: 0.0.0.0)"
    )
    run_parser.add_argument(
        "--port",
        type=int,
        default=3434, 
        help="Port to use when using SSE transport (default: 3434)"
    )
    
    # 'auth' command for authentication
    auth_parser = subparsers.add_parser("auth", help="Authenticate with TickTick")
    
    args = parser.parse_args()
    
    # If no command specified, default to 'run'
    if not args.command:
        args.command = "run"
    
    # For the run command, check if auth is set up
    if args.command == "run" and not check_auth_setup():
        print("""
╔════════════════════════════════════════════════╗
║      TickTick MCP Server - Authentication      ║
╚════════════════════════════════════════════════╝

Authentication setup required!
You need to set up TickTick authentication before running the server.

Would you like to set up authentication now? (y/n): """, end="")
        choice = input().lower().strip()
        if choice == 'y':
            # Run the auth flow
            auth_result = auth_main()
            if auth_result != 0:
                # Auth failed, exit
                sys.exit(auth_result)
        else:
            print("""
Authentication is required to use the TickTick MCP server.
Run 'uv run -m ticktick_mcp.cli auth' to set up authentication later.
            """)
            sys.exit(1)
    
    # Run the appropriate command
    if args.command == "auth":
        # Run authentication flow
        sys.exit(auth_main())
    elif args.command == "run":
        # Configure logging based on debug flag
        log_level = logging.DEBUG if args.debug else logging.INFO
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        
        # Start the server
        try:
            # Pass transport configuration to the server
            server_main(
                transport=args.transport,
                host=args.host,
                port=args.port
            )
        except KeyboardInterrupt:
            print("Server stopped by user", file=sys.stderr)
            sys.exit(0)
        except Exception as e:
            print(f"Error starting server: {e}", file=sys.stderr)
            sys.exit(1)

if __name__ == "__main__":
    main()