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

# --- File Explorer Components ---
file_checkboxes: dict[ft.Checkbox, str] = {}
# Use ListView for the main container
file_explorer_controls = ft.ListView(expand=True, spacing=0)

# --- Other UI Components ---
chat_history_display = ft.ListView(expand=True, spacing=10)
user_input = ft.TextField(hint_text="Enter prompt...", multiline=True, min_lines=2, max_lines=5, shift_enter=True, expand=True)
send_button = ft.IconButton(ft.icons.SEND_ROUNDED, tooltip="Send")
reset_button = ft.IconButton(ft.icons.REFRESH_ROUNDED, tooltip="Reset Conversation")
status_bar = ft.Text("")

# --- Conversation State ---
conversation_history: list[Content] = []
files_sent_in_convo = False

# --- Helper Functions ---
def extract_thinking(text: str) -> tuple[str, str]:
    thinking_parts = []
    pattern = re.compile(r"<thinking>(.*?)</thinking>", re.DOTALL | re.IGNORECASE)
    def replace_thinking(match): thinking_parts.append(match.group(1).strip()); return ""
    main_content = pattern.sub(replace_thinking, text).strip()
    return "\n---\n".join(thinking_parts), main_content

def populate_file_explorer(root_dir_path: str):
    global file_checkboxes
    file_checkboxes.clear()
    file_explorer_controls.controls.clear()
    logging.info(f"Populating file explorer (ListView) for: {root_dir_path}")

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
            logging.info(f"Using excluded dirs: {excluded_dirs}")
        except Exception as config_err:
            logging.warning(f"Could not load excluded_dirs from config, using defaults: {config_err}")
            excluded_dirs = default_excludes

        def walk_directory(current_path: pathlib.Path) -> list[ft.Control]:
            """Recursively walks directory, returns a list of Checkboxes and ExpansionPanels."""
            controls = []
            try:
                for item in sorted(current_path.iterdir()):
                    if item.name.startswith('.') or item.name in excluded_dirs:
                        logging.debug(f"Skipping hidden/excluded item: {item.name}")
                        continue

                    if item.is_dir():
                        sub_items = walk_directory(item)
                        if sub_items: # Only add if directory is not empty/fully excluded
                            # Create the Column for the ExpansionPanel content
                            content_column = ft.Column(spacing=0, tight=True)
                            # Add all sub-items (files and sub-panels) directly to the column
                            content_column.controls.extend(sub_items)

                            panel = ft.ExpansionPanel(
                                header=ft.ListTile(title=ft.Text(f"📁 {item.name}")),
                                content=content_column,
                            )
                            controls.append(panel)
                    elif item.is_file():
                        file_path_str = str(item)
                        checkbox = ft.Checkbox(label=f"📄 {item.name}", value=False, data=file_path_str)
                        file_checkboxes[checkbox] = file_path_str
                        controls.append(checkbox)
                        logging.debug(f"Adding file checkbox: {item.name}")

            except PermissionError:
                logging.warning(f"Permission denied accessing {current_path}")
                controls.append(ft.Text(f"🚫 {current_path.name} (Permission Denied)", color=ft.colors.ON_SURFACE_VARIANT, italic=True))
            except Exception as walk_err:
                logging.warning(f"Error walking directory {current_path}: {walk_err}")
                controls.append(ft.Text(f"⚠️ {current_path.name} (Error)", color=ft.colors.ORANGE_ACCENT, italic=True))
            return controls

        # --- Assemble Top Level ---
        top_level_items = walk_directory(root_path)

        if not top_level_items:
            file_explorer_controls.controls.append(ft.Text("No displayable files/dirs.", italic=True, opacity=0.7))
        else:
            top_level_files = []
            top_level_panels = []
            for item in top_level_items:
                if isinstance(item, ft.Checkbox) or isinstance(item, ft.Text): # Include error texts here too
                    top_level_files.append(item)
                elif isinstance(item, ft.ExpansionPanel):
                    top_level_panels.append(item)

            # Add top-level files/texts first
            file_explorer_controls.controls.extend(top_level_files)

            # If there are top-level directories, wrap ONLY them in an ExpansionPanelList
            if top_level_panels:
                # Add a separator if files were also present
                if top_level_files:
                     file_explorer_controls.controls.append(ft.Divider(height=5, color=ft.colors.TRANSPARENT))

                expansion_list = ft.ExpansionPanelList(
                    controls=top_level_panels,
                    expand_icon_color=ft.colors.with_opacity(0.6, ft.Colors.ON_SURFACE),
                    elevation=1,
                    divider_color=ft.Colors.OUTLINE_VARIANT, # Divider between top-level directories
                )
                file_explorer_controls.controls.append(expansion_list)

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
            logging.debug("File explorer ListView and status bar updated.")
        except Exception as update_err:
            logging.error(f"Error updating file explorer ListView UI: {update_err}")

def scroll_to_bottom():
    """Scrolls the chat history display to the bottom."""
    try:
         chat_history_display.scroll_to(offset=-1, duration=300, curve=ft.AnimationCurve.EASE_OUT)
         logging.debug("Scrolled chat history to bottom.")
    except Exception as scroll_err:
         logging.warning(f"Could not scroll chat: {scroll_err}")
