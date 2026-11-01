import os

# A real desktop run must retain Qt's native platform selection.
# Only the automated test process opts into headless rendering.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
