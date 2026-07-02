"""Point Jarvis at a throwaway workspace before any jarvis module is
imported, so tests never touch the real ~/Jarvis/workspace or need a real
API key just to exercise the skills.
"""

import os
import tempfile

os.environ.setdefault("JARVIS_WORKSPACE", tempfile.mkdtemp(prefix="jarvis-test-workspace-"))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-not-used")
