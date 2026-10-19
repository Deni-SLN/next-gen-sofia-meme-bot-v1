#!/usr/bin/env python
"""
Standalone runner for SOFIA Intelligence MCP Server.
Usage:
  # STDIO Mode (Standard for Hermes Agent, OpenClaw, Claude Desktop, Cursor, Antigravity)
  python run_mcp.py

  # SSE Mode (Networked / Remote Agents)
  python run_mcp.py --sse --port 8001
"""

import os
import sys

# Ensure services/api is on the python module search path
root_dir = os.path.dirname(os.path.abspath(__file__))
api_dir = os.path.join(root_dir, "services", "api")
if os.path.isdir(api_dir) and api_dir not in sys.path:
    sys.path.insert(0, api_dir)

from app.mcp_server import main

if __name__ == "__main__":
    main()
