"""
Pinterest Board Saver
tkinter UI + gallery-dl 래퍼
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import json
import os
from pathlib import Path
from downloader import PinterestDownloader

CONFIG_FILE = Path.home() / ".pinterest_saver_config.json"


def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"urls": [], "save_dir": str(Path.home() / "Downloads" / "Pinterest")}


def save_config(cfg: dict):
    CONFIG_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("📌 PIC — Pinterest Image Crawler")
        self.resizable(False, False)
        self.configure(bg="#1a1a1a")

        self.cfg = load_config()
        self.downloader: PinterestDownloader | None = None
        self.is_running = False

        self._build_ui()
        self._load_url_list()

    # ── UI 구성 ──────────────────────────────────────
    def _build_ui(self):
        PAD = dict(padx=12, pady=6)
        BG  = "#1a1a1a"
        FG  = "#eeeeee"
        ACC = "#e60023"   # Pinterest red
        ENT = "#2a2a2a"

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame",       background=BG)
        style.configure("TLabel",       background=BG, foreground=FG, font=("Helvetica", 11))
        style.configure("TButton",      background="#333", foreground=FG, font=("Helvetica", 10))
        style.configure("Accent.TButton", background=ACC, foreground="white", font=("Helvetica", 11, "bold"))
        style.configure("TEntry",       fieldbackground=ENT, foreground=FG, insertcolor=FG)
        style.configure("TProgressbar", troughcolor="#333", background=ACC)

        root = ttk.Frame(self, padding=16)
        root.pack(fill="both", expand=True)

        # 타이틀
        ttk.Label(root, text="📌  PIC — Pinterest Image Crawler",
                  font=("Helvetica", 15, "bold"), foreground=ACC).pack(anchor="w", pady=(0, 10))

        # URL 입력
        ttk.Label(root, text="보드 URL").pack(anchor="w")
        url_row = ttk.Frame(root)
        url_row.pack(fill="x", pady=(2, 4))
        self.url_entry = tk.Entry(url_row, width=46, bg="#2a2a2a", fg="#eee", insertbackground="#eee")
        self.url_entry.focus_set()
        self.url_entry.bind("<Command-v>", lambda e: self.url_entry.event_generate("<<Paste>>"))
        self.url_entry.bind("<Command-c>", lambda e: self.url_entry.event_generate("<<Copy>>"))
        self.url_entry.bind("<Command-a>", lambda e: self.url_entry.select_range(0, "end"))
        self.url_entry.pack(side="left", expand=True, fill="x")
        self.url_entry.bind("<Return>", lambda e: self._add_url())
        ttk.Button(url_row, text="+ 추가", command=self._add_url).pack(side="left", padx=(6, 0))
        ttk.Button(url_row, text="목록 불러오기", command=self._load_txt).pack(side="left", padx=(4, 0))

        # URL 목록
        ttk.Label(root, text="URL 목록").pack(anchor="w", pady=(6, 0))
        list_frame = ttk.Frame(root)
        list_frame.pack(fill="both", expand=True)
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side="right", fill="y")
        self.url_list = tk.Listbox(list_frame, height=7, bg="#222", fg=FG,
                                   selectbackground=ACC, activestyle="none",
                                   yscrollcommand=scrollbar.set, font=("Helvetica", 10))
        self.url_list.pack(fill="both", expand=True)
        scrollbar.config(command=self.url_list.yview)
        ttk.Button(root, text="선택 삭제", command=self._delete_url).pack(anchor="e", pady=(2, 8))

        # 저장 폴더
        ttk.Label(root, text="저장 폴더").pack(anchor="w")
        dir_row = ttk.Frame(root)
        dir_row.pack(fill="x", pady=(2, 10))
        self.dir_var = tk.StringVar(value=self.cfg.get("save_dir", ""))
        ttk.Entry(dir_row, textvariable=self.dir_var, width=44).pack(side="left", expand=True, fill="x")
        ttk.Button(dir_row, text="찾기", command=self._pick_dir).pack(side="left", padx=(6, 0))

        # 진행상황
        ttk.Label(root, text="진행상황").pack(anchor="w")
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(root, variable=self.progress_var,
                                             maximum=100, style="TProgressbar", length=440)
        self.progress_bar.pack(fill="x", pady=(2, 2))
        self.progress_label = ttk.Label(root, text="대기 중...", foreground="#aaa")
        self.progress_label.pack(anchor="w", pady=(0, 10))

        # 로그
        self.log_text = tk.Text(root, height=6, bg="#111", fg="#aaa",
                                font=("Courier", 9), state="disabled", wrap="word")
        self.log_text.pack(fill="x", pady=(0, 10))

        # 버튼
        btn_row = ttk.Frame(root)
        btn_row.pack(fill="x")
        self.start_btn = ttk.Button(btn_row, text="  시작  ", style="Accent.TButton",
                                    command=self._start)
        self.start_btn.pack(side="left", padx=(0, 8))
        self.stop_btn  = ttk.Button(btn_row, text="  중단  ", command=self._stop, state="disabled")
        self.stop_btn.pack(side="left")

    # ── URL 관리 ─────────────────────────────────────
    def _add_url(self):
        url = self.url_entry.get().strip()
        if not url:
            return
        if not url.startswith("http"):
            messagebox.showwarning("URL 오류", "http(s)로 시작하는 Pinterest URL을 입력하세요.")
            return
        existing = list(self.url_list.get(0, "end"))
        if url in existing:
            messagebox.showinfo("중복", "이미 목록에 있는 URL입니다.")
            return
        self.url_list.insert("end", url)
        self.url_entry.delete(0, "end")
        self._persist_urls()

    def _delete_url(self):
        sel = self.url_list.curselection()
        for i in reversed(sel):
            self.url_list.delete(i)
        self._persist_urls()

    def _load_txt(self):
        path = filedialog.askopenfilename(filetypes=[("텍스트 파일", "*.txt"), ("모든 파일", "*.*")])
        if not path:
            return
        lines = Path(path).read_text(encoding="utf-8").splitlines()
        added = 0
        existing = list(self.url_list.get(0, "end"))
        for line in lines:
            url = line.strip()
            if url.startswith("http") and url not in existing:
                self.url_list.insert("end", url)
                existing.append(url)
                added += 1
        self._persist_urls()
        messagebox.showinfo("불러오기 완료", f"{added}개 URL이 추가됐어요.")

    def _load_url_list(self):
        for url in self.cfg.get("urls", []):
            self.url_list.insert("end", url)

    def _persist_urls(self):
        self.cfg["urls"] = list(self.url_list.get(0, "end"))
        save_config(self.cfg)

    def _pick_dir(self):
        d = filedialog.askdirectory()
        if d:
            self.dir_var.set(d)
            self.cfg["save_dir"] = d
            save_config(self.cfg)

    # ── 다운로드 제어 ─────────────────────────────────
    def _start(self):
        urls = list(self.url_list.get(0, "end"))
        if not urls:
            messagebox.showwarning("URL 없음", "URL을 추가해주세요.")
            return
        save_dir = self.dir_var.get().strip()
        if not save_dir:
            messagebox.showwarning("폴더 없음", "저장 폴더를 선택해주세요.")
            return

        self.cfg["save_dir"] = save_dir
        save_config(self.cfg)

        self.is_running = True
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.progress_var.set(0)
        self._log_clear()

        self.downloader = PinterestDownloader(
            urls=urls,
            save_dir=save_dir,
            on_progress=self._on_progress,
            on_log=self._on_log,
            on_done=self._on_done,
        )
        threading.Thread(target=self.downloader.run, daemon=True).start()

    def _stop(self):
        if self.downloader:
            self.downloader.stop()
        self._on_log("⏹ 중단 요청...")

    def _on_progress(self, current: int, total: int, board: str):
        pct = (current / total * 100) if total > 0 else 0
        self.progress_var.set(pct)
        self.progress_label.config(
            text=f"{board}  —  {current} / {total}장  ({pct:.0f}%)"
        )

    def _on_log(self, msg: str):
        self.log_text.config(state="normal")
        self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def _on_done(self, success: bool):
        self.is_running = False
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        if success:
            self.progress_var.set(100)
            self._on_log("✅ 완료!")
            self.progress_label.config(text="완료!")
        else:
            self._on_log("⏹ 중단됨.")
            self.progress_label.config(text="중단됨.")

    def _log_clear(self):
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.config(state="disabled")


if __name__ == "__main__":
    app = App()
    app.mainloop()
