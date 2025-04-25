import json
import os

CONFIG_FILE = "anki_gui_config.json"

def load_config():
    """Loads configuration from the JSON file."""
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)
            print(f"Loaded config: {config}")
            return config
    except FileNotFoundError:
        print("Config file not found, using defaults.")
        return {}
    except json.JSONDecodeError:
        print("Error decoding config file, using defaults.")
        return {}
    except Exception as e:
        print(f"Error loading config: {e}")
        return {}

def save_config(config_data):
    """Saves the provided configuration data to the JSON file."""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=4)
            print(f"Saved config: {config_data}")
    except Exception as e:
        print(f"Error saving config: {e}")
        # In a real app, might want to log this or show a non-blocking warning
