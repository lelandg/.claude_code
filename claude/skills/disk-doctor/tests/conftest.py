import os
import sys

# Put the skill's bin/ directory on sys.path so tests can import disk_doctor_core.
BIN = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bin")
if BIN not in sys.path:
    sys.path.insert(0, BIN)
