import os
import re
import json
import time
import random
import threading
import logging
import html
from urllib.parse import urlparse
from bs4 import BeautifulSoup
log = logging.getLogger("BunkrV2.Scraper")
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]
class BunkrScraper:
    CDN_RE = re.compile(
        r"https?://[a-zA-Z0-9\-.]+\.(ru|ru/api|bunkr\.[a-z]{2,3}|bunkrr\.su|bunkr-free\.com|media-bunkr\.com|gigachad-cdn\.ru|bunkr\.link|scdn\.st)(/[^\s\"'<>\\]+)?",
        re.IGNORECASE,
    )
    def __init__(self, config_manager):
        self.config = config_manager
        self._thread_local = threading.local()
        self._drivers = []
        self._lock = threading.Lock()
    def rand_ua(self):
        return random.choice(USER_AGENTS)
    def get_driver(self):
        if hasattr(self._thread_local, "driver") and self._thread_local.driver:
            try:
                _ = self._thread_local.driver.window_handles
                return self._thread_local.driver
            except:
                self._thread_local.driver = None
        drv = self._make_driver()
        if drv:
            self._thread_local.driver = drv
            with self._lock:
                self._drivers.append(drv)
        return drv
    def _make_driver(self):
        from selenium import webdriver
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.chrome.options import Options
        from webdriver_manager.chrome import ChromeDriverManager
        
        opts = Options()
        opts.add_argument("--headless=new")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--mute-audio")
        opts.add_argument(f"--user-agent={self.rand_ua()}")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--disable-blink-features=AutomationControlled")
        opts.add_argument("--blink-settings=imagesEnabled=false")
        opts.add_experimental_option("prefs", {
            "download_restrictions": 3,
            "profile.default_content_setting_values.automatic_downloads": 2,
            "download.prompt_for_download": False
        })
        opts.set_capability("goog:loggingPrefs", {"performance": "ALL"})
        drv = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
        drv.set_page_load_timeout(60)
        return drv
    def quit_drivers(self):
        with self._lock:
            for d in self._drivers:
                try: d.quit()
                except: pass
            self._drivers = []
            if hasattr(self._thread_local, "driver"):
                self._thread_local.driver = None
        import os
        try:
            pass
        except:
            pass
    def quit_current_driver(self):
        """Closes only the driver of the calling thread. Does not break others."""
        drv = getattr(self._thread_local, "driver", None)
        if drv:
            try: drv.quit()
            except: pass
            with self._lock:
                if drv in self._drivers:
                    self._drivers.remove(drv)
            self._thread_local.driver = None
    def is_cdn_url(self, url):
        if not url or not url.startswith("http"): return False
        url_lower = url.lower()
        # Static and thumb filters
        if "static.scdn.st" in url_lower or "/thumbs/" in url_lower or "i-cheese.bunkr.ru" in url_lower:
            return False
        path = urlparse(url).path.lower()
        bad_exts = (".js", ".css", ".html", ".htm", ".json", ".xml", ".php", ".txt", ".ico", ".svg", ".map")
        if path.endswith(bad_exts): return False
        if "get.bunkrr.su/file/" in url_lower: return False
        if "/api/" in path or path.startswith("/api"): return False
        if self.CDN_RE.search(url):
            return True
        return False
    def harvest_cdn(self):
        drv = self.get_driver()
        if not drv: return ""
        try:
            logs = drv.get_log("performance")
            for entry in reversed(logs):
                try:
                    msg = json.loads(entry["message"])["message"]
                    params = msg.get("params", {})
                    url = params.get("request", {}).get("url", "") or \
                          params.get("response", {}).get("url", "")
                    if self.is_cdn_url(url): return url
                except: pass
        except: pass
        return ""
    def scrape_album(self, album_url):
        log.info(f"Scanning album: {album_url}")
        drv = self.get_driver()
        if not drv: return [], "Driver Error"
        try:
            drv.get(album_url)
            time.sleep(5)
            drv.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            soup = BeautifulSoup(drv.page_source, "html.parser")
            title = soup.find("h1").get_text(strip=True) if soup.find("h1") else "Unknown Album"
            host = f"{urlparse(album_url).scheme}://{urlparse(album_url).netloc}"
            if "/f/" in album_url or "/v/" in album_url or "/i/" in album_url or "/d/" in album_url:
                log.info("Tekil dosya tespit edildi.")
                name = title
                name = re.sub(r'[\\/*?:"<>|]', "_", name).strip(". ")
                ftype = "Unknown"
                ext = os.path.splitext(name)[1].lower()
                if ext in ('.jpg', '.jpeg', '.png', '.gif', '.webp'): ftype = "Image"
                elif ext in ('.mp4', '.mov', '.avi', '.mkv', '.webm'): ftype = "Video"
                album_link = soup.find("a", href=lambda h: h and "/a/" in h)
                real_album_id = "Tekli"
                if album_link:
                    from urllib.parse import urljoin
                    real_album_href = album_link.get("href", "")
                    real_album_url = urljoin(album_url, real_album_href)
                    real_album_id = real_album_href.rstrip("/").split("/")[-1]
                    try:
                        log.info(f"Navigating to main folder for original album name... ({real_album_url})")
                        drv.get(real_album_url)
                        time.sleep(3)
                        a_soup = BeautifulSoup(drv.page_source, "html.parser")
                        title = a_soup.find("h1").get_text(strip=True) if a_soup.find("h1") else "Unknown Album"
                    except Exception as e:
                        log.warning(f"Could not parse album title: {e}")
                        title = "Unknown Album"
                else:
                    title = "Single Downloads"
                    real_album_id = "Genel"
                return [{"name": name, "file_page": album_url, "type": ftype}], title, real_album_id
            def parse_items_from_soup(s_soup):
                page_items = []
                for card in s_soup.select("div.theItem"):
                    a = card.select_one("a[href*='/f/']")
                    if not a: continue
                    href = a["href"] if a["href"].startswith("http") else host + a["href"]
                    name_el = card.select_one(".theName") or card
                    name = name_el.get_text(strip=True)
                    name = re.sub(r'[\\/*?:"<>|]', "_", name).strip(". ")
                    ftype = "Unknown"
                    ext = os.path.splitext(name)[1].lower()
                    if ext in ('.jpg', '.jpeg', '.png', '.gif', '.webp'): ftype = "Image"
                    elif ext in ('.mp4', '.mov', '.avi', '.mkv', '.webm'): ftype = "Video"
                    page_items.append({"name": name, "file_page": href, "type": ftype})
                return page_items
            items = parse_items_from_soup(soup)
            max_page = 1
            pagination = soup.select_one("nav.pagination")
            if pagination:
                for a in pagination.find_all("a", href=True):
                    m = re.search(r"page=(\d+)", a["href"])
                    if m:
                        page_num = int(m.group(1))
                        if page_num > max_page:
                            max_page = page_num
            if max_page > 1:
                log.info(f"Album consists of {max_page} pages. Scanning other pages...")
                base_url = album_url.split("?")[0]
                for p in range(2, max_page + 1):
                    next_url = f"{base_url}?page={p}"
                    log.info(f"Tarama: Sayfa {p}/{max_page}")
                    try:
                        drv.get(next_url)
                        time.sleep(4)
                        drv.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                        time.sleep(2)
                        n_soup = BeautifulSoup(drv.page_source, "html.parser")
                        items.extend(parse_items_from_soup(n_soup))
                    except Exception as e:
                        log.warning(f"Error scanning page {p}: {e}")
            # Make names unique
            name_counts = {}
            for i, it in enumerate(items, 1):
                raw = it["name"]
                if raw in name_counts:
                    base, ext = os.path.splitext(raw)
                    it["name"] = f"{base}_{i}{ext}"
                else:
                    name_counts[raw] = 1
            log.info(f"Scan completed: {len(items)} files found.")
            orig_album_id = album_url.rstrip("/").split("/")[-1]
            return items, title, orig_album_id
        except Exception as e:
            log.error(f"Album scan error: {e}")
            return [], f"Hata: {e}", None
    def get_cdn_url(self, initial_url, retries=3):
        """Proof-of-work link resolution with retry logic for connection issues."""
        for attempt in range(retries):
            drv = self.get_driver()
            if not drv: return ""
            try:
                # Step 1: Handle /f/ page
                if "/f/" in initial_url:
                    log.debug(f"🔎 File page ({attempt+1}/{retries}): {initial_url.split('/')[-1]}")
                    try:
                        drv.get(initial_url)
                    except Exception as e:
                        if "net::ERR_CONNECTION_CLOSED" in str(e):
                            log.warning("⚠️ Connection closed, refreshing driver...")
                            self.quit_current_driver()
                            time.sleep(2 * (attempt + 1))
                            continue
                        raise e
                    time.sleep(4)
                    cdn = self.harvest_cdn()
                    if cdn: return cdn
                    soup = BeautifulSoup(drv.page_source, "html.parser")
                    bunkrr_link = soup.select_one("a[href*='get.bunkrr.su/file/']")
                    if bunkrr_link:
                        next_url = bunkrr_link["href"]
                        if not next_url.startswith("http"):
                            next_url = f"{urlparse(initial_url).scheme}://{urlparse(initial_url).netloc}" + next_url
                        return self.get_cdn_url(next_url)
                # Step 2: Intermediate page (get.bunkrr.su)
                if "get.bunkrr.su/file/" in initial_url:
                    log.debug(f"🔎 Ara sayfa ({attempt+1}/{retries}): {initial_url}")
                    try:
                        drv.get(initial_url)
                    except Exception as e:
                        if "net::ERR_CONNECTION_CLOSED" in str(e):
                            log.warning("⚠️ Connection closed, refreshing driver...")
                            self.quit_current_driver()
                            time.sleep(2 * (attempt + 1))
                            continue
                        raise e
                    time.sleep(4)
                    cdn = self.harvest_cdn()
                    if cdn: return cdn
                    from selenium.webdriver.common.by import By
                    selectors = ["a.btn-main", "#download-btn", "[data-id]", "a[href*='get.bunkrr.su']"]
                    for sel in selectors:
                        try:
                            btn = drv.find_element(By.CSS_SELECTOR, sel)
                            if btn:
                                log.debug(f"🖱️ Clicking: {sel}")
                                drv.execute_script("arguments[0].click();", btn)
                                time.sleep(6)
                                cdn = self.harvest_cdn()
                                if cdn: return cdn
                        except: continue
                # Final check in page source
                html_src = drv.page_source
                for m in self.CDN_RE.finditer(html_src):
                    url = m.group(0).split('"')[0].split("'")[0]
                    if self.is_cdn_url(url): return url
                return "" # Success logic reached but no link
            except Exception as e:
                log.error(f"Try {attempt+1} failed: {e}")
                if "net::ERR_CONNECTION_CLOSED" in str(e):
                    self.quit_current_driver()
                time.sleep(2 * (attempt + 1))
        return ""
