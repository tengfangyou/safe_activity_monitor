#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
safe_activity_monitor_txt.py

目的：
- 在「有人操作電腦」時，定期把前景視窗標題、程序名稱、PID 與時間，寫入純文字 .txt（記事本可讀）
- 不記錄按鍵內容（不是 keylogger）
- 每日自動分檔 logs/activity_YYYY-MM-DD.txt

依賴：
  pip install psutil pynput pywinctl
  (pywinctl 可選；若抓不到前景視窗會寫 "Unknown Window")

Windows/macOS/Linux（X11）皆可運作；Wayland 抓前景視窗可能受限。
"""

import os
import sys
import time
import psutil
import argparse
from pathlib import Path
from datetime import datetime
from threading import Event, Lock, Thread

# 使用者活動偵測（不記錄按鍵內容）
from pynput import mouse, keyboard

# （可選）前景視窗
try:
    import pywinctl as pwc
except Exception:
    pwc = None

DEFAULT_POLL = 5        # 有人在操作時，每 N 秒寫一筆
DEFAULT_IDLE = 10       # N 秒無輸入 => 視為 idle（不寫 active 資訊）
LOG_DIR_DEFAULT = "logs"

stop_event = Event()
last_input_ts = time.time()
last_input_lock = Lock()

def mark_input():
    global last_input_ts
    with last_input_lock:
        last_input_ts = time.time()

def is_active(idle_seconds: int) -> bool:
    with last_input_lock:
        return (time.time() - last_input_ts) <= idle_seconds

def get_active_window():
    """回傳 (title, pid, pname)。若無法取得，title='Unknown Window'、pid/pname 可能為 None。"""
    title = "Unknown Window"
    pid = None
    pname = None

    if pwc is None:
        return title, pid, pname

    try:
        w = pwc.getActiveWindow()
        if w:
            title = w.title or "Untitled"
            if hasattr(w, "getPid"):
                pid = w.getPid()
                try:
                    if pid:
                        pname = psutil.Process(pid).name()
                except Exception:
                    pass
    except Exception:
        pass
    return title, pid, pname

def daily_log_path(base_dir: Path) -> Path:
    day = datetime.now().strftime("%Y-%m-%d")
    return base_dir / f"activity_{day}.txt"

def write_line(log_file: Path, line: str):
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def input_listeners():
    # 只標記「有活動」，不記錄按什麼
    ml = mouse.Listener(on_move=lambda x, y: mark_input(),
                        on_click=lambda x, y, b, p: mark_input(),
                        on_scroll=lambda x, y, dx, dy: mark_input())
    kl = keyboard.Listener(on_press=lambda k: mark_input())
    ml.daemon = True; kl.daemon = True
    ml.start(); kl.start()
    return ml, kl

def process_diff_loop(base_dir: Path):
    """
    簡單偵測程序啟/閉並寫入文字檔。每 3 秒檢查一次。
    """
    seen = {}
    while not stop_event.is_set():
        current = {}
        for p in psutil.process_iter(["pid", "name"]):
            try:
                current[p.info["pid"]] = p.info["name"]
            except Exception:
                continue

        new_pids = set(current) - set(seen)
        dead_pids = set(seen) - set(current)

        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logfile = daily_log_path(base_dir)

        for pid in sorted(new_pids):
            line = f"[{ts}] PROCESS_START pid={pid} name={current.get(pid, '')}"
            write_line(logfile, line)

        for pid in sorted(dead_pids):
            line = f"[{ts}] PROCESS_END   pid={pid} name={seen.get(pid, '')}"
            write_line(logfile, line)

        seen = current
        time.sleep(3)

def main():
    parser = argparse.ArgumentParser(description="Safe Activity Monitor (txt logs). Not a keylogger.")
    parser.add_argument("--dir", default=LOG_DIR_DEFAULT, help="log 目錄（預設 logs）")
    parser.add_argument("--poll", type=int, default=DEFAULT_POLL, help="active 狀態下每幾秒寫一筆（預設 5）")
    parser.add_argument("--idle", type=int, default=DEFAULT_IDLE, help="視為 idle 的秒數（預設 10）")
    args = parser.parse_args()

    base_dir = Path(args.dir).expanduser().resolve()
    print(f"Log directory: {base_dir}")
    if pwc is None:
        print("提示：未載入 pywinctl，無法取得前景視窗標題（將記錄 Unknown Window）。")

    # 啟動輸入偵測
    input_listeners()

    # 程序啟閉背景偵測
    t = Thread(target=process_diff_loop, args=(base_dir,), daemon=True)
    t.start()

    try:
        while not stop_event.is_set():
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logfile = daily_log_path(base_dir)

            if is_active(args.idle):
                title, pid, pname = get_active_window()
                # 為了記事本閱讀性，做簡潔單行
                line = f"[{ts}] ACTIVE pid={pid or ''} name={pname or ''} window={title}"
                write_line(logfile, line)
            else:
                # 你也可以註解掉 idle 行，減少噪音
                write_line(logfile, f"[{ts}] IDLE")

            # 輕量 sleep
            for _ in range(int(args.poll * 10)):
                if stop_event.is_set():
                    break
                time.sleep(0.1)

    except KeyboardInterrupt:
        print("Stop requested, exiting…")

if __name__ == "__main__":
    main()
