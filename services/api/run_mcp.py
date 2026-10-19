#!/usr/bin/env python
"""
Runner for SOFIA Intelligence MCP Server from within services/api.
"""

import os
import sys

cur_dir = os.path.dirname(os.path.abspath(__file__))
if cur_dir not in sys.path:
    sys.path.insert(0, cur_dir)

from app.mcp_server import main

if __name__ == "__main__":
    main()
