#!/usr/bin/env python3
"""
YT Downloader  –  v6  (CustomTkinter)
Tabs: Download · History
Requirements:
    pip install yt-dlp customtkinter tkinterdnd2 plyer
    ffmpeg on PATH  (https://ffmpeg.org/download.html)
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
import threading
import subprocess
import shutil
import os, sys, json, re, time
import urllib.parse as up
from datetime import datetime
from pathlib import Path

try:
    from tkinterdnd2 import TkinterDnD, DND_TEXT, DND_FILES
    _DND_OK = True
except Exception:
    _DND_OK = False
    TkinterDnD = None
    DND_TEXT = DND_FILES = None

try:
    from plyer import notification as _plyer_notif
    _NOTIF_OK = True
except Exception:
    _NOTIF_OK = False

try:
    from PIL import Image as _PILImage
    _PIL_OK = True
except Exception:
    _PIL_OK = False

def _resource_path(name):
    """Resolve a bundled resource — works in dev and inside a PyInstaller --onefile exe."""
    base = getattr(sys, "_MEIPASS", None) or Path(__file__).resolve().parent
    return str(Path(base) / name)

LOGO_PATH = _resource_path("REAPER_01.png")
ICON_PATH = _resource_path("reaper.ico")

# Set a stable AppUserModelID so Windows groups the pinned exe with the running app,
# and uses the embedded icon for both. Has to happen before the Tk window is created.
if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("yt.downloader.reaper.1")
    except Exception:
        pass

# ─────────────────────────────────────────────────────────────────────────────
#  THEME
# ─────────────────────────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

BG      = "#000000"
CARD    = "#070707"
CARD2   = "#0d0d0d"
BORDER  = "#1a1a1a"
ACCENT  = "#ffffff"
ACCENT2 = "#e0e0e0"
TEXT    = "#f0f0f0"
DIM     = "#777777"
SUCCESS = "#00e676"
ERROR   = "#ff5252"
WARN    = "#ffab40"

FH  = ("Old London", 32)
FB  = ("Segoe UI", 12)
FS  = ("Segoe UI", 11)
FXS = ("Segoe UI",  9)
FM  = ("Consolas", 10)

HISTORY_FILE  = Path.home() / ".yt_downloader_history.json"
SETTINGS_FILE = Path.home() / ".yt_downloader_settings.json"

YT_URL_RE = re.compile(
    r"https?://(?:www\.)?(?:youtube\.com/watch\?|youtu\.be/)[^\s'\"<>]+", re.I
)


# ─────────────────────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────────────────────

_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


def check_deps():
    missing = []
    for prog in (["yt-dlp", "--version"], ["ffmpeg", "-version"]):
        try:
            subprocess.run(prog, capture_output=True, check=True,
                           creationflags=_NO_WINDOW)
        except Exception:
            missing.append(prog[0])
    return missing


def clean_url(url):
    parsed = up.urlparse(url)
    params = up.parse_qs(parsed.query)
    clean  = {k: v for k, v in params.items() if k == "v"}
    return up.urlunparse(parsed._replace(query=up.urlencode(clean, doseq=True)))


def load_history():
    try:
        return json.loads(HISTORY_FILE.read_text())
    except Exception:
        return []


def save_history(hist):
    try:
        HISTORY_FILE.write_text(json.dumps(hist, indent=2))
    except Exception:
        pass


def load_settings():
    try:
        return json.loads(SETTINGS_FILE.read_text())
    except Exception:
        return {}


def save_settings(s):
    try:
        SETTINGS_FILE.write_text(json.dumps(s, indent=2))
    except Exception:
        pass


def notify(title, message):
    if not _NOTIF_OK:
        return
    try:
        _plyer_notif.notify(
            title=title, message=message,
            app_name="YT Downloader", timeout=5,
        )
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
#  BASE CLASS
# ─────────────────────────────────────────────────────────────────────────────

if _DND_OK:
    class _Root(ctk.CTk, TkinterDnD.DnDWrapper):
        def __init__(self, *a, **kw):
            super().__init__(*a, **kw)
            self.TkdndVersion = TkinterDnD._require(self)
else:
    _Root = ctk.CTk


# ─────────────────────────────────────────────────────────────────────────────
#  MAIN APP
# ─────────────────────────────────────────────────────────────────────────────

class App(_Root):
    _URL_RE = re.compile(r"https?://[^\s'\"<>]+", re.I)

    def __init__(self):
        super().__init__()
        self.title("YT Downloader")
        self.geometry("880x840")
        self.minsize(820, 740)
        self.configure(fg_color=BG)

        # Window/taskbar icon — replaces tkinter's default blue feather
        try:
            if Path(ICON_PATH).is_file():
                self.iconbitmap(ICON_PATH)
        except Exception:
            pass

        self._settings  = load_settings()
        default_dl      = str(Path.home() / "Downloads")
        self._save_dir  = self._settings.get("save_dir", default_dl)
        if not Path(self._save_dir).is_dir():
            self._save_dir = default_dl
        self._history   = load_history()
        self._proc      = None
        self._cancelled = False

        self._build_ui()
        self._init_drag_and_drop()
        self._check_deps_on_start()
        self._refresh_history()

        self.bind("<FocusIn>", self._on_focus)

    # ─────────────────────────────────────────────────────────────────────────
    #  SHELL
    # ─────────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=28, pady=(18, 6))

        logo_done = False
        self._logo_load_error = None
        if not _PIL_OK:
            self._logo_load_error = "PIL/Pillow not available"
        elif not Path(LOGO_PATH).is_file():
            self._logo_load_error = f"Logo not found at {LOGO_PATH}"
        else:
            try:
                pil_img = _PILImage.open(LOGO_PATH).convert("RGBA")
                self._logo_img = ctk.CTkImage(
                    light_image=pil_img, dark_image=pil_img, size=(110, 96),
                )
                ctk.CTkLabel(hdr, image=self._logo_img, text="").pack(
                    side="left", padx=(0, 10))
                logo_done = True
            except Exception as e:
                self._logo_load_error = f"{type(e).__name__}: {e}"
        if not logo_done:
            ctk.CTkLabel(hdr, text="💾  ", font=("Segoe UI Emoji", 30),
                         text_color=TEXT).pack(side="left")

        ctk.CTkLabel(hdr, text="YT Downloader", font=FH,
                     text_color=TEXT).pack(side="left")

        self._update_btn = ctk.CTkButton(
            hdr, text="⟳  Update yt-dlp", font=FXS,
            width=140, height=30, corner_radius=15,
            fg_color="transparent", hover_color=CARD2,
            text_color=ACCENT, border_width=2, border_color=ACCENT,
            command=self._update_ytdlp,
        )
        self._update_btn.pack(side="right")

        self._tabs = ctk.CTkTabview(
            self, fg_color=CARD,
            segmented_button_fg_color="#bbbbbb",
            segmented_button_selected_color=ACCENT,
            segmented_button_selected_hover_color=ACCENT2,
            segmented_button_unselected_color="#bbbbbb",
            segmented_button_unselected_hover_color="#cccccc",
            text_color="#000000",
            border_width=1, border_color=BORDER,
            corner_radius=14,
        )
        self._tabs.pack(fill="both", expand=True, padx=20, pady=(2, 20))
        self._tabs.add("Download")
        self._tabs.add("History")
        self._build_download_tab(self._tabs.tab("Download"))
        self._build_history_tab(self._tabs.tab("History"))

    # =========================================================================
    #  TAB 1 – DOWNLOAD
    # =========================================================================

    def _build_download_tab(self, p):
        card = ctk.CTkFrame(p, fg_color=CARD2,
                            border_width=1, border_color=BORDER,
                            corner_radius=12)
        card.pack(fill="x", padx=8, pady=(8, 10))
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=18, pady=14)

        # ─── URL row ────────────────────────────────────────────────────────
        url_hdr = ctk.CTkFrame(inner, fg_color="transparent")
        url_hdr.pack(fill="x")
        ctk.CTkLabel(url_hdr, text="YouTube URL", font=FS,
                     text_color=DIM).pack(side="left")
        hint = "drag-and-drop or paste" if _DND_OK else "paste URL"
        ctk.CTkLabel(url_hdr, text=hint, font=FXS,
                     text_color=DIM).pack(side="right")

        self._url_var = tk.StringVar()
        self._url_entry = ctk.CTkEntry(
            inner, textvariable=self._url_var, font=FB,
            height=40, corner_radius=20,
            fg_color=BG, border_color=BORDER, border_width=1,
            text_color=TEXT, placeholder_text="https://youtube.com/…",
            placeholder_text_color=DIM,
        )
        self._url_entry.pack(fill="x", pady=(4, 10))

        # ─── Format row ─────────────────────────────────────────────────────
        ctk.CTkLabel(inner, text="Format", font=FS,
                     text_color=DIM).pack(anchor="w")
        fr = tk.Frame(inner, bg=CARD2)
        fr.pack(fill="x", pady=(4, 10))
        self._fmt_var     = tk.StringVar(value="mp4")
        self._fmt_buttons = {}
        for lbl, val in [("🎬  MP4",               "mp4"),
                          ("🎵  MP3 (audio only)",  "mp3"),
                          ("🎤  WAV (lossless)",     "wav")]:
            b = ctk.CTkButton(
                fr, text=lbl, font=FS, height=36, corner_radius=18,
                fg_color=BG, hover_color=CARD,
                text_color=TEXT, border_width=1, border_color=BORDER,
                command=lambda v=val: self._sel_fmt(v),
            )
            b.pack(side="left", padx=(0, 8))
            self._fmt_buttons[val] = b

        # ─── Options row (context-sensitive: quality + embed thumb) ─────────
        # height=1 prevents the default CTkFrame height of 200 from leaking through
        self._options_frame = ctk.CTkFrame(inner, fg_color="transparent", height=1)
        self._options_frame.pack(fill="x", pady=(0, 6))
        self._embed_thumb_var = tk.BooleanVar(value=True)

        # ─── Save folder row ────────────────────────────────────────────────
        ctk.CTkLabel(inner, text="Save to", font=FS,
                     text_color=DIM).pack(anchor="w", pady=(4, 0))
        dr = tk.Frame(inner, bg=CARD2)
        dr.pack(fill="x", pady=(4, 0))
        self._dir_lbl = ctk.CTkLabel(
            dr, text="📁  " + self._save_dir, font=FM,
            anchor="w", text_color=TEXT,
            fg_color=BG, corner_radius=20, height=36, padx=14,
        )
        self._dir_lbl.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(
            dr, text="Browse", font=FS, width=90, height=36, corner_radius=18,
            fg_color=BG, hover_color=CARD, text_color=TEXT,
            border_width=1, border_color=BORDER,
            command=self._browse,
        ).pack(side="left", padx=(8, 0))

        # Now safe to set initial format (all widgets exist)
        self._sel_fmt("mp4")

        # ─── Download + Cancel buttons ──────────────────────────────────────
        btn_row = ctk.CTkFrame(p, fg_color="transparent")
        btn_row.pack(fill="x", padx=8, pady=(4, 10))

        self._dl_btn = ctk.CTkButton(
            btn_row, text="Download",
            font=("Segoe UI", 14, "bold"),
            height=52, corner_radius=26,
            fg_color=ACCENT, hover_color=ACCENT2, text_color="#000000",
            command=self._start_download,
        )
        self._dl_btn.pack(side="left", fill="x", expand=True)

        self._cancel_btn = ctk.CTkButton(
            btn_row, text="✕  Cancel",
            font=("Segoe UI", 12),
            width=110, height=52, corner_radius=26,
            fg_color=BG, hover_color=CARD,
            text_color=ERROR, border_width=1, border_color=ERROR,
            command=self._cancel_download,
            state="disabled",
        )
        self._cancel_btn.pack(side="left", padx=(10, 0))

        # ─── Progress bar ────────────────────────────────────────────────────
        prog = ctk.CTkFrame(p, fg_color="transparent")
        prog.pack(fill="x", padx=8, pady=(0, 4))

        self._dl_title = ctk.CTkLabel(prog, text="", font=FM,
                                      text_color=TEXT, anchor="w")
        self._dl_title.pack(fill="x", pady=(4, 2))

        bar_row = ctk.CTkFrame(prog, fg_color="transparent")
        bar_row.pack(fill="x")

        self._progress_bar = ctk.CTkProgressBar(
            bar_row, height=10, corner_radius=5,
            fg_color=CARD, progress_color=ACCENT,
        )
        self._progress_bar.set(0)
        self._progress_bar.pack(side="left", fill="x", expand=True, pady=4)

        self._pct_label = ctk.CTkLabel(
            bar_row, text="0.0%", font=FM,
            text_color=DIM, width=52, anchor="e",
        )
        self._pct_label.pack(side="left", padx=(8, 0))

        self._dl_stats = ctk.CTkLabel(prog, text="", font=FM,
                                      text_color=DIM, anchor="w")
        self._dl_stats.pack(fill="x")

        # ─── Log box ─────────────────────────────────────────────────────────
        term = ctk.CTkFrame(p, fg_color=CARD, corner_radius=0, border_width=0)
        term.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self._log_box = tk.Text(
            term, font=FM, fg=DIM, bg=CARD,
            relief="flat", bd=0, state="disabled",
            wrap="word", padx=12, pady=8, height=9,
            insertbackground=TEXT, highlightthickness=0,
        )
        self._log_box.pack(fill="both", expand=True)
        self._log_box.tag_config("error",   foreground=ERROR)
        self._log_box.tag_config("success", foreground=SUCCESS)
        self._log_box.tag_config("warn",    foreground=WARN)
        self._log_box.tag_config("info",    foreground=DIM)
        self._log("Ready. Paste a YouTube URL above and hit Download.", "info")

    def _build_quality_controls(self):
        for w in self._options_frame.winfo_children():
            w.destroy()

        fmt = self._fmt_var.get()

        if fmt == "mp4":
            ctk.CTkLabel(self._options_frame, text="Quality", font=FS,
                         text_color=DIM).pack(anchor="w", pady=(0, 4))
            qr = tk.Frame(self._options_frame, bg=CARD2)
            qr.pack(fill="x")
            self._quality_var     = tk.StringVar(value="best")
            self._quality_buttons = {}
            for lbl, val in [("Best", "best"), ("1080p", "1080"),
                              ("720p", "720"), ("480p", "480"), ("360p", "360")]:
                b = ctk.CTkButton(
                    qr, text=lbl, font=FS, height=32, corner_radius=16,
                    fg_color=BG, hover_color=CARD,
                    text_color=TEXT, border_width=1, border_color=BORDER,
                    command=lambda v=val: self._sel_quality(v),
                )
                b.pack(side="left", padx=(0, 6))
                self._quality_buttons[val] = b
            self._sel_quality("best")

        elif fmt == "mp3":
            ctk.CTkLabel(self._options_frame, text="Audio Quality", font=FS,
                         text_color=DIM).pack(anchor="w", pady=(0, 4))
            aqr = tk.Frame(self._options_frame, bg=CARD2)
            aqr.pack(fill="x")
            self._audio_q_var     = tk.StringVar(value="192")
            self._audio_q_buttons = {}
            for lbl, val in [("128 kbps", "128"), ("192 kbps", "192"), ("320 kbps", "320")]:
                b = ctk.CTkButton(
                    aqr, text=lbl, font=FS, height=32, corner_radius=16,
                    fg_color=BG, hover_color=CARD,
                    text_color=TEXT, border_width=1, border_color=BORDER,
                    command=lambda v=val: self._sel_audio_q(v),
                )
                b.pack(side="left", padx=(0, 6))
                self._audio_q_buttons[val] = b
            self._sel_audio_q("192")

            # Embed thumbnail checkbox below audio quality
            ctk.CTkCheckBox(
                self._options_frame,
                text="Embed thumbnail in MP3",
                font=FS,
                variable=self._embed_thumb_var,
                text_color=DIM,
                fg_color=ACCENT, hover_color=ACCENT2,
                checkmark_color=BG, border_color=BORDER,
            ).pack(anchor="w", pady=(8, 0))

        # WAV: no options — frame stays empty (height=1 keeps it collapsed)

    # =========================================================================
    #  TAB 2 – HISTORY
    # =========================================================================

    def _build_history_tab(self, p):
        hdr = ctk.CTkFrame(p, fg_color="transparent")
        hdr.pack(fill="x", padx=8, pady=(8, 6))
        ctk.CTkLabel(hdr, text="Download History",
                     font=("Segoe UI", 14, "bold"),
                     text_color=TEXT).pack(side="left")
        ctk.CTkButton(
            hdr, text="Clear all", font=FS, height=32, corner_radius=16,
            fg_color="transparent", hover_color=CARD2,
            text_color=ERROR, border_width=1, border_color=BORDER,
            command=self._clear_history,
        ).pack(side="right")

        self._hist_inner = ctk.CTkScrollableFrame(
            p, fg_color=CARD2, corner_radius=12,
            border_width=1, border_color=BORDER,
        )
        self._hist_inner.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    # ─────────────────────────────────────────────────────────────────────────
    #  HISTORY LOGIC
    # ─────────────────────────────────────────────────────────────────────────

    def _refresh_history(self):
        for w in self._hist_inner.winfo_children():
            w.destroy()

        if not self._history:
            ctk.CTkLabel(self._hist_inner, text="No downloads yet.",
                         font=FB, text_color=DIM).pack(pady=24)
            return

        for i, entry in enumerate(reversed(self._history)):
            real_i = len(self._history) - 1 - i
            row = ctk.CTkFrame(self._hist_inner, fg_color=BG, corner_radius=10)
            row.pack(fill="x", padx=6, pady=4)

            title = entry.get("title", entry.get("file", "Unknown"))
            ctk.CTkLabel(
                row, text=title[:55] + ("…" if len(title) > 55 else ""),
                font=FS, text_color=TEXT, anchor="w",
            ).pack(side="left", padx=(14, 8), pady=10, fill="x", expand=True)

            ctk.CTkLabel(row, text=entry.get("fmt", "?").upper(),
                         font=("Segoe UI", 9, "bold"),
                         text_color=ACCENT, width=50).pack(side="left", padx=4)

            ctk.CTkLabel(row, text=entry.get("date", ""), font=FM,
                         text_color=DIM, width=120).pack(side="left", padx=4)

            path   = entry.get("path", "")
            folder = str(Path(path).parent) if path else self._save_dir

            ctk.CTkButton(
                row, text="✕", font=FS,
                width=32, height=28, corner_radius=14,
                fg_color="transparent", hover_color=CARD,
                text_color=ERROR, border_width=1, border_color=BORDER,
                command=lambda idx=real_i: self._delete_history_entry(idx),
            ).pack(side="right", padx=(4, 10), pady=8)

            ctk.CTkButton(
                row, text="▶ Open", font=FS,
                width=80, height=28, corner_radius=14,
                fg_color="transparent", hover_color=CARD,
                text_color=TEXT, border_width=1, border_color=BORDER,
                command=lambda f=path: self._open_file(f),
            ).pack(side="right", padx=4, pady=8)

            ctk.CTkButton(
                row, text="📂 Show", font=FS,
                width=80, height=28, corner_radius=14,
                fg_color="transparent", hover_color=CARD,
                text_color=TEXT, border_width=1, border_color=BORDER,
                command=lambda f=folder: self._open_folder(f),
            ).pack(side="right", padx=4, pady=8)

    def _add_history(self, title, fmt, path):
        self._history.append({
            "title": title, "fmt": fmt, "path": path,
            "date":  datetime.now().strftime("%Y-%m-%d  %H:%M"),
        })
        save_history(self._history)
        self.after(0, self._refresh_history)

    def _clear_history(self):
        if messagebox.askyesno("Clear history", "Remove all history entries?"):
            self._history = []
            save_history(self._history)
            self._refresh_history()

    def _delete_history_entry(self, idx):
        if 0 <= idx < len(self._history):
            del self._history[idx]
            save_history(self._history)
            self._refresh_history()

    def _open_file(self, path):
        if not path or not Path(path).exists():
            messagebox.showwarning("File not found", f"Cannot find:\n{path}")
            return
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])

    def _open_folder(self, folder):
        if sys.platform == "win32":
            os.startfile(folder)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", folder])
        else:
            subprocess.Popen(["xdg-open", folder])

    # ─────────────────────────────────────────────────────────────────────────
    #  DRAG AND DROP
    # ─────────────────────────────────────────────────────────────────────────

    def _init_drag_and_drop(self):
        if not _DND_OK:
            return
        try:
            self.drop_target_register(DND_TEXT, DND_FILES)
            self.dnd_bind("<<Drop>>", self._on_drop)
        except Exception as e:
            self._log(f"⚠  Drag-and-drop unavailable: {e}", "warn")

    def _on_drop(self, event):
        raw = (event.data or "").strip().strip("{}").strip()
        if not raw:
            return
        m = self._URL_RE.search(raw)
        url = m.group(0) if m else (raw.split()[0] if raw else "")
        if url:
            self._url_var.set(url)
            self._url_entry.focus_set()
            self._tabs.set("Download")

    # ─────────────────────────────────────────────────────────────────────────
    #  CLIPBOARD AUTO-DETECT
    # ─────────────────────────────────────────────────────────────────────────

    def _on_focus(self, event):
        if event.widget is not self:
            return
        if self._url_var.get().strip():
            return
        try:
            clip = self.clipboard_get().strip()
        except Exception:
            return
        if YT_URL_RE.search(clip):
            self._url_var.set(clip)
            self._log("ℹ  YouTube URL auto-filled from clipboard.", "info")

    # ─────────────────────────────────────────────────────────────────────────
    #  FORMAT / QUALITY SELECTORS
    # ─────────────────────────────────────────────────────────────────────────

    def _sel_fmt(self, val):
        self._fmt_var.set(val)
        for k, b in self._fmt_buttons.items():
            if k == val:
                b.configure(fg_color=CARD, border_color=ACCENT, text_color=TEXT)
            else:
                b.configure(fg_color=BG, border_color=BORDER, text_color=TEXT)
        self._build_quality_controls()

    def _sel_quality(self, val):
        self._quality_var.set(val)
        for k, b in self._quality_buttons.items():
            if k == val:
                b.configure(fg_color=CARD, border_color=ACCENT, text_color=TEXT)
            else:
                b.configure(fg_color=BG, border_color=BORDER, text_color=TEXT)

    def _sel_audio_q(self, val):
        self._audio_q_var.set(val)
        for k, b in self._audio_q_buttons.items():
            if k == val:
                b.configure(fg_color=CARD, border_color=ACCENT, text_color=TEXT)
            else:
                b.configure(fg_color=BG, border_color=BORDER, text_color=TEXT)

    def _browse(self):
        d = filedialog.askdirectory(initialdir=self._save_dir)
        if d:
            self._save_dir = d
            self._dir_lbl.configure(text="📁  " + d)
            self._settings["save_dir"] = d
            save_settings(self._settings)

    # ─────────────────────────────────────────────────────────────────────────
    #  LOG HELPERS
    # ─────────────────────────────────────────────────────────────────────────

    def _log(self, msg, tag="info"):
        self._log_box.configure(state="normal")
        self._log_box.insert("end", msg.rstrip() + "\n", tag)
        self._log_box.see("end")
        self._log_box.configure(state="disabled")

    def _clear_log(self):
        self._log_box.configure(state="normal")
        self._log_box.delete("1.0", "end")
        self._log_box.configure(state="disabled")

    # ─────────────────────────────────────────────────────────────────────────
    #  DOWNLOAD LOGIC
    # ─────────────────────────────────────────────────────────────────────────

    def _check_deps_on_start(self):
        missing = check_deps()
        if missing:
            self._log("⚠  Missing: " + ", ".join(missing) +
                      " — see setup guide.", "error")
        if getattr(self, "_logo_load_error", None):
            self._log("⚠  Logo load failed: " + self._logo_load_error, "warn")

    def _start_download(self):
        url = self._url_var.get().strip()
        if not url:
            messagebox.showwarning("No URL", "Please paste a YouTube URL first.")
            return
        missing = check_deps()
        if missing:
            messagebox.showerror("Missing deps", "Install: " + ", ".join(missing))
            return
        self._cancelled = False
        self._dl_btn.configure(state="disabled", text="Downloading…")
        self._cancel_btn.configure(state="normal")
        self._clear_log()
        self._progress_bar.set(0)
        self._pct_label.configure(text="0.0%")
        self._dl_title.configure(text="Resolving video…")
        self._dl_stats.configure(text="")
        threading.Thread(target=self._run_download, args=(url,), daemon=True).start()

    def _cancel_download(self):
        self._cancelled = True
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()

    def _run_download(self, url):
        fmt     = self._fmt_var.get()
        out_dir = self._save_dir
        os.makedirs(out_dir, exist_ok=True)
        template = os.path.join(out_dir, "%(title)s.%(ext)s")

        cleaned = clean_url(url)
        if cleaned != url:
            self.after(0, self._log,
                       "ℹ  Playlist stripped — downloading single video only.", "warn")
        url = cleaned

        progress_tpl = ("PRG|%(progress._percent_str)s"
                        "|%(progress._speed_str)s"
                        "|%(progress._eta_str)s"
                        "|%(info.title)s")
        base = ["--no-playlist", "--no-color", "--newline",
                "--progress-template", progress_tpl,
                "--print", "after_move:filepath"]

        if fmt == "mp4":
            q = self._quality_var.get() if hasattr(self, "_quality_var") else "best"
            if q == "best":
                fmt_str = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
            else:
                fmt_str = (f"bestvideo[height<={q}][ext=mp4]+bestaudio[ext=m4a]/"
                           f"bestvideo[height<={q}]+bestaudio/best[height<={q}]/best")
            cmd = ["yt-dlp", *base,
                   "--format", fmt_str,
                   "--merge-output-format", "mp4",
                   "--output", template, url]

        elif fmt == "mp3":
            bitrate = (self._audio_q_var.get() if hasattr(self, "_audio_q_var") else "192") + "K"
            extra = (["--embed-thumbnail", "--add-metadata"]
                     if self._embed_thumb_var.get() else [])
            cmd = ["yt-dlp", *base,
                   "--format", "bestaudio/best",
                   "--extract-audio", "--audio-format", "mp3",
                   "--audio-quality", bitrate,
                   *extra,
                   "--output", template, url]

        else:  # wav
            cmd = ["yt-dlp", *base,
                   "--format", "bestaudio/best",
                   "--extract-audio", "--audio-format", "wav",
                   "--output", template, url]

        saved_path  = None
        saved_title = None

        # ── Phase tracking for multi-stage progress (Option B) ──
        is_mp4 = (fmt == "mp4")
        self._dl_phase_idx = -1    # incremented on each "[download] Destination:"
        self._in_post     = False  # in ffmpeg merge / audio extract
        self._last_prg    = time.time()
        self._indet_on    = False

        # Start indeterminate-fallback watchdog (Option D)
        self.after(1500, self._watchdog_stall)

        try:
            self._proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, creationflags=_NO_WINDOW,
            )
            for line in self._proc.stdout:
                line = line.rstrip()
                if not line:
                    continue

                # Phase detection
                if line.startswith("[download] Destination:"):
                    self._dl_phase_idx += 1
                    self._in_post = False
                elif ("[Merger]" in line or "Merging formats" in line
                        or "[ExtractAudio]" in line
                        or "[EmbedThumbnail]" in line
                        or "[Metadata]" in line):
                    self._in_post = True

                if line.startswith("PRG|"):
                    parts = line.split("|", 4)
                    if len(parts) == 5:
                        _, pct_s, spd_s, eta_s, title_s = parts
                        try:
                            raw_pct = float(pct_s.strip().rstrip("%"))
                        except ValueError:
                            raw_pct = 0.0
                        self._last_prg = time.time()
                        overall, label = self._weighted_pct(raw_pct, is_mp4)
                        self.after(0, self._on_progress,
                                   overall, label, spd_s.strip(),
                                   eta_s.strip(), title_s.strip())
                    continue

                # Bump bar to floor of post-processing range when we enter it
                if self._in_post:
                    floor = 90.0 if is_mp4 else 85.0
                    label = "Merging…" if is_mp4 else "Converting audio…"
                    self.after(0, self._bump_to_floor, floor, label)

                if "/" in line or os.sep in line:
                    candidate = Path(line)
                    if candidate.suffix:
                        saved_path  = line
                        saved_title = candidate.stem
                self.after(0, self._log, line, "info")

            self._proc.wait()

            if self._cancelled:
                self.after(0, self._on_dl_cancelled)
                return

            if self._proc.returncode == 0:
                if saved_path and saved_title:
                    self.after(0, self._add_history, saved_title, fmt, saved_path)
                self.after(0, self._on_dl_success, out_dir,
                           saved_title or "Video", saved_path)
            else:
                self.after(0, self._on_dl_error, "Download failed. Check the URL.")

        except Exception as e:
            if not self._cancelled:
                self.after(0, self._on_dl_error, str(e))
        finally:
            self._proc = None

    # ── Multi-stage weighted progress helpers ────────────────────────────────

    def _weighted_pct(self, raw_pct, is_mp4):
        """Map raw 0-100 within current phase onto a smooth overall 0-100 bar."""
        raw = max(0.0, min(100.0, raw_pct))
        if self._in_post:
            if is_mp4:
                return 90.0 + raw * 0.10, "Merging video + audio…"
            return 85.0 + raw * 0.15, "Converting audio…"
        if is_mp4:
            if self._dl_phase_idx <= 0:
                return raw * 0.70, "Downloading video"
            return 70.0 + raw * 0.20, "Downloading audio"
        # MP3 / WAV — single stream download
        return raw * 0.85, "Downloading audio"

    def _bump_to_floor(self, floor_pct, label):
        """When entering a post-process phase with no PRG, jump bar to the floor."""
        if self._indet_on:
            return  # let watchdog handle visuals
        current_frac = self._progress_bar.get()
        if current_frac * 100.0 < floor_pct:
            self._progress_bar.set(floor_pct / 100.0)
            self._pct_label.configure(text=f"{floor_pct:5.1f}%")
        self._dl_stats.configure(text=label)

    def _watchdog_stall(self):
        """If no progress in >2s, switch bar to indeterminate animation (Option D)."""
        if not self._proc or self._proc.poll() is not None:
            if self._indet_on:
                try:
                    self._progress_bar.stop()
                    self._progress_bar.configure(mode="determinate")
                except Exception:
                    pass
                self._indet_on = False
            return

        silence = time.time() - self._last_prg
        if silence > 2.0 and not self._indet_on:
            try:
                self._progress_bar.configure(mode="indeterminate")
                self._progress_bar.start()
                self._indet_on = True
            except Exception:
                pass
        elif silence <= 2.0 and self._indet_on:
            try:
                self._progress_bar.stop()
                self._progress_bar.configure(mode="determinate")
            except Exception:
                pass
            self._indet_on = False

        self.after(500, self._watchdog_stall)

    def _on_progress(self, pct, label, speed, eta, title):
        # If watchdog had us indeterminate, switch back to determinate now that
        # real progress is flowing again.
        if self._indet_on:
            try:
                self._progress_bar.stop()
                self._progress_bar.configure(mode="determinate")
            except Exception:
                pass
            self._indet_on = False
        self._progress_bar.set(pct / 100.0)
        self._pct_label.configure(text=f"{pct:5.1f}%")
        if title:
            self._dl_title.configure(text=title)
        stat_bits = [label, speed or None, f"ETA {eta}" if eta else None]
        self._dl_stats.configure(
            text="   ·   ".join(b for b in stat_bits if b))

    def _stop_indet(self):
        """Make sure the bar is back in determinate mode (used by end-of-run paths)."""
        if getattr(self, "_indet_on", False):
            try:
                self._progress_bar.stop()
                self._progress_bar.configure(mode="determinate")
            except Exception:
                pass
            self._indet_on = False

    def _on_dl_success(self, out_dir, title, saved_path=None):
        self._stop_indet()
        self._progress_bar.set(1.0)
        self._pct_label.configure(text="100.0%")
        self._dl_btn.configure(state="normal", text="Download")
        self._cancel_btn.configure(state="disabled")
        self._dl_stats.configure(text="Done.")
        self._log(f"\n✅  Saved to: {out_dir}", "success")
        notify("Download complete", f"{title} saved to {out_dir}")
        # Reveal the finished file in Explorer (highlighted), or just open the folder.
        self._reveal_in_explorer(saved_path, out_dir)

    def _reveal_in_explorer(self, file_path, folder):
        try:
            if sys.platform == "win32" and file_path and Path(file_path).exists():
                subprocess.Popen(
                    ["explorer", "/select,", str(Path(file_path))],
                    creationflags=_NO_WINDOW,
                )
            else:
                self._open_folder(folder)
        except Exception as e:
            self._log(f"⚠  Couldn't open folder: {e}", "warn")

    def _on_dl_error(self, msg):
        self._stop_indet()
        self._progress_bar.set(0)
        self._pct_label.configure(text="0.0%")
        self._dl_btn.configure(state="normal", text="Download")
        self._cancel_btn.configure(state="disabled")
        self._dl_title.configure(text="")
        self._dl_stats.configure(text="")
        self._log(f"\n❌  {msg}", "error")

    def _on_dl_cancelled(self):
        self._stop_indet()
        self._progress_bar.set(0)
        self._pct_label.configure(text="0.0%")
        self._dl_btn.configure(state="normal", text="Download")
        self._cancel_btn.configure(state="disabled")
        self._dl_title.configure(text="")
        self._dl_stats.configure(text="")
        self._log("\n⚠  Download cancelled.", "warn")

    # ─────────────────────────────────────────────────────────────────────────
    #  UPDATE YT-DLP
    # ─────────────────────────────────────────────────────────────────────────

    def _update_ytdlp(self):
        self._tabs.set("Download")
        self._log("⟳  Checking for yt-dlp update…", "info")
        cflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        threading.Thread(target=self._run_update, args=(cflags,), daemon=True).start()

    def _run_update(self, cflags):
        try:
            python_exe = sys.executable
            if getattr(sys, "frozen", False):
                python_exe = shutil.which("python") or shutil.which("py")
                if not python_exe:
                    self.after(0, self._log,
                               "❌  Couldn't find a Python install to run pip. "
                               "Install Python, or update yt-dlp manually: "
                               "pip install --upgrade yt-dlp", "error")
                    return
            proc = subprocess.Popen(
                [python_exe, "-m", "pip", "install", "--upgrade", "yt-dlp"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, creationflags=cflags,
            )
            for line in proc.stdout:
                self.after(0, self._log, line.rstrip(), "info")
            proc.wait()
            tag = "success" if proc.returncode == 0 else "error"
            msg = ("✅  yt-dlp is up to date." if proc.returncode == 0
                   else "❌  yt-dlp update failed.")
            self.after(0, self._log, msg, tag)
        except Exception as e:
            self.after(0, self._log, f"Update error: {e}", "error")


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = App()
    app.mainloop()
