import customtkinter as ctk
from PIL import Image
import os
import threading
import re
import html
import json
from tkinter import filedialog, ttk
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import logging
class BunkrApp(ctk.CTk):
    def __init__(self, config_manager, scraper, downloader):
        super().__init__()
        self.config_manager = config_manager
        self.scraper = scraper
        self.downloader = downloader
        self.title("Bunker Downloader")
        self.geometry("730x650")
        self.minsize(700, 600)
        ctk.set_appearance_mode(self.config_manager.get("ui", "theme"))
        ctk.set_default_color_theme("blue")
        # Grid Layout
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.sidebar_frame = ctk.CTkFrame(self, width=140, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(4, weight=1)
        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="Bunker Downloader", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))
        self.btn_download = ctk.CTkButton(self.sidebar_frame, text="Downloader", command=self.show_download_frame)
        self.btn_download.grid(row=1, column=0, padx=20, pady=10)
        self.btn_history = ctk.CTkButton(self.sidebar_frame, text="Downloads", command=self.show_history_frame)
        self.btn_history.grid(row=2, column=0, padx=20, pady=10)
        self.btn_settings = ctk.CTkButton(self.sidebar_frame, text="Settings", command=self.show_settings_frame)
        self.btn_settings.grid(row=3, column=0, padx=20, pady=10)
        
        self.theme_switch = ctk.CTkSwitch(self.sidebar_frame, text="Dark Theme", command=self.toggle_theme)
        self.theme_switch.grid(row=5, column=0, padx=20, pady=(20, 20), sticky="s")
        if self.config_manager.get("ui", "theme") == "dark":
            self.theme_switch.select()
        else:
            self.theme_switch.deselect()
            self.theme_switch.configure(text="Light Theme")
        self.download_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.setup_download_ui()
        self.history_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.setup_history_ui()
        # --- Ayarlar Paneli ---
        self.settings_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.setup_settings_ui()
        self.show_download_frame()
        self.download_queue = []
        self.is_downloading = False
        self.is_paused = False
        self._executor = None
        self.link_scan_queue = []
        self.is_scanning = False
        self.captured_file = Path("auto_captured_links.txt")
        dl_path = Path(self.config_manager.get("paths", "download_path"))
        dl_path.mkdir(exist_ok=True)
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
    def toggle_theme(self):
        if self.theme_switch.get() == 1:
            theme = "dark"
            self.theme_switch.configure(text="Dark Theme")
        else:
            theme = "light"
            self.theme_switch.configure(text="Light Theme")
        ctk.set_appearance_mode(theme)
        self.config_manager.set("ui", "theme", theme)

    def on_closing(self):
        if getattr(self, "is_downloading", False) and not getattr(self, "is_paused", False):
            self.toggle_pause()
        try:
            self.scraper.quit_drivers()
        except Exception:
            pass
        try:
            import ctypes
            ctypes.windll.kernel32.FreeConsole()
        except Exception:
            pass
        self.destroy()
        import os
        os._exit(0)
    def setup_download_ui(self):
        self.url_label = ctk.CTkLabel(self.download_frame, text="Bunker Album / File URL:", font=ctk.CTkFont(size=14))
        self.url_label.grid(row=0, column=0, padx=20, pady=(20, 0), sticky="w")
        self.url_entry = ctk.CTkEntry(self.download_frame, placeholder_text="https://bunkr.cr/a/...", width=500)
        self.url_entry.grid(row=1, column=0, padx=20, pady=10, sticky="ew", columnspan=2)
        self.button_frame = ctk.CTkFrame(self.download_frame, fg_color="transparent")
        self.button_frame.grid(row=2, column=0, columnspan=2, padx=20, pady=10, sticky="ew")
        self.url_entry.bind("<Return>", lambda event: self.handle_start_btn())
        self.btn_start_dl = ctk.CTkButton(self.button_frame, text="Start Download", width=120, fg_color="green", hover_color="darkgreen", command=self.handle_start_btn)
        self.btn_start_dl.pack(side="left", padx=(0, 10))
        self.btn_pause_dl = ctk.CTkButton(self.button_frame, text="Pause", width=100, fg_color="#C0392B", hover_color="#922B21", command=self.toggle_pause, state="disabled")
        self.btn_pause_dl.pack(side="left", padx=(0, 10))
        self.btn_txt = ctk.CTkButton(self.button_frame, text="Add from TXT", width=100, command=self.load_from_txt)
        self.btn_txt.pack(side="left", padx=(0, 10))
        self.download_frame.grid_columnconfigure(0, weight=1)
        self.download_frame.grid_rowconfigure(3, weight=1)
        self.dl_tree_frame = ctk.CTkFrame(self.download_frame)
        self.dl_tree_frame.grid(row=3, column=0, padx=(20, 10), pady=10, sticky="nsew")


        from tkinter import ttk
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview", background="#2b2b2b", foreground="white", fieldbackground="#2b2b2b", borderwidth=0)
        style.map("Treeview", background=[('selected', '#1f538d')])
        self.dl_tree = ttk.Treeview(self.dl_tree_frame, columns=("name", "size", "progress", "speed", "path"), show="tree headings", height=8)
        self.dl_tree.heading("#0", text="Album / File Name")
        self.dl_tree.heading("name", text="File")
        self.dl_tree.heading("size", text="Size")
        self.dl_tree.heading("progress", text="%")
        self.dl_tree.heading("speed", text="Speed")
        self.dl_tree.column("#0", width=250)
        self.dl_tree.column("name", width=0, stretch=False)
        self.dl_tree.column("size", width=80, anchor="center")
        self.dl_tree.column("progress", width=60, anchor="center")
        self.dl_tree.column("speed", width=80, anchor="center")
        self.dl_tree["displaycolumns"] = ("size", "progress", "speed")
        self.dl_tree.pack(side="left", fill="both", expand=True)
        self.dl_tree.bind("<Double-1>", self._on_dl_tree_double_click)
        self.dl_tree_scroll = ctk.CTkScrollbar(self.dl_tree_frame, command=self.dl_tree.yview)
        self.dl_tree_scroll.pack(side="right", fill="y")
        self.dl_tree.configure(yscrollcommand=self.dl_tree_scroll.set)
        # Bilgi ve Durum Log TextBox (Altta)
        self.status_box = ctk.CTkTextbox(self.download_frame, height=120)
        self.status_box.grid(row=4, column=0, columnspan=2, padx=20, pady=(0, 10), sticky="nsew")
    def _on_dl_tree_double_click(self, event):
        selected = self.dl_tree.selection()
        if not selected: return
        vals = self.dl_tree.item(selected[0])["values"]
        if len(vals) >= 5:
            p = vals[4]
            # When path contains spaces, tkinter split sometimes might need handling, but values dict is exact python dict
            if p and Path(p).exists():
                os.startfile(p)
    def setup_history_ui(self):
        from tkinter import ttk
        self.hist_label = ctk.CTkLabel(self.history_frame, text="Downloaded Files", font=ctk.CTkFont(size=16, weight="bold"))
        self.hist_label.pack(pady=10)
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview", background="#2b2b2b", foreground="white", fieldbackground="#2b2b2b", borderwidth=0)
        style.map("Treeview", background=[('selected', '#1f538d')])
        # Treeview ve Scrollbar
        self.tree_frame = ctk.CTkFrame(self.history_frame)
        self.tree_frame.pack(fill="both", expand=True, padx=20, pady=10)
        self.tree = ttk.Treeview(self.tree_frame, columns=("path", "time", "size", "raw_time", "raw_size"), show="tree headings")
        self.tree.heading("#0", text="Album / File Name", command=lambda: self.sort_tree("#0", False))
        self.tree.heading("time", text="Download Time", command=lambda: self.sort_tree("time", False))
        self.tree.heading("size", text="Size", command=lambda: self.sort_tree("size", False))
        self.tree.column("#0", width=400)
        self.tree.column("time", width=150, anchor="center")
        self.tree.column("size", width=100, anchor="center")
        self.tree["displaycolumns"] = ("time", "size") # Hide raw data
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree_scroll = ctk.CTkScrollbar(self.tree_frame, command=self.tree.yview)
        self.tree_scroll.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=self.tree_scroll.set)
        self.tree.bind("<Double-1>", self._on_tree_double_click)
        self.hist_btn_frame = ctk.CTkFrame(self.history_frame, fg_color="transparent")
        self.hist_btn_frame.pack(fill="x", padx=20, pady=10)
        self.btn_open_file = ctk.CTkButton(self.hist_btn_frame, text="Open File", command=self.open_selected_file)
        self.btn_open_file.pack(side="left", padx=5)
        self.btn_open_folder = ctk.CTkButton(self.hist_btn_frame, text="Open Folder", command=self.open_selected_folder)
        self.btn_open_folder.pack(side="left", padx=5)
        self.btn_refresh_hist = ctk.CTkButton(self.hist_btn_frame, text="Refresh", width=100, command=self.refresh_history)
        self.btn_refresh_hist.pack(side="right", padx=5)
        self.btn_clear_hist = ctk.CTkButton(self.hist_btn_frame, text="Clear List", width=100, fg_color="#e67e22", hover_color="#d35400", command=self.clear_history)
        self.btn_clear_hist.pack(side="right", padx=5)
    def clear_history(self):
        from tkinter import messagebox
        ans = messagebox.askyesno("Clear List", "Download history will be cleared (files will NOT BE DELETED FROM DISK). Confirm?", parent=self)
        if not ans: return
        hidden = []
        try:
            if Path("hidden_history.json").exists():
                with open("hidden_history.json", "r", encoding="utf-8") as f:
                    hidden = json.load(f)
        except: pass
        for item in self.tree.get_children():
            vals = self.tree.item(item).get("values")
            if vals:
                p = str(vals[0])
                if p not in hidden:
                    hidden.append(p)
        with open("hidden_history.json", "w", encoding="utf-8") as f:
            json.dump(hidden, f, indent=2, ensure_ascii=False)
        self.refresh_history()
        self.log_status("🧹 Download history cleared.")
    def sort_tree(self, col, reverse):
        col_map = {"time": 3, "size": 4}
        def sort_level(parent):
            children = list(self.tree.get_children(parent))
            if not children: return
            for child in children:
                sort_level(child)
            values_list = []
            for child in children:
                if col == "#0":
                    val = self.tree.item(child, "text").lower()
                else:
                    try:
                        val = float(self.tree.item(child, "values")[col_map[col]])
                    except:
                        val = 0.0
                values_list.append((val, child))
            values_list.sort(reverse=reverse)
            for index, (val, child) in enumerate(values_list):
                self.tree.move(child, parent, index)
        sort_level("")
        self.tree.heading(col, command=lambda: self.sort_tree(col, not reverse))
    def refresh_history(self):
        import math
        from datetime import datetime
        def format_size(size_bytes):
            if size_bytes == 0: return "0 B"
            sizes = ["B", "KB", "MB", "GB", "TB"]
            i = int(math.floor(math.log(size_bytes, 1024)))
            p = math.pow(1024, i)
            s = round(size_bytes / p, 2)
            return f"{s} {sizes[i]}"
        # Treeview'i Temizle
        for item in self.tree.get_children():
            self.tree.delete(item)
        hidden = []
        try:
            if Path("hidden_history.json").exists():
                with open("hidden_history.json", "r", encoding="utf-8") as f:
                    hidden = json.load(f)
        except: pass
        dl_path = Path(self.config_manager.get("paths", "download_path"))
        if not dl_path.exists(): return
        albums = []
        for album_dir in dl_path.iterdir():
            if album_dir.is_dir() and str(album_dir) not in hidden:
                try:
                    a_time = album_dir.stat().st_mtime
                    a_size = sum(f.stat().st_size for f in album_dir.iterdir() if f.is_file())
                    albums.append((album_dir, a_time, a_size))
                except Exception:
                    pass
        # Sort by latest by default
        albums.sort(key=lambda x: x[1], reverse=True)
        failed_entries = []
        for album_dir, a_time, a_size in albums:
            dt_str = datetime.fromtimestamp(a_time).strftime("%Y-%m-%d %H:%M:%S")
            files = []
            try:
                for f in album_dir.iterdir():
                    if f.is_file():
                        files.append((f, f.stat().st_mtime, f.stat().st_size))
            except Exception:
                pass
            downloaded_count = len(files)
            failed_count = sum(1 for en in failed_entries if en.get("album") == album_dir.name)
            total_count = downloaded_count + failed_count
            if total_count < downloaded_count:
                total_count = downloaded_count
            status_text = f" ({downloaded_count}/{total_count} Successful)" if total_count > 0 else " (Empty)"
            album_node = self.tree.insert("", "end", text=f"📂 {album_dir.name}{status_text}", open=False, values=(str(album_dir), dt_str, format_size(a_size), a_time, a_size))
            files.sort(key=lambda x: x[1], reverse=True)
            for f, f_time, f_size in files:
                f_dt_str = datetime.fromtimestamp(f_time).strftime("%Y-%m-%d %H:%M:%S")
                self.tree.insert(album_node, "end", text=f"📄 {f.name}", values=(str(f), f_dt_str, format_size(f_size), f_time, f_size))
    def _on_tree_double_click(self, event):
        self.open_selected_file()
    def open_selected_file(self):
        selected = self.tree.selection()
        if not selected: return
        path_str = self.tree.item(selected[0])["values"][0]
        p = Path(path_str)
        if p.is_file():
            os.startfile(p)
    def open_selected_folder(self):
        selected = self.tree.selection()
        if not selected: return
        path_str = self.tree.item(selected[0])["values"][0]
        p = Path(path_str)
        if p.is_file():
            os.startfile(p.parent)
        else:
            os.startfile(p)
    def show_download_frame(self):
        self.settings_frame.grid_forget()
        self.history_frame.grid_forget()
        self.download_frame.grid(row=0, column=1, sticky="nsew")
    def show_history_frame(self):
        self.download_frame.grid_forget()
        self.settings_frame.grid_forget()
        self.history_frame.grid(row=0, column=1, sticky="nsew")
        self.refresh_history()
    def show_settings_frame(self):
        self.download_frame.grid_forget()
        self.history_frame.grid_forget()
        self.settings_frame.grid(row=0, column=1, sticky="nsew")

    def setup_settings_ui(self):
        self.settings_tabview = ctk.CTkTabview(self.settings_frame)
        self.settings_tabview.pack(fill="both", expand=True, padx=20, pady=20)
        # Sekmeleri Ekle
        self.settings_tabview.add("Speed")
        self.settings_tabview.add("Error Handling")
        self.settings_tabview.add("Paths")
        tab_speed = self.settings_tabview.tab("Speed")
        current_kb = self.config_manager.get('speed', 'download_speed_limit')
        current_mbit = int(current_kb / 125)
        lbl_limit = ctk.CTkLabel(tab_speed, text=f"Download Speed Limit: {current_mbit} Mbit/s {'(Unlimited)' if current_mbit == 0 else ''}")
        lbl_limit.pack(pady=(10, 0), anchor="w")
        def update_limit_label(val):
            mbit = int(val)
            limit_text = f"Download Speed Limit: {mbit} Mbit/s" if mbit > 0 else "Download Speed Limit: Unlimited"
            lbl_limit.configure(text=limit_text)
            self.config_manager.set("speed", "download_speed_limit", mbit * 125)
        self.speed_slider = ctk.CTkSlider(tab_speed, from_=0, to=100, number_of_steps=100, command=update_limit_label)
        self.speed_slider.pack(pady=5, fill="x")
        self.speed_slider.set(current_mbit)
        # Extraction Workers
        lbl_ext = ctk.CTkLabel(tab_speed, text="Extraction Workers:")
        lbl_ext.pack(pady=(15, 0), anchor="w")
        self.ext_workers = ctk.CTkSegmentedButton(tab_speed, values=["1", "2", "4", "8", "16"],
                                               command=lambda v: self.config_manager.set("speed", "max_extraction_workers", int(v)))
        self.ext_workers.pack(pady=5, fill="x")
        self.ext_workers.set(str(self.config_manager.get("speed", "max_extraction_workers")))
        # Download Workers
        lbl_dl = ctk.CTkLabel(tab_speed, text="Concurrent Downloads:")
        lbl_dl.pack(pady=(15, 0), anchor="w")
        self.dl_workers = ctk.CTkSegmentedButton(tab_speed, values=["1", "2", "4", "8", "16"],
                                               command=lambda v: self.config_manager.set("speed", "max_download_workers", int(v)))
        self.dl_workers.pack(pady=5, fill="x")
        self.dl_workers.set(str(self.config_manager.get("speed", "max_download_workers")))

        tab_error = self.settings_tabview.tab("Error Handling")
        # Max Retries
        lbl_ret = ctk.CTkLabel(tab_error, text="Manual Retries on Error:")
        lbl_ret.pack(pady=(10, 0), anchor="w")
        self.retry_entry = ctk.CTkSegmentedButton(tab_error, values=["1", "3", "5", "10", "20"],
                                                command=lambda v: self.config_manager.set("error_handling", "max_retries", int(v)))
        self.retry_entry.pack(pady=5, fill="x")
        self.retry_entry.set(str(self.config_manager.get("error_handling", "max_retries")))
        self.sw_404 = ctk.CTkSwitch(tab_error, text="Abort Album on 404 Errors",
                                   command=lambda: self.config_manager.set("error_handling", "abort_on_404", self.sw_404.get()))
        self.sw_404.pack(pady=15, anchor="w")
        if self.config_manager.get("error_handling", "abort_on_404"): self.sw_404.select()
        self.sw_skip = ctk.CTkSwitch(tab_error, text="Skip Bad Servers",
                                    command=lambda: self.config_manager.set("error_handling", "enable_server_skipping", self.sw_skip.get()))
        self.sw_skip.pack(pady=15, anchor="w")
        if self.config_manager.get("error_handling", "enable_server_skipping"): self.sw_skip.select()
        # --- Yollar Sekmesi ---
        tab_paths = self.settings_tabview.tab("Paths")
        lbl_path = ctk.CTkLabel(tab_paths, text="Download Folder:")
        lbl_path.pack(pady=(10, 0), anchor="w")
        path_frame = ctk.CTkFrame(tab_paths, fg_color="transparent")
        path_frame.pack(pady=5, fill="x", anchor="w")
        self.path_entry = ctk.CTkEntry(path_frame, width=350)
        self.path_entry.pack(side="left", padx=(0, 10))
        self.path_entry.insert(0, self.config_manager.get("paths", "download_path"))
        def browse_path():
            d = filedialog.askdirectory(initialdir=self.path_entry.get())
            if d:
                self.path_entry.delete(0, "end")
                self.path_entry.insert(0, d)
        btn_browse = ctk.CTkButton(path_frame, text="Browse", width=100, command=browse_path)
        btn_browse.pack(side="left")
        def save_path():
            self.config_manager.set("paths", "download_path", self.path_entry.get())
            self.log_status(f"📂 Download path updated: {self.path_entry.get()}")
        btn_save_path = ctk.CTkButton(tab_paths, text="Save Path", command=save_path)
        btn_save_path.pack(pady=10, anchor="w")
    def log_status(self, message):
        logging.info(message.replace("✅", "[SUCCESS]").replace("❌", "[ERROR]").replace("⚠️", "[WARNING]").replace("🛑", "[STOP]"))
        self.after(0, lambda: self._safe_log(message))
    def _safe_log(self, message):
        self.status_box.insert("end", f"{message}\n")
        self.status_box.see("end")
    def toggle_clipboard_watcher(self):
        self.clipboard_watching = self.sw_clipboard.get() == 1
        if self.clipboard_watching:
            self.log_status("👁️ Clipboard watcher ENABLED. (Auto-capture active)")
            self.check_clipboard()
        else:
            self.log_status("👁️ Clipboard watcher DISABLED.")
    def check_clipboard(self):
        if not self.clipboard_watching: return
        try:
            content = self.clipboard_get().strip()
            if content != self.last_clipboard and "http" in content and "bunkr" in content.lower():
                self.last_clipboard = content
                already_downloaded = False
                lines = []
                if self.captured_file.exists():
                    with open(self.captured_file, "r", encoding="utf-8") as f:
                        lines = [line.strip() for line in f]
                        if f"# {content}" in lines:
                            already_downloaded = True
                            self.log_status(f"⚠️ Caught from clipboard but already downloaded (skipped): {content}")
                if not already_downloaded:
                    if content not in lines and f"# {content}" not in lines:
                        with open(self.captured_file, "a", encoding="utf-8") as f:
                            f.write(content + "\n")
                    self.log_status(f"📋 Caught from clipboard: {content}")
                    if not getattr(self, "current_scanned_url", "") == content and not any(item[0] == content for item in self.link_scan_queue):
                        self.link_scan_queue.append((content, True, True)) # (url, auto_queue=True, auto_dl=True)
                        if not self.is_scanning:
                            self.after(500, self._process_scan_queue)
        except:
            pass
        self.after(1000, self.check_clipboard)
    def load_from_txt(self):
        fpath = filedialog.askopenfilename(title="Select Txt File", filetypes=[("Text Files", "*.txt")])
        if not fpath: return
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                lines = f.readlines()
            added = 0
            for line in lines:
                L = line.strip()
                if not L or L.startswith("#"):
                    continue
                if "bunkr" in L.lower() and "http" in L.lower():
                    if not getattr(self, "current_scanned_url", "") == L and not any(item[0] == L for item in self.link_scan_queue):
                        self.link_scan_queue.append((L, True, True))
                        added += 1
            if added > 0:
                self.log_status(f"📄 {added} new links added to queue from TXT file.")
                if not self.is_scanning:
                    self._process_scan_queue()
            else:
                self.log_status(f"⚠️ No new links could be added from selected TXT (all might be downloaded already).")
        except Exception as e:
            self.log_status(f"❌ TXT read error: {e}")
    def handle_add_queue_click(self):
        url = self.url_entry.get().strip()
        if not url: return
        if getattr(self, "current_scanned_url", "") == url and hasattr(self, "scanned_items") and self.scanned_items:
            self.add_to_queue()
        else:
            self.link_scan_queue.append((url, True, False))
            if not self.is_scanning:
                self._process_scan_queue()
    def handle_start_btn(self):
        url = self.url_entry.get().strip()
        if url:
            self.start_scan(auto_queue=True, auto_dl=True)
        elif self.download_queue:
            self.start_download()

    def start_scan(self, auto_queue=True, auto_dl=True):
        url = self.url_entry.get().strip()
        if not url: return
        self.link_scan_queue.append((url, auto_queue, auto_dl))
        if not self.is_scanning:
            self._process_scan_queue()
    def _process_scan_queue(self):
        if getattr(self, "is_scanning", False) or not self.link_scan_queue:
            return
        url, auto_queue, auto_dl = self.link_scan_queue.pop(0)
        self.is_scanning = True
        self.current_scanned_url = url
        self.auto_queue_pending = auto_queue
        self.auto_download_pending = auto_dl
        self.url_entry.delete(0, "end")
        self.url_entry.insert(0, url)
        self.status_box.delete("1.0", "end")
        self.log_status(f"🔍 Starting scan: {url}")
        self.btn_start_dl.configure(state="disabled")
        if hasattr(self, "btn_add_queue"):
            self.btn_add_queue.configure(state="disabled")
        threading.Thread(target=self._scan_thread, args=(url,), daemon=True).start()
    def _safe_name(self, s):
        """Cleans file names and fixes character encoding errors."""
        if not s: return "dosya"
        s = html.unescape(str(s))
        try:
            s = s.encode('latin-1').decode('utf-8')
        except: pass
        s = re.sub(r'[\\/*?:"<>|]', "_", s).strip(". ")
        return s[:200] or "dosya"
    def _scan_thread(self, url):
        try:
            res = self.scraper.scrape_album(url)
            if len(res) == 2:
                items, title = res
                album_id = url.rstrip("/").split("/")[-1]
            else:
                items, title, album_id = res
                if not album_id:
                    album_id = url.rstrip("/").split("/")[-1]
            title = self._safe_name(title)
            # Her bir dosya ismini temizle
            for item in items:
                item["name"] = self._safe_name(item["name"])
            self.scanned_items = items
            self.album_title = f"{title} - {album_id}"
            def check_and_continue():
                self.log_status(f"✅ Album Found: {self.album_title} ({len(items)} files)")
                self.btn_start_dl.configure(state="normal")
                if hasattr(self, "btn_add_queue"):
                    self.btn_add_queue.configure(state="normal")
                if items:
                    if getattr(self, "auto_queue_pending", False):
                        self.after(0, self.add_to_queue)
                        self.auto_queue_pending = False
                        if getattr(self, "auto_download_pending", False):
                            if not getattr(self, "is_downloading", False):
                                self.after(500, self.start_download)
                            self.auto_download_pending = False
                self.is_scanning = False
                self.after(500, self._process_scan_queue)
            self.after(0, check_and_continue)
        except Exception as e:
            self.log_status(f"❌ Scan error: {e}")
            def enable_btns():
                self.btn_start_dl.configure(state="normal")
                if hasattr(self, "btn_add_queue"):
                    self.btn_add_queue.configure(state="normal")
                self.is_scanning = False
                self.after(500, self._process_scan_queue)
            self.after(0, enable_btns)
    def _show_download_buttons(self):
        if hasattr(self, "btn_add_queue"):
            self.btn_add_queue.configure(state="normal")
        if hasattr(self, "btn_start_dl"):
            self.btn_start_dl.configure(state="normal")
    def add_to_queue(self):
        if hasattr(self, "scanned_items") and hasattr(self, "album_title") and self.scanned_items:
            for item in self.download_queue:
                if item["album_title"] == self.album_title:
                    existing_names = [i["name"] for i in item["scanned_items"]]
                    added_count = 0
                    for new_item in self.scanned_items:
                        if new_item["name"] not in existing_names:
                            item["scanned_items"].append(new_item)
                            added_count += 1
                    if added_count > 0:
                        self.log_status(f"✚ {added_count} new files added to '{self.album_title}' currently in queue. (Total: {len(item['scanned_items'])})")
                        for child in self.queue_tree.get_children():
                            if self.queue_tree.item(child)["values"][0] == self.album_title:
                                self.queue_tree.item(child, values=(self.album_title, len(item["scanned_items"])))
                                break
                    else:
                        self.log_status("⚠️ Scanned files already exist in queued album with same name.")
                    self.scanned_items = []
                    if hasattr(self, "btn_add_queue"):
                        self.btn_add_queue.configure(state="normal")
                    return
            self.download_queue.append({
                "album_title": self.album_title,
                "scanned_items": self.scanned_items,
                "original_url": getattr(self, "current_scanned_url", "")
            })
            self.queue_tree.insert("", "end", values=(self.album_title, len(self.scanned_items)))
            self.log_status(f"➕ Added to queue: {self.album_title} ({len(self.scanned_items)} files)")
            self.scanned_items = []
            if hasattr(self, "btn_add_queue"):
                self.btn_add_queue.configure(state="normal")
    def _on_queue_tree_right_click(self, event):
        iid = self.queue_tree.identify_row(event.y)
        if iid:
            self.queue_tree.selection_set(iid)
            self.queue_menu.tk_popup(event.x_root, event.y_root)
    def _on_queue_drag_start(self, event):
        row = self.queue_tree.identify_row(event.y)
        if row:
            self.queue_tree.selection_set(row)
            self._drag_data = {"item": row, "y": event.y}
        else:
            self._drag_data = None
    def _on_queue_drag_motion(self, event):
        if not getattr(self, "_drag_data", None):
            return
        dragged_item = self._drag_data["item"]
        target_item = self.queue_tree.identify_row(event.y)
        if not target_item or dragged_item == target_item:
            return
        target_index = self.queue_tree.index(target_item)
        self.queue_tree.move(dragged_item, "", target_index)
    def _on_queue_drag_release(self, event):
        if not getattr(self, "_drag_data", None):
            return
        self._drag_data = None
        self._sync_queue_from_tree()
    def _sync_queue_from_tree(self):
        """Synchronizes Treeview order with download_queue"""
        new_queue = []
        for iid in self.queue_tree.get_children():
            album_name = self.queue_tree.item(iid)["values"][0]
            for q in self.download_queue:
                if q["album_title"] == album_name:
                    new_queue.append(q)
                    break
        self.download_queue = new_queue
    def _move_queue_top(self):
        selected = self.queue_tree.selection()
        if not selected: return
        for s in selected:
            idx = self.queue_tree.index(s)
            if idx > 0:
                self.queue_tree.move(s, "", 0)
        self._sync_queue_from_tree()
    def _move_queue_up(self):
        selected = self.queue_tree.selection()
        if not selected: return
        for s in selected:
            idx = self.queue_tree.index(s)
            if idx > 0:
                self.queue_tree.move(s, "", idx - 1)
        self._sync_queue_from_tree()
    def _move_queue_down(self):
        selected = self.queue_tree.selection()
        if not selected: return
        for s in reversed(selected):
            idx = self.queue_tree.index(s)
            count = len(self.queue_tree.get_children())
            if idx < count - 1:
                self.queue_tree.move(s, "", idx + 1)
        self._sync_queue_from_tree()
    def _remove_from_queue(self):
        selected = self.queue_tree.selection()
        if not selected: return
        for s in selected:
            album_name = self.queue_tree.item(s)["values"][0]
            self.download_queue = [q for q in self.download_queue if q["album_title"] != album_name]
            self.queue_tree.delete(s)
            self.log_status(f"🗑️ Removed from queue: {album_name}")
    def start_download(self):
        if not self.download_queue:
            self.log_status("⚠️ Kuyrukta indirilecek dosya yok.")
            return
        if self.is_downloading and not self.is_paused:
            return
        self.is_downloading = True
        self.is_paused = False
        if hasattr(self, "btn_start_dl"):
            self.btn_start_dl.configure(state="disabled")
        if hasattr(self, "btn_pause_dl"):
            self.btn_pause_dl.configure(state="normal", text="Pause", fg_color="#C0392B", hover_color="#922B21")
        self.log_status("🚀 Starting download...")
        self._start_next_in_queue()
    def toggle_pause(self):
        if not self.is_downloading:
            return
        self.is_paused = not self.is_paused
        if self.is_paused:
            if hasattr(self, "btn_pause_dl"):
                self.btn_pause_dl.configure(text="Resume", fg_color="#F39C12", hover_color="#D68910")
            self.log_status("⏸️ Pausing download (will stop after current operations finish)...")
        else:
            if hasattr(self, "btn_pause_dl"):
                self.btn_pause_dl.configure(text="Pause", fg_color="#C0392B", hover_color="#922B21")
            self.log_status("▶️ Resuming download...")
            self._start_next_in_queue()
    def _start_next_in_queue(self):
        for el in self.dl_tree.get_children():
            self.dl_tree.delete(el)
        self.tree_items = {}
        threading.Thread(target=self._download_loop, daemon=True).start()
    def _download_loop(self):
        import time
        from concurrent.futures import ThreadPoolExecutor, wait
        from pathlib import Path
        max_workers = self.config_manager.get("speed", "max_download_workers")
        self.log_status(f"🚀 Smart Multi-Queue system started ({max_workers} concurrent workers)...")
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            self._executor = executor
            active_futures = set()
            active_contexts = []
            while self.is_downloading and not self.is_paused:
                while len(active_futures) < max_workers * 2 and self.download_queue:
                    current_job = self.download_queue.pop(0)
                    album_title = current_job["album_title"]
                    items = current_job["scanned_items"]
                    self.log_status(f"📂 Processing New Album: {album_title} ({len(items)} files)")
                    dest_parent = Path(self.config_manager.get("paths", "download_path"))
                    dest_dir = dest_parent / album_title
                    dest_dir.mkdir(parents=True, exist_ok=True)
                    ctx = {
                        "dest_dir": dest_dir,
                        "album_title": album_title,
                        "total_items": len(items),
                        "completed_count": 0,
                        "success_count": 0,
                        "fail_count": 0,
                        "abort_album": False,
                        "progress_lock": threading.Lock(),
                        "original_url": current_job.get("original_url", ""),
                        "ui_node": None
                    }
                    active_contexts.append(ctx)
                    def _update_q(t=album_title, itms=items, cx=ctx):
                        parent_id = self.dl_tree.insert("", "end", text=f"📂 {t}", values=(t, "-", "Processing Album", "", ""), open=True)
                        cx["ui_node"] = parent_id
                        for it in itms:
                            iid = self.dl_tree.insert(parent_id, "end", text=f"📄 {it['name']}", values=(it["name"], "-", "In Queue", "", ""))
                            self.tree_items[f"{t}_{it['name']}"] = iid
                    self.after(0, _update_q)
                    for i, item in enumerate(items, 1):
                        f = executor.submit(self._download_single_task, item, i, ctx)
                        active_futures.add(f)
                if not active_futures:
                    time.sleep(1)
                    if not self.download_queue:
                        break
                    continue
                done, not_done = wait(
                    active_futures, timeout=1.0)
                for f in done:
                    active_futures.remove(f)
        if self.is_paused:
            self.log_status("⏸️ Download paused.")
        else:
            self.is_downloading = False
            self.after(0, lambda: self.btn_start_dl.configure(state="normal"))
            self.after(0, lambda: self.btn_pause_dl.configure(state="disabled", text="Pause", fg_color="#C0392B"))
            self.log_status("✅ Entire download queue completed.")
            try:
                self.scraper.quit_drivers()
            except:
                pass
    def _download_single_task(self, item, index, ctx):
        name = item["name"]
        page = item["file_page"]
        dict_key = f"{ctx['album_title']}_{name}"
        item_id = self.tree_items.get(dict_key)
        with ctx["progress_lock"]:
            if ctx.get("abort_album", False) or ctx["fail_count"] >= 3:
                ctx["abort_album"] = True
                self.log_status(f"⏭️ Skipped (Too Many Errors): {name}")
                def _set_skipped():
                    if item_id and self.dl_tree.exists(item_id):
                        self.dl_tree.item(item_id, values=(name, "-", "Skipped", "", ""))
                self.after(0, _set_skipped)
                self._check_album_finished(ctx)
                return False
        self.log_status(f"[{index}/{ctx['total_items']}] Fetching CDN link for {name}...")
        def _set_connecting():
            if item_id and self.dl_tree.exists(item_id):
                self.dl_tree.item(item_id, values=(name, "-", "Connecting..", "", ""))
        self.after(0, _set_connecting)
        cdn_url = self.scraper.get_cdn_url(page)
        if not cdn_url:
            self.log_status(f"❌ CDN not found: {name}")
            def _set_cdn_err():
                if item_id and self.dl_tree.exists(item_id):
                    self.dl_tree.item(item_id, values=(name, "-", "CDN Error", "", ""))
            self.after(0, _set_cdn_err)
            with ctx["progress_lock"]:
                ctx["fail_count"] += 1
            self._check_album_finished(ctx)
            return False
        self.log_status(f"⬇️ Downloading {name}...")
        def progress_cb(dl_bytes, t_size, speed):
            pct = int((dl_bytes / t_size) * 100) if t_size > 0 else 0
            sp = f"{speed/1024:.1f} KB/s" if speed < 1024*1024 else f"{speed/(1024*1024):.1f} MB/s"
            size_str = f"{t_size/(1024*1024):.1f} MB" if t_size > 1024*1024 else f"{t_size/1024:.1f} KB" if t_size > 0 else "?"
            item["formatted_size"] = size_str
            def _update():
                if item_id and self.dl_tree.exists(item_id):
                    self.dl_tree.item(item_id, values=(name, size_str, f"%{pct}", sp, ""))
            self.after(0, _update)
        # Retry loop: 503 means CDN is temporarily unavailable — wait and retry
        import time as _time
        MAX_RETRIES = 4
        RETRY_DELAYS = [10, 30, 60, 120]  # seconds between each attempt
        res = None
        for attempt in range(MAX_RETRIES):
            if ctx.get("abort_album", False):
                res = "aborted"
                break
            res = self.downloader.download_file(cdn_url, ctx["dest_dir"], name, page, progress_callback=progress_cb, abort_callback=lambda: ctx.get("abort_album", False))
            if res == "success" or res == "aborted":
                break
            # Check if the error string contains a 503 (or 429 rate-limit) to decide whether to retry
            is_retryable = res and ("503" in str(res) or "429" in str(res) or "Service Temporarily Unavailable" in str(res))
            if is_retryable and attempt < MAX_RETRIES - 1:
                wait_sec = RETRY_DELAYS[attempt]
                self.log_status(f"⏳ CDN returned {503 if '503' in str(res) else 429} for {name}. Retrying in {wait_sec}s... (attempt {attempt + 1}/{MAX_RETRIES - 1})")
                def _set_retry(w=wait_sec):
                    if item_id and self.dl_tree.exists(item_id):
                        self.dl_tree.item(item_id, values=(name, "-", f"Retry {attempt+1}...", "", ""))
                self.after(0, _set_retry)
                # Re-fetch CDN URL before retrying in case it has expired
                _time.sleep(wait_sec)
                new_cdn = self.scraper.get_cdn_url(page)
                if new_cdn:
                    cdn_url = new_cdn
            else:
                break  # Non-retryable error or out of attempts
        if res == "success":
            with ctx["progress_lock"]:
                ctx["success_count"] += 1
            self.log_status(f"✅ Completed: {name}")
            def _set_success():
                if item_id and self.dl_tree.exists(item_id):
                    self.dl_tree.item(item_id, values=(name, self.dl_tree.item(item_id)["values"][1], "Completed", "", str(ctx["dest_dir"] / name)))
                    self.dl_tree.move(item_id, self.dl_tree.parent(item_id), "end")
            self.after(0, _set_success)
            self._check_album_finished(ctx)
            return True
        elif res == "aborted":
            self.log_status(f"⏸️ Paused: {name}")
            def _set_paused():
                if item_id and self.dl_tree.exists(item_id):
                    self.dl_tree.item(item_id, values=(name, self.dl_tree.item(item_id)["values"][1], "Paused", "", ""))
            self.after(0, _set_paused)
            self._check_album_finished(ctx)
            return False
        else:
            self.log_status(f"❌ Error ({res}): {name}")
            def _set_error():
                if item_id and self.dl_tree.exists(item_id):
                    self.dl_tree.item(item_id, values=(name, self.dl_tree.item(item_id)["values"][1], "Error", "", ""))
            self.after(0, _set_error)
            with ctx["progress_lock"]:
                ctx["fail_count"] += 1
                if ctx["fail_count"] >= 3:
                    ctx["abort_album"] = True
                    if ctx["fail_count"] == 3:
                        self.log_status(f"⚠️ Too many errors ({ctx['fail_count']}) in album {ctx['album_title']}. Remaining files will be skipped!")
            self._check_album_finished(ctx)
            return False
    def _check_album_finished(self, ctx):
        with ctx["progress_lock"]:
            ctx["completed_count"] += 1
            is_finished = (ctx["completed_count"] == ctx["total_items"])
        if is_finished:
            self.log_status(f"🏁 {ctx['album_title']} Process completed. Successful: {ctx['success_count']}/{ctx['total_items']}")
            def _finish_ui():
                node_id = ctx.get("ui_node")
                if node_id and self.dl_tree.exists(node_id):
                    self.dl_tree.delete(node_id)
                if hasattr(self, "refresh_history"):
                    self.refresh_history()
            self.after(2000, _finish_ui)
            if ctx["success_count"] > 0:
                orig_url = ctx["original_url"]
                if orig_url and self.captured_file.exists():
                    try:
                        with open(self.captured_file, "r", encoding="utf-8") as f:
                            lines = f.readlines()
                        with open(self.captured_file, "w", encoding="utf-8") as f:
                            for line in lines:
                                if line.strip() == orig_url:
                                    f.write(f"# {line.strip()}\n")
                                else:
                                    f.write(line)
                    except:
                        pass
            try:
                if ctx["dest_dir"].exists() and not any(ctx["dest_dir"].iterdir()):
                    ctx["dest_dir"].rmdir()
                    self.log_status(f"🗑️ Empty folder deleted as no downloadable file found: {ctx['album_title']}")
            except:
                pass
