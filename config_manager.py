import json
import logging

CONFIG_FILE = "config.json"

DEFAULT_CONFIG = {
    "vertex_ai_project_id": "YOUR_PROJECT_ID",
    "vertex_ai_location": "YOUR_LOCATION",
    "root_directory": "",
    "available_models": [
        "gemini-1.5-flash-001",
        "gemini-1.5-pro-001",
        "gemini-1.0-pro-001"
    ],
    "default_model": "gemini-1.5-flash-001",
    "default_temperature": 0.7,
    "default_max_output_tokens": 8192,
    "default_system_prompt": ""
}

def load_config():
    """Loads configuration from config.json, providing defaults."""
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
            logging.info(f"Configuration loaded from {CONFIG_FILE}")
            # Merge with defaults to ensure all keys exist
            # Loaded values take precedence
            merged_config = DEFAULT_CONFIG.copy()
            merged_config.update(config_data)
            return merged_config
    except FileNotFoundError:
        logging.warning(f"Configuration file '{CONFIG_FILE}' not found. Using default config.")
        print(f"Warning: Configuration file '{CONFIG_FILE}' not found. Using default config.")
        return DEFAULT_CONFIG.copy()
    except json.JSONDecodeError:
        logging.error(f"Configuration file '{CONFIG_FILE}' contains invalid JSON. Using default config.")
        print(f"Error: Configuration file '{CONFIG_FILE}' contains invalid JSON. Using default config.")
        return DEFAULT_CONFIG.copy()
    except Exception as e:
        logging.error(f"Error loading configuration: {e}", exc_info=True)
        print(f"Error loading configuration: {e}")
        return DEFAULT_CONFIG.copy()

# Load config when module is imported
config = load_config()

def get_config():
    """Returns the loaded configuration dictionary."""
    return config

def update_root_directory(new_path: str) -> bool:
    """プロジェクトのルートディレクトリパスを更新"""
    try:
        # 現在の設定を読み込み
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        
        # パスを更新
        config_data["root_directory"] = new_path
        
        # 設定を保存
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)
        
        # グローバル設定も更新
        global config
        config["root_directory"] = new_path
        
        logging.info(f"プロジェクトパスを更新しました: {new_path}")
        return True
    except Exception as e:
        logging.error(f"プロジェクトパス更新に失敗: {e}", exc_info=True)
        return False
