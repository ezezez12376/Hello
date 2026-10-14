"""
YouTube Shorts Auto Viewer — Multi-Tab Edition (Optimized)
tkinter GUI + thread pool + shared URL queue
Optimized for 4GB RAM — Python 3.14 compatible
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import threading
import subprocess
import sys
import os
import time
import random
import json
import queue
import re
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional

# ── Settings ───────────────────────────────────────────────────────────────
def get_settings_path() -> str:
    appdata = os.environ.get("APPDATA") or os.path.expanduser("~")
    folder = os.path.join(appdata, "ShortsViewer")
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, "settings.json")

# ── Theme Constants ────────────────────────────────────────────────────────
class Theme:
    BG       = "#0a0a0f"
    BG2      = "#12121a"
    BG3      = "#1a1a2e"
    BG4      = "#22223a"
    BG_HOVER = "#2a2a44"
    ACCENT   = "#ff2d55"
    ACCENT2  = "#ff6b6b"
    ACCENT_D = "#cc2444"
    TEXT     = "#f0f0f5"
    TEXT_DIM = "#8888aa"
    TEXT_MUT = "#555570"
    GREEN    = "#34d399"
    GREEN_D  = "#059669"
    YELLOW   = "#fbbf24"
    BLUE     = "#60a5fa"
    PURPLE   = "#a78bfa"
    ORANGE   = "#fb923c"
    CYAN     = "#22d3ee"
    PINK     = "#f472b6"
    RED      = "#ef4444"
    BORDER   = "#2a2a40"
    BORDER_L = "#3a3a55"

    FONT_MONO  = ("Cascadia Code", 9)
    FONT_UI    = ("Segoe UI", 10)
    FONT_SM    = ("Segoe UI", 9)
    FONT_XS    = ("Segoe UI", 8)
    FONT_TITLE = ("Segoe UI", 20, "bold")
    FONT_SUB   = ("Segoe UI", 12, "bold")
    FONT_BTN   = ("Segoe UI", 11, "bold")

    TAB_COLORS = [
        "#ff2d55", "#60a5fa", "#34d399", "#fbbf24",
        "#a78bfa", "#fb923c", "#22d3ee", "#f472b6",
    ]

    @classmethod
    def tab_color(cls, i: int) -> str:
        return cls.TAB_COLORS[i % len(cls.TAB_COLORS)]

# ── Data Classes ───────────────────────────────────────────────────────────
@dataclass
class RunConfig:
    watch_time: float = 11.0
    loops: int = 1
    delay: float = 1.0
    headless: bool = True
    shuffle: bool = True
    proxy: str = ""
    n_tabs: int = 2

@dataclass
class Counters:
    done: int = 0
    success: int = 0
    fail: int = 0
    total: int = 0

# ── Log System ─────────────────────────────────────────────────────────────
_log_queue: queue.Queue = queue.Queue(maxsize=500)

def log(msg: str, tag: str = "info", tab_id: int = -1):
    ts = datetime.now().strftime("%H:%M:%S")
    prefix = f"[T{tab_id + 1}]" if tab_id >= 0 else "[SYS]"
    _log_queue.put((f"{ts}  {prefix}  {msg}", tag))

# ── Scraper ────────────────────────────────────────────────────────────────
def get_shorts_urls(channel_url: str, max_videos: int = 0) -> list:
    log("Fetching shorts list…")
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "--flat-playlist", "--print", "url",
        "--no-warnings", "--quiet",
        channel_url,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        lines = [l.strip() for l in result.stdout.strip().split("\n") if l.strip()]
        shorts = []
        for url in lines:
            if "/shorts/" in url:
                shorts.append(url)
            elif "watch?v=" in url:
                m = re.search(r"v=([a-zA-Z0-9_-]+)", url)
                if m:
                    shorts.append(f"https://www.youtube.com/shorts/{m.group(1)}")
        if max_videos > 0:
            shorts = shorts[:max_videos]
        log(f"Found {len(shorts)} shorts", "success")
        return shorts
    except subprocess.TimeoutExpired:
        log("Timeout fetching list.", "error")
    except Exception as e:
        log(f"Scraper error: {e}", "error")
    return []

# ── Selenium Driver ────────────────────────────────────────────────────────
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15",
]

_driver_lock = threading.Lock()

def build_driver(headless: bool = True, proxy: str = ""):
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        from webdriver_manager.chrome import ChromeDriverManager
    except ImportError:
        subprocess.run(
            [sys.executable, "-m", "pip", "install",
             "selenium", "webdriver-manager", "-q"],
            check=False,
        )
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        from webdriver_manager.chrome import ChromeDriverManager

    opts = Options()
    if headless:
        opts.add_argument("--headless=new")

    flags = [
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--disable-extensions",
        "--disable-images",
        "--blink-settings=imagesEnabled=false",
        "--disable-background-networking",
        "--disable-sync",
        "--mute-audio",
        "--window-size=480,320",
        "--js-flags=--max-old-space-size=256",
        "--disable-blink-features=AutomationControlled",
        "--disable-translate",
        "--disable-notifications",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-component-update",
        "--disable-domain-reliability",
    ]
    for f in flags:
        opts.add_argument(f)

    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    opts.add_argument(f"--user-agent={random.choice(USER_AGENTS)}")
    if proxy:
        opts.add_argument(f"--proxy-server={proxy}")

    with _driver_lock:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=opts)

    driver.execute_script(
        "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"
    )
    driver.set_page_load_timeout(20)
    return driver

def watch_video(driver, url: str, watch_time: float) -> bool:
    try:
        driver.get(url)
        time.sleep(1.2)
        try:
            video = driver.find_element("tag name", "video")
            driver.execute_script("arguments[0].play();", video)
        except Exception:
            pass
        time.sleep(watch_time + random.uniform(0.3, 1.2))
        return True
    except Exception:
        return False

# ── Helper: styled widgets ─────────────────────────────────────────────────
def _flat_entry(parent, var, width=None, **kw):
    e = tk.Entry(
        parent, textvariable=var, font=Theme.FONT_UI,
        bg=Theme.BG3, fg=Theme.TEXT, insertbackground=Theme.TEXT,
        relief="flat", bd=0, highlightthickness=1,
        highlightbackground=Theme.BORDER, highlightcolor=Theme.ACCENT,
        **kw,
    )
    if width:
        e.config(width=width)
    return e

def _flat_btn(parent, text, command, fg=Theme.TEXT, bg=Theme.BG3,
              hover_bg=Theme.BG4, font=Theme.FONT_SM, padx=12, pady=6):
    b = tk.Button(
        parent, text=text, command=command, font=font,
        bg=bg, fg=fg, activebackground=hover_bg, activeforeground=fg,
        relief="flat", bd=0, cursor="hand2", padx=padded, pady=pady,
    )
    b.bind("<Enter>", lambda e: b.config(bg=hover_bg))
    b.bind("<Leave>", lambda e: b.config(bg=bg))
    return b

def _section_label(parent, text):
    tk.Label(
        parent, text=text.upper(), font=("Segoe UI", 8, "bold"),
        fg=Theme.TEXT_MUT, bg=Theme.BG, anchor="w",
    ).pack(fill="x", pady=(14, 2))
    tk.Frame(parent, bg=Theme.BORDER, height=1).pack(fill="x", pady=(0, 8))

def _field_row(parent, label, var, tooltip=""):
    row = tk.Frame(parent, bg=Theme.BG)
    row.pack(fill="x", pady=2)
    lbl = tk.Label(
        row, text=label, font=Theme.FONT_SM, fg=Theme.TEXT_DIM,
        bg=Theme.BG, width=18, anchor="w",
    )
    lbl.pack(side="left")
    if tooltip:
        lbl.config(cursor="question_arrow")
        _add_tooltip(lbl, tooltip)
    _flat_entry(row, var).pack(
        side="left", fill="x", expand=True, ipady=4, padx=(6, 0)
    )
    return row

def _add_tooltip(widget, text):
    tip_win = None
    def show(e):
        nonlocal tip_win
        tip_win = tk.Toplevel(widget)
        tip_win.wm_overrideredirect(True)
        tip_win.wm_geometry(f"+{e.x_root + 12}+{e.y_root + 12}")
        tk.Label(
            tip_win, text=text, font=Theme.FONT_XS,
            bg=Theme.BG4, fg=Theme.TEXT, padx=8, pady=4,
            highlightthickness=1, highlightbackground=Theme.BORDER_L,
        ).pack()
    def hide(e):
        nonlocal tip_win
        if tip_win:
            tip_win.destroy()
            tip_win = None
    widget.bind("<Enter>", show)
    widget.bind("<Leave>", hide)

# ── Main Application ───────────────────────────────────────────────────────
class App(tk.Tk):
    RESTART_INTERVAL = 25  # restart driver every N videos

    def __init__(self):
        super().__init__()
        self.title("YouTube Shorts Viewer")
        self.geometry("1060x740")
        self.minsize(920, 640)
        self.configure(bg=Theme.BG)

        self._running = False
        self._stop_flag = threading.Event()
        self._urls: list = []
        self._counters = Counters()
        self._lock = threading.Lock()
        self._start_t = 0.0

        self._build_ui()
        self._poll_log()
        self._poll_stats()
        self._load_settings()

    # ────────────────────────────────────────────────────────────────────────
    #  UI CONSTRUCTION
    # ────────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        self._build_header()
        body = tk.Frame(self, bg=Theme.BG)
        body.pack(fill="both", expand=True, padx=16, pady=(8, 4))

        left = tk.Frame(body, bg=Theme.BG, width=370)
        left.pack(side="left", fill="y", padx=(0, 12))
        left.pack_propagate(False)

        right = tk.Frame(body, bg=Theme.BG)
        right.pack(side="left", fill="both", expand=True)

        self._build_left(left)
        self._build_right(right)
        self._build_footer()

    # ── Header ─────────────────────────────────────────────────────────────
    def _build_header(self):
        hdr = tk.Frame(self, bg=Theme.BG, pady=10)
        hdr.pack(fill="x", padx=20)

        # Accent bar
        tk.Frame(hdr, bg=Theme.ACCENT, width=4, height=36).pack(
            side="left", padx=(0, 12))

        info = tk.Frame(hdr, bg=Theme.BG)
        info.pack(side="left")
        tk.Label(
            info, text="Shorts Auto Viewer", font=Theme.FONT_TITLE,
            fg=Theme.TEXT, bg=Theme.BG, anchor="w",
        ).pack(anchor="w")
        tk.Label(
            info, text="Multi-tab  •  Headless  •  RAM-optimized",
            font=Theme.FONT_XS, fg=Theme.TEXT_MUT, bg=Theme.BG, anchor="w",
        ).pack(anchor="w")

        # Badge
        tk.Label(
            hdr, text="MULTI-TAB", font=("Segoe UI", 8, "bold"),
            fg=Theme.ACCENT, bg=Theme.BG3, padx=8, pady=3,
        ).pack(side="left", padx=14, pady=6)

        self._status_lbl = tk.Label(
            hdr, text="● Ready", font=Theme.FONT_SM,
            fg=Theme.GREEN, bg=Theme.BG,
        )
        self._status_lbl.pack(side="right", padx=(8, 0))

        tk.Frame(self, bg=Theme.BORDER, height=1).pack(fill="x", pady=(2, 0))

    # ── Left panel ─────────────────────────────────────────────────────────
    def _build_left(self, p):
        # Channel section
        _section_label(p, "YouTube Channel")
        row = tk.Frame(p, bg=Theme.BG)
        row.pack(fill="x")
        tk.Label(
            row, text="Channel URL", font=Theme.FONT_SM,
            fg=Theme.TEXT_DIM, bg=Theme.BG, width=18, anchor="w",
        ).pack(side="left")
        self._channel_var = tk.StringVar()
        _flat_entry(row, self._channel_var).pack(
            side="left", fill="x", expand=True, ipady=4, padx=(6, 0))

        btn_row = tk.Frame(p, bg=Theme.BG)
        btn_row.pack(fill="x", pady=(6, 0))

        self._fetch_btn = _flat_btn(
            btn_row, "↓  Fetch Shorts", self._fetch_urls,
            fg=Theme.ACCENT, font=("Segoe UI", 9, "bold"),
        )
        self._fetch_btn.pack(side="left", fill="x", expand=True)

        self._url_count = tk.Label(
            p, text="No list loaded", font=Theme.FONT_XS,
            fg=Theme.TEXT_MUT, bg=Theme.BG, anchor="w",
        )
        self._url_count.pack(anchor="w", pady=(4, 0))

        io_row = tk.Frame(p, bg=Theme.BG)
        io_row.pack(fill="x", pady=(4, 0))
        _flat_btn(io_row, "📂 Load .txt", self._load_from_file,
                  fg=Theme.TEXT_DIM).pack(side="left", fill="x", expand=True)
        _flat_btn(io_row, "💾 Save", self._save_to_file,
                  fg=Theme.TEXT_DIM).pack(side="left", padx=(4, 0),
                                           fill="x", expand=True)

        # Settings section
        _section_label(p, "Settings")
        self._watch_var = tk.StringVar(value="11")
        self._loops_var = tk.StringVar(value="1")
        self._max_var   = tk.StringVar(value="0")
        self._delay_var = tk.StringVar(value="1")
        self._proxy_var = tk.StringVar(value="")

        _field_row(p, "Watch time (s)", self._watch_var,
                   "Seconds to watch each video")
        _field_row(p, "Loops", self._loops_var,
                   "Repeat the full list N times")
        _field_row(p, "Max videos", self._max_var,
                   "0 = all videos")
        _field_row(p, "Delay (s)", self._delay_var,
                   "Pause between videos")
        _field_row(p, "Proxy", self._proxy_var,
                   "ip:port format, empty = none")

        # Tabs section
        _section_label(p, "Parallel Tabs")
        self._tabs_var = tk.IntVar(value=2)

        tab_row = tk.Frame(p, bg=Theme.BG)
        tab_row.pack(fill="x", pady=2)
        self._tab_lbl = tk.Label(
            tab_row, text="Tabs: 2", font=("Segoe UI", 11, "bold"),
            fg=Theme.ACCENT, bg=Theme.BG, width=9, anchor="w",
        )
        self._tab_lbl.pack(side="left")

        slider = tk.Scale(
            tab_row, from_=1, to=6, orient="horizontal",
            variable=self._tabs_var, bg=Theme.BG, fg=Theme.TEXT,
            troughcolor=Theme.BG3, highlightthickness=0, bd=0,
            activebackground=Theme.ACCENT, sliderrelief="flat",
            length=220, command=self._on_tab_slider,
        )
        slider.pack(side="left", fill="x", expand=True)

        self._ram_warn = tk.Label(
            p, text="", font=Theme.FONT_XS, fg=Theme.YELLOW,
            bg=Theme.BG, wraplength=330, anchor="w",
        )
        self._ram_warn.pack(anchor="w", pady=(2, 0))
        self._on_tab_slider(2)

        # Toggles
        tgl = tk.Frame(p, bg=Theme.BG)
        tgl.pack(fill="x", pady=(10, 0))
        self._headless_var = tk.BooleanVar(value=True)
        self._shuffle_var  = tk.BooleanVar(value=True)
        self._mk_check(tgl, "Headless (hide browser)", self._headless_var)
        self._mk_check(tgl, "Shuffle video order", self._shuffle_var)

    def _mk_check(self, parent, text, var):
        row = tk.Frame(parent, bg=Theme.BG)
        row.pack(fill="x", pady=1)
        cb = tk.Checkbutton(
            row, text=text, variable=var, font=Theme.FONT_SM,
            fg=Theme.TEXT, bg=Theme.BG, activebackground=Theme.BG,
            activeforeground=Theme.TEXT, selectcolor=Theme.BG3,
            relief="flat", bd=0, anchor="w",
        )
        cb.pack(anchor="w")

    def _on_tab_slider(self, val):
        n = int(float(val))
        self._tab_lbl.config(text=f"Tabs: {n}")
        ram = n * 300
        if ram > 3000:
            txt, fg = f"⚠ ~{ram} MB — may lag on 4 GB. Use ≤ 3 tabs.", Theme.RED
        elif ram > 1800:
            txt, fg = f"~{ram} MB — tight on 4 GB.", Theme.YELLOW
        else:
            txt, fg = f"~{ram} MB — OK.", Theme.GREEN
        self._ram_warn.config(text=txt, fg=fg)

    # ── Right panel ────────────────────────────────────────────────────────
    def _build_right(self, p):
        # Tab status area
        self._tab_frame = tk.Frame(p, bg=Theme.BG)
        self._tab_frame.pack(fill="x", pady=(0, 6))
        self._tab_indicators: list[tk.Label] = []

        # Log
        log_hdr = tk.Frame(p, bg=Theme.BG)
        log_hdr.pack(fill="x")
        tk.Label(
            log_hdr, text="LOG", font=("Segoe UI", 8, "bold"),
            fg=Theme.TEXT_MUT, bg=Theme.BG,
        ).pack(side="left")
        _flat_btn(log_hdr, "Clear", self._clear_log,
                  fg=Theme.TEXT_MUT, padx=8, pady=2).pack(side="right")
        tk.Frame(p, bg=Theme.BORDER, height=1).pack(fill="x", pady=(2, 4))

        self._log_box = scrolledtext.ScrolledText(
            p, font=Theme.FONT_MONO, bg=Theme.BG2, fg=Theme.TEXT,
            insertbackground=Theme.TEXT, relief="flat", bd=0,
            highlightthickness=1, highlightbackground=Theme.BORDER,
            state="disabled", wrap="word", padx=8, pady=6,
        )
        self._log_box.pack(fill="both", expand=True)

        for tag, color in [
            ("info", Theme.TEXT), ("success", Theme.GREEN),
            ("error", Theme.RED), ("warning", Theme.YELLOW),
            ("dim", Theme.TEXT_MUT),
        ]:
            self._log_box.tag_config(tag, foreground=color)

        # Progress
        pf = tk.Frame(p, bg=Theme.BG)
        pf.pack(fill="x", pady=(8, 0))
        self._prog_lbl = tk.Label(
            pf, text="0 / 0", font=Theme.FONT_SM,
            fg=Theme.TEXT_DIM, bg=Theme.BG, anchor="w",
        )
        self._prog_lbl.pack(anchor="w")

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(
            "Accent.Horizontal.TProgressbar",
            troughcolor=Theme.BG3, background=Theme.ACCENT,
            bordercolor=Theme.BG3, lightcolor=Theme.ACCENT,
            darkcolor=Theme.ACCENT, thickness=6,
        )
        self._progress = ttk.Progressbar(
            pf, style="Accent.Horizontal.TProgressbar", mode="determinate",
        )
        self._progress.pack(fill="x", pady=(3, 0))

        # Stats row
        sf = tk.Frame(p, bg=Theme.BG)
        sf.pack(fill="x", pady=(8, 0))
        self._stat_ok    = self._stat_box(sf, "✓ OK",      Theme.GREEN)
        self._stat_err   = self._stat_box(sf, "✗ Fail",    Theme.RED)
        self._stat_eta   = self._stat_box(sf, "⏱ ETA",     Theme.TEXT_DIM)
        self._stat_speed = self._stat_box(sf, "⚡ vid/min", Theme.BLUE)

    def _stat_box(self, parent, label, color):
        f = tk.Frame(parent, bg=Theme.BG3, padx=14, pady=8,
                     highlightthickness=1, highlightbackground=Theme.BORDER)
        f.pack(side="left", padx=(0, 6), fill="x", expand=True)
        val = tk.Label(f, text="0", font=("Segoe UI", 15, "bold"),
                       fg=color, bg=Theme.BG3)
        val.pack()
        tk.Label(f, text=label, font=Theme.FONT_XS,
                 fg=Theme.TEXT_MUT, bg=Theme.BG3).pack()
        return val

    # ── Tab indicators ─────────────────────────────────────────────────────
    def _build_tab_indicators(self, n: int):
        for w in self._tab_frame.winfo_children():
            w.destroy()
        self._tab_indicators.clear()

        tk.Label(
            self._tab_frame, text="TAB STATUS", font=("Segoe UI", 8, "bold"),
            fg=Theme.TEXT_MUT, bg=Theme.BG,
        ).pack(anchor="w")
        tk.Frame(self._tab_frame, bg=Theme.BORDER, height=1).pack(
            fill="x", pady=(2, 4))

        grid = tk.Frame(self._tab_frame, bg=Theme.BG)
        grid.pack(fill="x")

        for i in range(n):
            c = Theme.tab_color(i)
            cell = tk.Frame(
                grid, bg=Theme.BG3, padx=10, pady=6,
                highlightthickness=1, highlightbackground=c,
            )
            cell.grid(row=i // 3, column=i % 3, padx=3, pady=3, sticky="ew")
            grid.columnconfigure(i % 3, weight=1)

            tk.Label(
                cell, text=f"Tab {i + 1}", font=("Segoe UI", 9, "bold"),
                fg=c, bg=Theme.BG3, anchor="w",
            ).pack(anchor="w")
            st = tk.Label(
                cell, text="Waiting…", font=Theme.FONT_XS,
                fg=Theme.TEXT_MUT, bg=Theme.BG3, anchor="w",
            )
            st.pack(anchor="w")
            self._tab_indicators.append(st)

    def _update_tab_status(self, tab_id: int, text: str, tag: str = "dim"):
        if tab_id < len(self._tab_indicators):
            colors = {
                "success": Theme.GREEN, "error": Theme.RED,
                "warning": Theme.YELLOW, "info": Theme.TEXT,
                "dim": Theme.TEXT_MUT,
            }
            self._tab_indicators[tab_id].config(
                text=text, fg=colors.get(tag, Theme.TEXT_MUT))

    # ── Footer ─────────────────────────────────────────────────────────────
    def _build_footer(self):
        tk.Frame(self, bg=Theme.BORDER, height=1).pack(fill="x")
        bar = tk.Frame(self, bg=Theme.BG, pady=10)
        bar.pack(fill="x", padx=20)

        self._start_btn = tk.Button(
            bar, text="▶  START", font=Theme.FONT_BTN,
            bg=Theme.ACCENT, fg="white",
            activebackground=Theme.ACCENT_D, activeforeground="white",
            relief="flat", bd=0, cursor="hand2", padx=28, pady=10,
            command=self._toggle_run,
        )
        self._start_btn.pack(side="left")
        self._start_btn.bind("<Enter>",
            lambda e: self._start_btn.config(bg=Theme.ACCENT2)
            if not self._running else None)
        self._start_btn.bind("<Leave>",
            lambda e: self._start_btn.config(
                bg=Theme.ACCENT if not self._running else Theme.BG3))

        _flat_btn(bar, "💾  Save Settings", self._save_settings,
                  fg=Theme.TEXT_DIM).pack(side="right")

    # ────────────────────────────────────────────────────────────────────────
    #  RUN LOGIC
    # ────────────────────────────────────────────────────────────────────────
    def _toggle_run(self):
        if self._running:
            self._stop()
        else:
            self._start()

    def _start(self):
        if not self._urls:
            messagebox.showwarning("No list", "Fetch or load a shorts list first.")
            return

        n_tabs = self._tabs_var.get()
        self._running = True
        self._stop_flag.clear()
        self._counters = Counters()
        self._start_t = time.time()

        self._start_btn.config(text="■  STOP", bg=Theme.BG3, fg=Theme.ACCENT)
        self._status_lbl.config(text=f"● Running {n_tabs} tabs", fg=Theme.YELLOW)
        self._build_tab_indicators(n_tabs)

        cfg = RunConfig(
            watch_time=float(self._watch_var.get() or 11),
            loops=int(self._loops_var.get() or 1),
            delay=float(self._delay_var.get() or 1),
            headless=self._headless_var.get(),
            shuffle=self._shuffle_var.get(),
            proxy=self._proxy_var.get().strip(),
            n_tabs=n_tabs,
        )
        threading.Thread(target=self._orchestrator, args=(cfg,),
                         daemon=True).start()

    def _stop(self):
        self._stop_flag.set()
        log("Stopping all tabs…", "warning")
        self._start_btn.config(text="⏳ Stopping…", state="disabled")

    def _orchestrator(self, cfg: RunConfig):
        urls = list(self._urls) * cfg.loops
        if cfg.shuffle:
            random.shuffle(urls)

        with self._lock:
            self._counters.total = len(urls)

        log(f"Starting {cfg.n_tabs} tabs for {len(urls)} videos…")

        url_q: queue.Queue = queue.Queue()
        for u in urls:
            url_q.put(u)

        threads = []
        for i in range(cfg.n_tabs):
            t = threading.Thread(target=self._tab_thread,
                                 args=(i, url_q, cfg), daemon=True)
            threads.append(t)
            t.start()
            time.sleep(0.6)

        for t in threads:
            t.join()

        self.after(0, self._on_done)

    def _tab_thread(self, tab_id: int, url_q: queue.Queue, cfg: RunConfig):
        driver = None
        vid_count = 0
        self.after(0, self._update_tab_status, tab_id, "Starting…", "warning")

        try:
            driver = build_driver(cfg.headless, cfg.proxy)
            self.after(0, self._update_tab_status, tab_id, "Ready ✓", "success")
            log("Ready", "success", tab_id)

            while not self._stop_flag.is_set():
                try:
                    url = url_q.get(timeout=3)
                except queue.Empty:
                    break

                sid = url.rsplit("/", 1)[-1]
                self.after(0, self._update_tab_status,
                           tab_id, f"▶ {sid}", "info")

                ok = watch_video(driver, url, cfg.watch_time)

                with self._lock:
                    if ok:
                        self._counters.success += 1
                    else:
                        self._counters.fail += 1
                    self._counters.done += 1

                url_q.task_done()
                vid_count += 1

                self.after(0, self._update_tab_status, tab_id,
                           "✓ Done" if ok else "✗ Error",
                           "success" if ok else "error")

                time.sleep(cfg.delay + random.uniform(0, 0.8))

                if vid_count % self.RESTART_INTERVAL == 0:
                    self.after(0, self._update_tab_status,
                               tab_id, "↺ Restarting…", "warning")
                    try:
                        driver.quit()
                    except Exception:
                        pass
                    time.sleep(1.5)
                    driver = build_driver(cfg.headless, cfg.proxy)

        except Exception as e:
            log(f"Error: {e}", "error", tab_id)
            self.after(0, self._update_tab_status, tab_id, "✗ Error", "error")
        finally:
            if driver:
                try:
                    driver.quit()
                except Exception:
                    pass
            self.after(0, self._update_tab_status, tab_id, "Stopped", "dim")

    def _on_done(self):
        self._running = False
        self._start_btn.config(
            text="▶  START", bg=Theme.ACCENT, fg="white", state="normal")
        self._status_lbl.config(text="● Done", fg=Theme.GREEN)
        c = self._counters
        log(f"Finished!  ✓ {c.success}   ✗ {c.fail}", "success")

    # ────────────────────────────────────────────────────────────────────────
    #  POLLING
    # ────────────────────────────────────────────────────────────────────────
    def _poll_stats(self):
        if self._running:
            c = self._counters
            total = max(c.total, 1)
            done = c.done
            pct = done / total * 100
            elapsed = max(time.time() - self._start_t, 0.1)
            eta_s = int((elapsed / max(done, 1)) * (total - done))
            speed = round(done / (elapsed / 60), 1) if elapsed > 1 else 0

            self._progress["value"] = pct
            self._prog_lbl.config(text=f"{done} / {total}  ({pct:.0f}%)")
            self._stat_ok.config(text=str(c.success))
            self._stat_err.config(text=str(c.fail))
            self._stat_eta.config(text=f"{eta_s // 60}m {eta_s % 60}s")
            self._stat_speed.config(text=str(speed))

        self.after(500, self._poll_stats)

    def _poll_log(self):
        try:
            while True:
                msg, tag = _log_queue.get_nowait()
                self._log_box.config(state="normal")
                self._log_box.insert("end", msg + "\n", tag)
                self._log_box.see("end")
                self._log_box.config(state="disabled")
        except queue.Empty:
            pass
        self.after(80, self._poll_log)

    # ────────────────────────────────────────────────────────────────────────
    #  FETCH / FILE I/O
    # ────────────────────────────────────────────────────────────────────────
    def _fetch_urls(self):
        url = self._channel_var.get().strip()
        if not url:
            messagebox.showwarning("Missing URL", "Enter a YouTube channel URL.")
            return
        self._fetch_btn.config(state="disabled", text="⏳ Loading…")

        def worker():
            max_v = int(self._max_var.get() or 0)
            urls = get_shorts_urls(url, max_v)
            self._urls = urls
            self.after(0, self._on_fetched, len(urls))

        threading.Thread(target=worker, daemon=True).start()

    def _on_fetched(self, count):
        self._fetch_btn.config(state="normal", text="↓  Fetch Shorts")
        if count:
            n = self._tabs_var.get()
            mins = max(count * 13 // 60 // n, 1)
            self._url_count.config(
                text=f"✓ {count} shorts  •  ~{mins} min with {n} tab(s)",
                fg=Theme.GREEN)
        else:
            self._url_count.config(text="No videos found", fg=Theme.RED)

    def _load_from_file(self):
        path = filedialog.askopenfilename(
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if not path:
            return
        with open(path, encoding="utf-8") as f:
            self._urls = [l.strip() for l in f if l.strip()]
        self._url_count.config(
            text=f"✓ {len(self._urls)} URLs from file", fg=Theme.GREEN)
        log(f"Loaded {len(self._urls)} URLs", "success")

    def _save_to_file(self):
        if not self._urls:
            messagebox.showinfo("Empty", "No URLs to save.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".txt")
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(self._urls))
        log(f"Saved {len(self._urls)} URLs", "success")

    # ────────────────────────────────────────────────────────────────────────
    #  SETTINGS
    # ────────────────────────────────────────────────────────────────────────
    def _save_settings(self):
        cfg = {
            "channel":    self._channel_var.get(),
            "watch_time": self._watch_var.get(),
            "loops":      self._loops_var.get(),
            "max_videos": self._max_var.get(),
            "delay":      self._delay_var.get(),
            "proxy":      self._proxy_var.get(),
            "n_tabs":     self._tabs_var.get(),
            "headless":   self._headless_var.get(),
            "shuffle":    self._shuffle_var.get(),
        }
        try:
            with open(get_settings_path(), "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2)
            log("Settings saved ✓", "success")
        except Exception as e:
            log(f"Save failed: {e}", "error")

    def _load_settings(self):
        path = get_settings_path()
        if not os.path.exists(path):
            return
        try:
            with open(path, encoding="utf-8") as f:
                cfg = json.load(f)
            self._channel_var.set(cfg.get("channel", ""))
            self._watch_var.set(cfg.get("watch_time", "11"))
            self._loops_var.set(cfg.get("loops", "1"))
            self._max_var.set(cfg.get("max_videos", "0"))
            self._delay_var.set(cfg.get("delay", "1"))
            self._proxy_var.set(cfg.get("proxy", ""))
            self._tabs_var.set(cfg.get("n_tabs", 2))
            self._headless_var.set(cfg.get("headless", True))
            self._shuffle_var.set(cfg.get("shuffle", True))
        except Exception:
            pass

    # ────────────────────────────────────────────────────────────────────────
    #  MISC
    # ────────────────────────────────────────────────────────────────────────
    def _clear_log(self):
        self._log_box.config(state="normal")
        self._log_box.delete("1.0", "end")
        self._log_box.config(state="disabled")

    def on_close(self):
        if self._running:
            if messagebox.askyesno(
                "Running",
                "The bot is running. Quitting will stop all tabs. Continue?",
            ):
                self._stop_flag.set()
                self.destroy()
        else:
            self.destroy()

# ── Dependency check ───────────────────────────────────────────────────────
def check_deps():
    pkgs = {
        "selenium": "selenium",
        "webdriver_manager": "webdriver-manager",
        "yt_dlp": "yt-dlp",
    }
    for mod, pip_name in pkgs.items():
        try:
            __import__(mod)
        except ImportError:
            print(f"Installing {pip_name}…")
            subprocess.run(
                [sys.executable, "-m", "pip", "install", pip_name, "-q"],
                check=False,
            )

# ── Entry ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    check_deps()
    app = App()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()