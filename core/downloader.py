import os
import time
import uuid
import shutil
import requests
import threading
import logging
import random
from pathlib import Path
log = logging.getLogger("BunkrV2.Downloader")
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]
class BunkrDownloader:
    def __init__(self, config_manager):
        self.config = config_manager
        self._abort_requested = False
        self._skipped_hosts = set()
        self._lock = threading.Lock()
    def rand_ua(self):
        return random.choice(USER_AGENTS)
    def get_proxies(self):
        return None
    def get_headers(self, referer="https://bunkr.cr/"):
        return {
            "User-Agent": self.rand_ua(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Referer": referer,
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
    def download_file(self, url, dest_dir, filename, referer, progress_callback=None, abort_callback=None):
        retries = self.config.get("error_handling", "max_retries")
        temp_file = dest_dir / f"{filename}.part"
        downloaded_bytes = 0
        total_size = 0
        for attempt in range(retries):
            if self._abort_requested or (abort_callback and abort_callback()): return "aborted"
            try:
                headers = self.get_headers(referer)
                if downloaded_bytes > 0:
                    headers["Range"] = f"bytes={downloaded_bytes}-"
                with requests.get(url, headers=headers, stream=True, timeout=(15, 60),
                                 verify=False, proxies=self.get_proxies()) as r:
                    if r.status_code == 404:
                        return "failed_404"
                    if r.status_code == 416: break # Already finished
                    r.raise_for_status()
                    # Safety Check
                    ctype = r.headers.get("Content-Type", "").lower()
                    if "text/html" in ctype or "application/json" in ctype:
                        return "invalid_content"
                    # Size info
                    if downloaded_bytes == 0:
                        total_size = int(r.headers.get("Content-Length", 0))
                    else:
                        if r.status_code != 206:
                            downloaded_bytes = 0
                            total_size = int(r.headers.get("Content-Length", 0))
                        else:
                            cr = r.headers.get("Content-Range", "")
                            if "/" in cr: total_size = int(cr.split("/")[-1])
                    mode = "ab" if downloaded_bytes > 0 else "wb"
                    start_time = time.time()
                    chunk_start_time = time.time()
                    with open(temp_file, mode) as f:
                        for chunk in r.iter_content(chunk_size=65536): # 64KB chunks
                            if self._abort_requested or (abort_callback and abort_callback()): break
                            if chunk:
                                f.write(chunk)
                                ln = len(chunk)
                                downloaded_bytes += ln
                                # Speed Limiter
                                limit = self.config.get("speed", "download_speed_limit") # KB/s
                                if limit > 0:
                                    elapsed = time.time() - chunk_start_time
                                    expected = ln / (limit * 1024)
                                    if elapsed < expected:
                                        time.sleep(expected - elapsed)
                                    chunk_start_time = time.time()
                                if progress_callback:
                                    duration = time.time() - start_time
                                    speed = downloaded_bytes / duration if duration > 0 else 0
                                    progress_callback(downloaded_bytes, total_size, speed)
                    if self._abort_requested or (abort_callback and abort_callback()):
                        return "aborted"
                    final_path = dest_dir / filename
                    shutil.move(str(temp_file), str(final_path))
                    return "success"
            except Exception as e:
                log.warning(f"Connection error (Attempt {attempt+1}): {e}")
                if attempt < retries - 1:
                    sleep_time = 15 if any(code in str(e) for code in ["429", "522"]) else 5
                    for _ in range(sleep_time):
                        if self._abort_requested or (abort_callback and abort_callback()):
                            return "aborted"
                        time.sleep(1)
                else:
                    if temp_file.exists(): temp_file.unlink()
                    return f"error: {str(e)}"
        return "failed"
