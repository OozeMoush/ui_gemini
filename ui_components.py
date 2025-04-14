import flet as ft
import pathlib
import logging
import os
import re
from config_manager import get_config
from vertexai.generative_models import Content # For conversation history typing

config = get_config()

# --- UI Component Definitions ---
default_model = config.get("default_model", "gemini-1.5-flash-001")
available_models = config.get("available_models", [default_model])
if default_model not in available_models:
    logging.warning(f"Default model '{default_model}' not in available_models list. Using first available.")
    default_model = available_models[0] if available_models else "gemini-1.5-flash-001"

model_dropdown = ft.Dropdown(label="Model", options=[ft.dropdown.Option(m) for m in available_models], value=default_model, tooltip="Select model", expand=True)
temperature_slider = ft.Slider(min=0.0, max=1.0, divisions=20, label="{value:.2f}", value=config.get("default_temperature", 0.7), tooltip="Temperature", expand=True)
temperature_label = ft.Text(f"{temperature_slider.value:.2f}", width=40)
max_tokens_field = ft.TextField(label="MaxTok", value=str(config.get("default_max_output_tokens", 8192)), keyboard_type=ft.KeyboardType.NUMBER, tooltip="Max Output Tokens", width=100)
system_prompt_field = ft.TextField(label="System Prompt", value=config.get("default_system_prompt", ""), tooltip="Optional system instruction", multiline=True, min_lines=1, max_lines=3, expand=True)

file_checkboxes: dict[ft.Checkbox, str] = {}
file_explorer_controls = ft.Column(scroll=ft.ScrollMode.ADAPTIVE, expand=True, spacing=0)
chat_history_display = ft.ListView(expand=True, spacing=10, auto_scroll=True)
user_input = ft.TextField(hint_text="Enter prompt...", multiline=True, min_lines=2, max_lines=5, shift_enter=True, expand=True)
send_button = ft.IconButton(ft.icons.SEND_ROUNDED, tooltip="Send")
reset_button = ft.IconButton(ft.icons.REFRESH_ROUNDED, tooltip="Reset Conversation")
status_bar = ft.Text("")

# --- Conversation State (Managed here for now) ---
conversation_history: list[Content] = []
files_sent_in_convo = False

# --- Helper Functions related to UI or State ---
def extract_thinking(text: str) -> tuple[str, str]:
    thinking_parts = []
    pattern = re.compile(r"<thinking>(.*?)</thinking>", re.DOTALL | re.IGNORECASE)
    def replace_thinking(match): thinking_parts.append(match.group(1).strip()); return ""
    main_content = pattern.sub(replace_thinking, text).strip()
    return "\n---\n".join(thinking_parts), main_content

def populate_file_explorer(root_dir_path: str):
    # Clear previous state
    file_checkboxes.clear()
    file_explorer_controls.controls.clear()
    logging.info(f"Populating file explorer for: {root_dir_path}")
    try:
        root_path = pathlib.Path(root_dir_path).resolve()
        if not root_path.is_dir():
            status_bar.value = f"Error: Root dir '{root_dir_path}' not found."
            logging.error(status_bar.value)
            return

        status_bar.value = f"Loading files from {root_path}..."; items = []
        excluded_dirs = {'.venv', '__pycache__', 'node_modules', '.git', '.vscode', 'dist', 'build', 'assets'}

        for item_path in sorted(root_path.rglob('*')):
            try:
                relative_path = item_path.relative_to(root_path)
                is_hidden_or_excluded = any(part.startswith('.') or part in excluded_dirs for part in relative_path.parts)
                if is_hidden_or_excluded or item_path.name.startswith('.') or item_path.name in excluded_dirs:
                     logging.debug(f"Skipping excluded/hidden: {item_path}"); continue

                indent = len(relative_path.parts) - 1; prefix = "  " * indent
                if item_path.is_dir():
                    items.append(ft.Text(f"{prefix}📁 {item_path.name}", opacity=0.7))
                elif item_path.is_file():
                    checkbox = ft.Checkbox(label=f"{prefix}📄 {item_path.name}", value=False, data=str(item_path))
                    file_checkboxes[checkbox] = str(item_path)
                    items.append(checkbox)
                    logging.debug(f"Adding file: {item_path}")
            except Exception as item_err: logging.warning(f"Could not process path {item_path}: {item_err}")

        if not items: items.append(ft.Text("No displayable files/dirs.", italic=True, opacity=0.7))
        file_explorer_controls.controls.extend(items)
        status_bar.value = f"Files loaded from {root_path}."
        logging.info(status_bar.value)

    except Exception as e:
        status_bar.value = f"Error scanning directory: {e}"; logging.error(status_bar.value, exc_info=True)

    # Update via page context if available
    if file_explorer_controls.page:
        try: file_explorer_controls.page.update()
        except Exception as update_err: logging.error(f"Error updating file explorer UI: {update_err}")


def scroll_to_bottom():
    """Scrolls the chat history display to the bottom."""
    try:
         chat_history_display.scroll_to(offset=-1, duration=300, curve=ft.AnimationCurve.EASE_OUT)
         logging.debug("Scrolled chat to bottom.")
    except Exception as scroll_err:
         logging.warning(f"Could not scroll chat: {scroll_err}")
