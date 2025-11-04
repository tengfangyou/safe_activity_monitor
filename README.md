## Safe Activity Monitor (TXT)

> A **privacy-respecting** helper that logs *when the machine is being actively used* and *which foreground app/window is open*, to plain text files readable by Notepad. **No keystrokes are recorded.**

### Features
- Detects user activity (mouse/keyboard events) without recording key content.
- While active, snapshots every `N` seconds: **PID**, **process name**, **active window title**.
- Logs are simple `.txt`, one line per event; auto-rotated **daily** as `logs/activity_YYYY-MM-DD.txt`.
- Also notes **process start/terminate** events.

### Install
```bash
pip install psutil pynput pywinctl
