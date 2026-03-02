import sys
import os
import logging
import urllib3
from core.config_manager import ConfigManager
from core.scraper import BunkrScraper
from core.downloader import BunkrDownloader
from ui.app import BunkrApp

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
def main():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(current_dir)
    config = ConfigManager()
    scraper = BunkrScraper(config)
    downloader = BunkrDownloader(config)
    app = BunkrApp(config, scraper, downloader)
    import threading
    import ctypes
    import pystray
    from PIL import Image, ImageDraw
    from pystray import MenuItem as item
    def create_image():
        # Siyah arkaplan ve B harfi ile basit bir ikon
        image = Image.new('RGB', (64, 64), color=(31, 83, 141))
        draw = ImageDraw.Draw(image)
        draw.rectangle((16, 16, 48, 48), fill=(255, 255, 255))
        return image
    def terminate_process():
        try:
            hwnd = ctypes.windll.kernel32.GetConsoleWindow()
            if hwnd:
                ctypes.windll.user32.ShowWindow(hwnd, 0)
        except:
            pass
        try:
            scraper.quit_drivers()
        except:
            pass
        try:
            os.system("taskkill /F /IM chromedriver.exe /T > NUL 2>&1")
        except:
            pass
        try:
            for handler in logging.root.handlers[:]:
                handler.close()
                logging.root.removeHandler(handler)
            logging.shutdown()
        except:
            pass
        os._exit(0)
    def actual_quit(icon, item):
        icon.stop()
        threading.Thread(target=terminate_process, daemon=True).start()
    def show_window(icon, item):
        icon.stop()
        app.after(0, app.deiconify)
    def on_closing():
        app.withdraw()
        menu = (item('Show Bunker Downloader', show_window, default=True), item('Quit Program', actual_quit))
        icon = pystray.Icon("bunkrpro_v2", create_image(), "Bunker Downloader (Open)", menu)
        threading.Thread(target=icon.run, daemon=True).start()
    app.protocol("WM_DELETE_WINDOW", on_closing)
    app.mainloop()
if __name__ == "__main__":
    main()
