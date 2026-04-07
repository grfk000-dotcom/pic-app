"""
PinterestDownloader — gallery-dl subprocess 래퍼
보드 이름별 폴더 자동 분리 저장
"""

import subprocess
import threading
import re
import os
from pathlib import Path
from typing import Callable


def _board_name_from_url(url: str) -> str:
    """pinterest.com/user/board-name/ → board-name"""
    url = url.rstrip("/")
    parts = url.split("/")
    # pinterest.com/username/boardname 구조
    for i, p in enumerate(parts):
        if "pinterest" in p and i + 2 < len(parts):
            return parts[i + 2]
    return parts[-1] if parts else "board"


class PinterestDownloader:
    def __init__(
        self,
        urls: list[str],
        save_dir: str,
        on_progress: Callable[[int, int, str], None],
        on_log: Callable[[str], None],
        on_done: Callable[[bool], None],
    ):
        self.urls       = urls
        self.save_dir   = save_dir
        self.on_progress = on_progress
        self.on_log     = on_log
        self.on_done    = on_done
        self._proc: subprocess.Popen | None = None
        self._stop_flag = threading.Event()

    def stop(self):
        self._stop_flag.set()
        if self._proc:
            try:
                self._proc.kill()
            except Exception:
                pass

    def run(self):
        try:
            for idx, url in enumerate(self.urls):
                if self._stop_flag.is_set():
                    break

                board = _board_name_from_url(url)
                dest  = str(Path(self.save_dir) / board)
                os.makedirs(dest, exist_ok=True)

                self.on_log(f"\n📌 [{idx+1}/{len(self.urls)}] {board}")
                self.on_log(f"   → {dest}")
                self.on_progress(0, 1, board)

                cmd = [
                    "gallery-dl",
                    "--dest", dest,
                    "--no-mtime",
                    "-v",
                    url,
                ]

                self._proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )

                total   = 0
                current = 0

                for line in self._proc.stdout:
                    if self._stop_flag.is_set():
                        self._proc.kill()
                        break

                    line = line.rstrip()
                    self.on_log(line)

                    # 총 개수 파악 (gallery-dl: "Downloading X files")
                    m = re.search(r'(\d+)\s+files?', line, re.I)
                    if m:
                        total = int(m.group(1))

                    # 다운로드 진행 (gallery-dl: "[download] filename")
                    if line.strip().startswith("[download]") or ".jpg" in line or ".png" in line or ".webp" in line:
                        current += 1
                        if total > 0:
                            self.on_progress(current, total, board)
                        else:
                            self.on_progress(current, max(current, 1), board)

                self._proc.wait()

            success = not self._stop_flag.is_set()
            self.on_done(success)

        except FileNotFoundError:
            self.on_log("❌ gallery-dl을 찾을 수 없어요. 설치 확인: pip install gallery-dl")
            self.on_done(False)
        except Exception as e:
            self.on_log(f"❌ 오류: {e}")
            self.on_done(False)
