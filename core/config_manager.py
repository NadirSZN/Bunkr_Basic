import json
from pathlib import Path

class ConfigManager:
    DEFAULT_CONFIG = {
        "speed": {
            "max_extraction_workers": 4,
            "max_download_workers": 4,
            "download_speed_limit": 0  # 0 = Unlimited (KB/s)
        },
        "error_handling": {
            "max_retries": 5,
            "abort_on_404": False,
            "enable_server_skipping": True,
            "auto_skip_on_fail": True
        },
        "paths": {
            "download_path": "Downloads"
        },
        "ui": {
            "theme": "dark",
            "countdown_seconds": 10
        }
    }

    def __init__(self, config_file="config.json"):
        self.config_folder = Path(__file__).parent.parent
        self.config_path = self.config_folder / config_file
        self.config = self.DEFAULT_CONFIG.copy()
        self.load()

    def load(self):
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    # Update only valid keys
                    for category, values in self.DEFAULT_CONFIG.items():
                        if category in loaded:
                            for key in values:
                                if key in loaded[category]:
                                    self.config[category][key] = loaded[category][key]
            except Exception as e:
                print(f"Error: Could not load config: {e}")

    def save(self):
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            print(f"Error: Could not save config: {e}")

    def get(self, category, key):
        return self.config.get(category, {}).get(key)

    def set(self, category, key, value):
        if category in self.config and key in self.config[category]:
            self.config[category][key] = value
            self.save()
