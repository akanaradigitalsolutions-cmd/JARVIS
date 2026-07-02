"""Point Jarvis at a throwaway workspace before any jarvis module is
imported, so tests never touch the real ~/Jarvis/workspace.
"""

import os
import tempfile

os.environ.setdefault("JARVIS_WORKSPACE", tempfile.mkdtemp(prefix="jarvis-test-workspace-"))
