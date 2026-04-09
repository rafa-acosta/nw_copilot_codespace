"""
Example 9: Launch the local RAG copilot GUI.

This starts a self-contained local web server with:
- document upload and indexing
- retrieval controls
- chat-style querying with grounded source cards
"""

from __future__ import annotations

from pathlib import Path
import sys

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from copilot_ui import run_server


if __name__ == "__main__":
    run_server(host="127.0.0.1", port=8765, open_browser=False)
