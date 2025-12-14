import flet as ft
import pathlib
import logging
import os
import re
from config_manager import get_config
from vertex_ai_client import Content

config = get_config()

# --- UI Component Definitions ---
default_model = config.get("default_model", "gemini-1.5-flash-001")
available_models = config.get("available_models", [default_model])
if default_model not in available_models:
    logging.warning(f"Default model '{default_model}' not in available_models list. Using first available.")
    default_model = available_models[0] if available_models else "gemini-1.5-flash-001"

# システムプロンプトテンプレート設定
system_prompt_templates = config.get("system_prompt_templates", {"なし": ""})
template_names = list(system_prompt_templates.keys())

model_dropdown = ft.Dropdown(label="Model", options=[ft.dropdown.Option(m) for m in available_models], value=default_model, tooltip="Select model", expand=True)
temperature_slider = ft.Slider(min=0.0, max=1.0, divisions=20, label="{value:.2f}", value=config.get("default_temperature", 0.7), tooltip="Temperature", expand=True)
temperature_label = ft.Text(f"{temperature_slider.value:.2f}", width=40)
max_tokens_field = ft.TextField(label="MaxTok", value=str(config.get("default_max_output_tokens", 8192)), keyboard_type=ft.KeyboardType.NUMBER, tooltip="Max Output Tokens", width=100)

# システムプロンプトテンプレート選択ドロップダウン
system_prompt_template_dropdown = ft.Dropdown(
    label="テンプレート",
    options=[ft.dropdown.Option(name) for name in template_names],
    value=template_names[0],
    tooltip="システムプロンプトテンプレートを選択",
    width=150
)

system_prompt_field = ft.TextField(label="System Prompt", value=config.get("default_system_prompt", ""), tooltip="Optional system instruction", multiline=True, min_lines=1, max_lines=5, expand=True)

# --- Thinking Controls ---
# デフォルトでGemini 2.5 Flashの制限値を使用（最大24576）
thinking_budget_slider = ft.Slider(min=0, max=24576, divisions=24, label="{value:.0f}", value=8192, tooltip="思考バジェット (0=無効, -1=自動)", expand=True)
thinking_budget_label = ft.Text("8192", width=60)
thinking_auto_budget_switch = ft.Switch(label="自動バジェット", value=False, tooltip="思考バジェットの自動最適化を使用")

# Gemini 3.0 Pro用のthinking_level選択
thinking_level_dropdown = ft.Dropdown(
    label="思考レベル",
    options=[
        ft.dropdown.Option("HIGH", "HIGH"),
        ft.dropdown.Option("LOW", "LOW")
    ],
    value="HIGH",
    tooltip="思考レベル (HIGH=高深度推論, LOW=低レイテンシ)",
    width=150,
    visible=False  # デフォルトでは非表示（モデルに応じて表示/非表示を切り替え）
)

# 思考表示スイッチは削除（バジェットが0でない場合は常に表示）

# --- Grounding Controls ---
grounding_config = config.get("grounding", {})
grounding_switch = ft.Switch(
    label="グラウンディング (Google Search)",
    value=grounding_config.get("enabled", False),
    tooltip="Google Search Toolを使用して最新の情報を検索"
)

# --- File Explorer Components (Reverting to simple Column) ---
# Use dictionary to track checkboxes and their corresponding file paths
file_checkboxes: dict[ft.Checkbox, str] = {}
# Revert to using Column for stability, sacrificing folding feature
file_explorer_controls = ft.Column(scroll=ft.ScrollMode.ADAPTIVE, expand=True, spacing=0)

# --- Other UI Components ---
chat_history_display = ft.ListView(expand=True, spacing=10)
user_input = ft.TextField(hint_text="Ctrl+Enter to send...", multiline=True, min_lines=2, max_lines=5, shift_enter=True, expand=True)
send_button = ft.IconButton(ft.Icons.SEND_ROUNDED, tooltip="Send")
cancel_button = ft.IconButton(ft.Icons.CANCEL_ROUNDED, tooltip="Cancel sending", visible=False, icon_color=ft.Colors.ERROR)
reset_button = ft.IconButton(ft.Icons.REFRESH_ROUNDED, tooltip="Reset Conversation")
status_bar = ft.Text("")

# --- Conversation State ---
conversation_history: list[Content] = []
is_sending = False
cancel_requested = False

# --- Session Management Components ---
session_dropdown = ft.Dropdown(
    label="Session",
    options=[ft.dropdown.Option("default")],
    value="default",
    tooltip="Select conversation session",
    width=150
)

new_session_name_field = ft.TextField(
    label="新しいセッション名",
    hint_text="Session name...",
    expand=True,
    height=40
)

create_session_button = ft.IconButton(
    icon=ft.Icons.ADD_ROUNDED,
    tooltip="新しいセッションを作成",
    width=40,
    height=40
)

delete_session_button = ft.IconButton(
    icon=ft.Icons.DELETE_ROUNDED,
    tooltip="現在のセッションを削除",
    width=40,
    height=40,
    icon_color=ft.Colors.ERROR
)

session_info_text = ft.Text(
    "Session: default",
    size=12,
    color=ft.Colors.ON_SURFACE_VARIANT,
    italic=True
)

# --- Session Management Helper Functions ---
def update_session_dropdown_options(session_list: list[str], current_session: str = "default"):
    """セッション一覧を更新"""
    logging.info(f"Updating dropdown options: {session_list}, current: {current_session}")
    session_dropdown.options = [ft.dropdown.Option(session) for session in session_list]
    session_dropdown.value = current_session if current_session in session_list else (session_list[0] if session_list else "default")
    logging.info(f"Dropdown value set to: {session_dropdown.value}")

def update_session_info(session_name: str, message_count: int = 0):
    """セッション情報を更新"""
    session_info_text.value = f"Session: {session_name} ({message_count} messages)"
    if hasattr(session_info_text, 'page') and session_info_text.page:
        session_info_text.update()

# --- Helper Functions ---
def extract_thinking(text: str) -> tuple[str, str]:
    thinking_parts = []
    pattern = re.compile(r"<thinking>(.*?)</thinking>", re.DOTALL | re.IGNORECASE)
    def replace_thinking(match): thinking_parts.append(match.group(1).strip()); return ""
    main_content = pattern.sub(replace_thinking, text).strip()
    return "\n---\n".join(thinking_parts), main_content

def format_thinking_display(thinking_text: str) -> str:
    """思考テキストを見やすい形式にフォーマット"""
    if not thinking_text:
        return ""
    
    # 思考テキストを整形
    formatted = thinking_text.strip()
    
    # 長い思考の場合は省略表示のオプション
    if len(formatted) > 2000:
        lines = formatted.split('\n')
        if len(lines) > 50:
            preview_lines = lines[:25] + ['...', '（中略）', '...'] + lines[-25:]
            formatted = '\n'.join(preview_lines)
    
    return formatted

def update_thinking_budget_label(e):
    """Update thinking budget label when slider changes"""
    thinking_budget_label.value = str(int(e.control.value))
    try:
        thinking_budget_label.update()
    except:
        pass

def update_thinking_controls(e):
    """Update thinking controls when auto budget switch changes"""
    is_auto = thinking_auto_budget_switch.value
    # 自動バジェットがONの時はスライダーを無効化
    thinking_budget_slider.disabled = is_auto
    thinking_budget_label.disabled = is_auto
    if is_auto:
        thinking_budget_label.value = "Auto"
    else:
        thinking_budget_label.value = str(int(thinking_budget_slider.value))
    try:
        thinking_budget_slider.update()
        thinking_budget_label.update()
    except:
        pass

def update_thinking_for_model(e=None):
    """モデル変更時に思考制御を更新"""
    if not model_dropdown.value:
        return
    
    model_name = model_dropdown.value.lower()
    is_flash_model = "flash" in model_name
    is_pro_model = "pro" in model_name
    is_flash_lite = "flash-lite" in model_name
    is_gemini_3_pro = "3-pro" in model_name or "gemini-3-pro" in model_name
    
    if is_gemini_3_pro:
        # Gemini 3.0 Pro: thinking_levelを使用
        # バジェットスライダーを非表示
        thinking_budget_slider.visible = False
        thinking_budget_label.visible = False
        thinking_auto_budget_switch.visible = False
        # thinking_levelドロップダウンを表示
        thinking_level_dropdown.visible = True
        thinking_level_dropdown.tooltip = "思考レベル (HIGH=高深度推論, LOW=低レイテンシ)"
    else:
        # その他のモデル: thinking_budgetを使用
        # thinking_levelドロップダウンを非表示
        thinking_level_dropdown.visible = False
        # バジェットスライダーを表示
        thinking_budget_slider.visible = True
        thinking_budget_label.visible = True
        thinking_auto_budget_switch.visible = True
        
        if is_pro_model:
            # Gemini 2.5 Pro: 128-32768トークン、思考無効化不可
            thinking_budget_slider.min = 128
            thinking_budget_slider.max = 32768
            thinking_budget_slider.divisions = 32
            thinking_budget_slider.tooltip = "思考バジェット (128-32768, Proでは思考無効化不可, -1=自動)"
            thinking_auto_budget_switch.tooltip = "思考バジェットの自動最適化（Proモデル推奨）"
            
            # 現在値が範囲外の場合は調整
            if thinking_budget_slider.value < 128:
                thinking_budget_slider.value = 8192  # デフォルト値
                
        elif is_flash_lite:
            # Gemini 2.5 Flash-Lite: 512-24576トークン
            thinking_budget_slider.min = 0  # 0で無効化可能
            thinking_budget_slider.max = 24576
            thinking_budget_slider.divisions = 24
            thinking_budget_slider.tooltip = "思考バジェット (0=無効, 512-24576, -1=自動)"
            thinking_auto_budget_switch.tooltip = "思考バジェットの自動最適化（Flash-Lite）"
            
        elif is_flash_model:
            # Gemini 2.5 Flash: 1-24576トークン
            thinking_budget_slider.min = 0  # 0で無効化可能
            thinking_budget_slider.max = 24576
            thinking_budget_slider.divisions = 24
            thinking_budget_slider.tooltip = "思考バジェット (0=無効, 1-24576, -1=自動)"
            thinking_auto_budget_switch.tooltip = "思考バジェットの自動最適化（Flashモデル）"
            
        else:
            # その他のモデル：デフォルト制限
            thinking_budget_slider.min = 0
            thinking_budget_slider.max = 8192
            thinking_budget_slider.divisions = 8
            thinking_budget_slider.tooltip = "思考バジェット (0=無効, モデルによってはサポートされない場合があります)"
            thinking_auto_budget_switch.tooltip = "思考バジェットの自動最適化"
        
        # ラベル更新
        if thinking_auto_budget_switch.value:
            thinking_budget_label.value = "Auto"
        else:
            thinking_budget_label.value = str(int(thinking_budget_slider.value))
    
    # グラウンディングスイッチは常に表示
    if hasattr(grounding_switch, 'visible'):
        grounding_switch.visible = True
    
    # UIを更新
    try:
        thinking_budget_slider.update()
        thinking_budget_label.update()
        thinking_auto_budget_switch.update()
        thinking_level_dropdown.update()
        if hasattr(grounding_switch, 'update'):
            grounding_switch.update()
    except:
        pass

def load_system_prompt_template(e):
    """Load selected system prompt template into the text field"""
    selected_template = system_prompt_template_dropdown.value
    if selected_template and selected_template in system_prompt_templates:
        system_prompt_field.value = system_prompt_templates[selected_template]
        if hasattr(e.control, 'page') and e.control.page:
            system_prompt_field.update()

# Set up event handlers
thinking_budget_slider.on_change = update_thinking_budget_label
thinking_auto_budget_switch.on_change = update_thinking_controls
system_prompt_template_dropdown.on_change = load_system_prompt_template
model_dropdown.on_change = update_thinking_for_model

# Populate function for simple Column view (Reverted)
def populate_file_explorer(root_dir_path: str):
    global file_checkboxes
    file_checkboxes.clear()
    file_explorer_controls.controls.clear()

    try:
        root_path = pathlib.Path(root_dir_path).resolve()
        if not root_path.is_dir():
            status_bar.value = f"Error: Root dir '{root_dir_path}' not found."
            logging.error(status_bar.value)
            if file_explorer_controls.page:
                try: status_bar.update(); file_explorer_controls.update()
                except: pass
            return

        status_bar.value = f"Loading files from {root_path}..."
        if file_explorer_controls.page:
              try: status_bar.update()
              except: pass

        default_excludes = {'.venv', 'venv', '__pycache__', 'node_modules', '.git', '.vscode', 'dist', 'build', 'assets'}
        try:
            current_config = get_config()
            excluded_dirs_list = current_config.get("excluded_dirs", list(default_excludes))
            excluded_dirs = set(excluded_dirs_list)
        except Exception as config_err:
            logging.warning(f"Could not load excluded_dirs from config, using defaults: {config_err}")
            excluded_dirs = default_excludes

        items_to_add = [] # List to hold controls

        def walk_directory_simple(current_path: pathlib.Path, depth: int):
            """Recursively walks directory, creating Text for dirs and Checkbox for files."""
            prefix = "  " * depth # Indentation based on depth
            try:
                # Sort: Dirs first, then files, case-insensitive
                sorted_items = sorted(current_path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
                for item in sorted_items:
                    if item.name.startswith('.') or item.name in excluded_dirs:
                        continue

                    if item.is_dir():
                        # Add directory text with indentation
                        items_to_add.append(ft.Text(f"{prefix}📁 {item.name}", opacity=0.7))
                        # Recurse into subdirectory
                        walk_directory_simple(item, depth + 1)
                    elif item.is_file():
                        # Add file checkbox with indentation
                        file_path_str = str(item)
                        checkbox = ft.Checkbox(label=f"{prefix}📄 {item.name}", value=False, data=file_path_str)
                        file_checkboxes[checkbox] = file_path_str # Track checkbox
                        items_to_add.append(checkbox)

            except PermissionError:
                logging.warning(f"Permission denied accessing {current_path}")
                items_to_add.append(ft.Text(f"{prefix}🚫 {current_path.name} (Permission Denied)", color=ft.colors.ON_SURFACE_VARIANT, italic=True))
            except Exception as walk_err:
                logging.warning(f"Error walking directory {current_path}: {walk_err}")
                items_to_add.append(ft.Text(f"{prefix}⚠️ {current_path.name} (Error)", color=ft.colors.ORANGE_ACCENT, italic=True))

        # Start the recursive walk
        walk_directory_simple(root_path, 0)

        if not items_to_add:
            items_to_add.append(ft.Text("No displayable files/dirs.", italic=True, opacity=0.7))

        # Add all collected controls to the Column
        file_explorer_controls.controls.extend(items_to_add)

        status_bar.value = f"Files loaded from {root_path}."
        logging.info(status_bar.value)

    except Exception as e:
        status_bar.value = f"Error scanning directory: {e}"
        logging.error(status_bar.value, exc_info=True)
        file_explorer_controls.controls.clear()
        file_explorer_controls.controls.append(ft.Text(f"Error: {e}", color=ft.colors.RED))

    # Update UI
    if file_explorer_controls.page:
        try:
            file_explorer_controls.update()
            status_bar.update()
        except Exception as update_err:
            logging.error(f"Error updating file explorer Column UI: {update_err}")

def scroll_to_bottom():
    """Scrolls the chat history display to the bottom."""
    try:
         chat_history_display.scroll_to(offset=-1, duration=300, curve=ft.AnimationCurve.EASE_OUT)
    except Exception as scroll_err:
         logging.warning(f"Could not scroll chat: {scroll_err}")

# 新しいチャット表示システムは削除（従来の表示方式に戻すため）
