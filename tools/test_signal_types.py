#!/usr/bin/env python3
"""Test Qt signals carry int terminal_state, not bool."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import pyqtSignal, QObject
from model_download_task import SUCCEEDED, FAILED, CANCELLED

app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)

errors = 0

class Receiver(QObject):
    def __init__(self):
        super().__init__()
        self.received = []
    def on_done(self, model_id, terminal_state, error, attempt):
        self.received.append((model_id, terminal_state, error, attempt, type(terminal_state).__name__))

class Sender(QObject):
    done = pyqtSignal(str, int, object, int)
    def send(self, mid, ts, err, att):
        self.done.emit(mid, ts, err, att)

# Test 1: SUCCEEDED stays as int 3
r1 = Receiver()
s1 = Sender()
s1.done.connect(r1.on_done)
s1.send("tiny", SUCCEEDED, None, 1)
assert len(r1.received) == 1
ts = r1.received[0][1]
assert ts == 3 and type(ts).__name__ == 'int', f"SUCCEEDED: expected int 3, got {ts} ({type(ts).__name__})"
print("PASS 1: SUCCEEDED = int 3")

# Test 2: FAILED stays as int 4
r2 = Receiver()
s2 = Sender()
s2.done.connect(r2.on_done)
s2.send("small", FAILED, "timeout", 3)
ts2 = r2.received[0][1]
assert ts2 == 4 and type(ts2).__name__ == 'int', f"FAILED: expected int 4, got {ts2}"
print("PASS 2: FAILED = int 4")

# Test 3: CANCELLED stays as int 5
r3 = Receiver()
s3 = Sender()
s3.done.connect(r3.on_done)
s3.send("tiny", CANCELLED, "Cancelled", 2)
ts3 = r3.received[0][1]
assert ts3 == 5 and type(ts3).__name__ == 'int', f"CANCELLED: expected int 5, got {ts3}"
print("PASS 3: CANCELLED = int 5")

print("ALL 3 PASSED")
