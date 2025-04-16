import flet as ft
import time
import pathlib
# Logging and Config are now handled by importing the modules
import logger_setup # Initializes logging
import config_manager # Loads configuration
import logging # Still needed for logging calls within this file
import google.cloud.aiplatform as aiplatform
from vertexai.generative_models import (
    # Keep only necessary imports here, others are used in vertex_ai_client
    Part, FinishReason, GenerationConfig, Content
)
import vertexai.generative_models as generative_models # Re-add this import for safety_settings
# Import necessary UI components, state variables, and helpers from ui_components
# Ensure ui_components import reflects the reverted state (using file_checkboxes)
import ui_components
from ui_components import (
    model_dropdown, temperature_slider, temperature_label, max_tokens_field,
    system_prompt_field, file_checkboxes, file_explorer_controls,
    chat_history_display, user_input, send_button, reset_button, status_bar,
    populate_file_explorer, scroll_to_bottom, extract_thinking,
    conversation_history,
    files_sent_in_convo
)
# Import the new client function
from vertex_ai_client import generate_gemini_response

config = config_manager.get_config()

# --- Vertex AI Initialization ---
vertex_ai_initialized = False
init_error_message = ""
safety_settings = { category: generative_models.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE for category in generative_models.HarmCategory }
try:
    project_id = config.get("vertex_ai_project_id")
    location = config.get("vertex_ai_location")
    if project_id and location and project_id != "YOUR_PROJECT_ID" and location != "YOUR_LOCATION":
        aiplatform.init(project=project_id, location=location)
        vertex_ai_initialized = True
        logging.info(f"Vertex AI initialized for project {project_id} in {location}.")
        print(f"Vertex AI initialized for project {project_id} in {location}.")
    else:
        init_error_message = "Vertex AI project ID or location not configured properly in config.json."
        logging.warning(init_error_message); print(f"Warning: {init_error_message}")
except Exception as e:
    init_error_message = f"Error initializing Vertex AI: {e}"; logging.error(init_error_message, exc_info=True); print(f"Error: {init_error_message}")

# --- Main Application Logic ---
def main(page: ft.Page):
    page.title = "Gemini UI Chat"
    page.theme_mode = ft.ThemeMode.DARK # Keep Dark theme
    logging.info("Main UI function started.")
    # Assign page context to UI elements that need it for updates
    status_bar.page = page; file_explorer_controls.page = page; chat_history_display.page = page
    global files_sent_in_convo

    # Display init error via SnackBar using the correct method
    if init_error_message:
        snackbar = ft.SnackBar(ft.Text(f"Vertex AI Init Error: {init_error_message}"), open=True)
        if hasattr(page, 'overlay'):
             page.overlay.append(snackbar)
        else:
             logging.warning("Page overlay not ready for init error snackbar.")


    def update_temp_label(e): temperature_label.value = f"{e.control.value:.2f}"; page.update()
    temperature_slider.on_change = update_temp_label

    def reset_conversation(e):
        global files_sent_in_convo
        logging.info("Resetting conversation."); conversation_history.clear(); files_sent_in_convo = False
        chat_history_display.controls.clear()
        # Reset checkboxes stored in the dictionary (Reverted logic)
        logging.debug(f"Resetting {len(ui_components.file_checkboxes)} checkboxes in dictionary.")
        checkbox_update_errors = 0
        # Use the imported file_checkboxes directly
        for checkbox in ui_components.file_checkboxes.keys():
            checkbox.value = False;
        try:
            # Update the Column containing checkboxes
            ui_components.file_explorer_controls.update()
            logging.debug("File explorer Column updated after checkbox reset.")
        except Exception as control_update_err:
             # Fallback might be needed if column update fails
             logging.warning(f"Failed update on reset trying individuals: {control_update_err}")
             for checkbox in ui_components.file_checkboxes.keys():
                 try: checkbox.update()
                 except Exception as cb_err: checkbox_update_errors += 1; logging.debug(f"Individual checkbox update failed: {cb_err}")
             if checkbox_update_errors > 0: logging.warning(f"{checkbox_update_errors} checkboxes failed to update individually on reset.")

        system_prompt_field.value = config.get("default_system_prompt", "")
        status_bar.value = "Conversation reset."; page.update()
    reset_button.on_click = reset_conversation

    # --- Copy Button Handler ---
    def copy_to_clipboard(e, text_to_copy):
        logging.info(f"Copying text to clipboard (length: {len(text_to_copy)}).")
        page.set_clipboard(text_to_copy)
        snackbar = ft.SnackBar(ft.Text("Response text copied!"), open=True, duration=2000)
        page.overlay.append(snackbar)
        page.update()

    def send_message(e):
        global files_sent_in_convo
        prompt_text = user_input.value.strip()
        system_prompt_text = system_prompt_field.value.strip()
        if not prompt_text: snackbar = ft.SnackBar(ft.Text("Please enter a prompt."), open=True); page.overlay.append(snackbar); page.update(); return
        if not vertex_ai_initialized: logging.warning("Send: Vertex AI not initialized."); snackbar = ft.SnackBar(ft.Text(f"Vertex AI not initialized. Err: {init_error_message}"), open=True); page.overlay.append(snackbar); page.update(); return

        input_tokens_display = ft.Text("", size=10, italic=True, color=ft.Colors.ON_SURFACE_VARIANT, selectable=True)
        user_message_column = ft.Column([
            ft.Text(f"You: {prompt_text}", selectable=True),
            input_tokens_display
        ], spacing=2)

        chat_history_display.controls.append(user_message_column); user_input.value = ""; user_input.focus()
        scroll_to_bottom(); page.update()

        send_button.disabled = True; reset_button.disabled = True; status_bar.value = "Processing..."; page.update()

        current_prompt_parts = [Part.from_text(prompt_text)]; files_appended_now = False
        if not files_sent_in_convo:
            # File reading logic using file_checkboxes (Reverted logic)
            try:
                selected_files_this_turn = []
                if not status_bar.value.startswith("Error scanning"):
                    # Use the imported file_checkboxes directly
                    for checkbox, file_path_str in ui_components.file_checkboxes.items():
                        if checkbox.value:
                            try:
                                file_path = pathlib.Path(file_path_str)
                                if file_path.is_file():
                                    selected_files_this_turn.append(file_path.name)
                                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f: file_content = f.read()
                                    current_prompt_parts.insert(0, Part.from_text(f"--- Content of {file_path.name} ---\n```\n{file_content}\n```\n"))
                                    logging.debug(f"Read/added selected file: {file_path_str}")
                                else:
                                    logging.warning(f"Selected path is not a file: {file_path_str}")
                            except Exception as read_err:
                                file_name = file_path.name if 'file_path' in locals() and hasattr(file_path, 'name') else file_path_str
                                logging.warning(f"Error reading selected file {file_name}: {read_err}")
                                chat_history_display.controls.append(ft.Text(f"Error reading {file_name}: {read_err}", color=ft.Colors.ORANGE))
                                scroll_to_bottom(); page.update()

                if selected_files_this_turn: files_sent_in_convo = True; files_appended_now = True; logging.info(f"Prepending files: {', '.join(selected_files_this_turn)}")
            except Exception as proc_err: logging.error("File processing error.", exc_info=True); chat_history_display.controls.append(ft.Text(f"Error processing selected files: {proc_err}", color=ft.Colors.RED)); send_button.disabled = False; reset_button.disabled = False; status_bar.value = "Error processing files."; scroll_to_bottom(); page.update(); return

        gemini_response_md = ft.Markdown(f"**Gemini:**\n▌", selectable=True, code_theme="atom-one-dark", extension_set=ft.MarkdownExtensionSet.GITHUB_WEB, on_tap_link=lambda e: page.launch_url(e.data))
        gemini_response_container = ft.Container(content=gemini_response_md, padding=ft.padding.only(bottom=10), expand=True)
        response_row = ft.Row([gemini_response_container], vertical_alignment=ft.CrossAxisAlignment.START)
        chat_history_display.controls.append(response_row)
        scroll_to_bottom(); page.update()

        last_stream_update_time = time.time(); stream_update_interval = 0.05
        def stream_callback(accumulated_text: str):
            nonlocal last_stream_update_time
            gemini_response_md.value = f"**Gemini:**\n{accumulated_text}▌"
            current_time = time.time()
            if current_time - last_stream_update_time >= stream_update_interval:
                try:
                    page.update(); last_stream_update_time = current_time
                    logging.debug("Stream UI updated.")
                except Exception as update_err: logging.warning(f"Stream update error: {update_err}")

        full_response_text = None
        final_model_content = None
        api_error_message = None
        input_tokens = None
        output_tokens = None
        input_cost = None
        output_cost = None
        total_cost = None

        try:
            selected_model_name = model_dropdown.value; selected_temperature = temperature_slider.value
            try: selected_max_tokens = int(max_tokens_field.value); assert selected_max_tokens > 0
            except (ValueError, AssertionError): selected_max_tokens = config.get("default_max_output_tokens", 8192); max_tokens_field.value = str(selected_max_tokens); snackbar = ft.SnackBar(ft.Text("Invalid Max Tokens. Using default."), open=True); page.overlay.append(snackbar); page.update()

            system_instruction = Content(parts=[Part.from_text(system_prompt_text)], role="system") if system_prompt_text else None
            generation_config = GenerationConfig(temperature=selected_temperature, max_output_tokens=selected_max_tokens)
            current_content = Content(parts=current_prompt_parts, role="user")

            status_bar.value = f"Sending to {selected_model_name}..."; page.update()

            full_response_text, final_model_content, api_error_message, input_tokens, output_tokens, input_cost, output_cost, total_cost = generate_gemini_response(
                model_name=selected_model_name, system_instruction=system_instruction,
                contents=conversation_history + [current_content], generation_config=generation_config,
                safety_settings=safety_settings, stream_update_callback=stream_callback
            )

            input_info_text = ""
            if input_tokens is not None:
                input_info_text = f"({input_tokens} tokens"
                if input_cost is not None:
                    input_info_text += f" | Cost: ${input_cost:.6f}"
                input_info_text += ")"
            else:
                input_info_text = "(Input tokens unavailable)"

            input_tokens_display.value = input_info_text
            try:
                input_tokens_display.update()
            except Exception as input_token_update_err:
                logging.warning(f"Could not update input token/cost display: {input_token_update_err}")

            output_info_text = ""
            cost_breakdown_available = input_cost is not None and output_cost is not None and total_cost is not None

            if output_tokens is not None:
                output_info_text += f"({output_tokens} output tokens"
                if output_cost is not None:
                     output_info_text += f" | Cost: ${output_cost:.6f}"
                output_info_text += ")"

            if cost_breakdown_available:
                 separator = " | " if output_info_text else ""
                 output_info_text += f"{separator}Total Cost: ${total_cost:.6f}"
            elif total_cost is not None:
                 separator = " | " if output_info_text else ""
                 output_info_text += f"{separator}Total Cost (Input Only): ${total_cost:.6f}"
            elif input_tokens is not None:
                 separator = " | " if output_info_text else ""
                 output_info_text += f"{separator}Cost calculation failed"

            if api_error_message:
                logging.error(f"API Client Error: {api_error_message}")
                if response_row in chat_history_display.controls:
                     chat_history_display.controls.remove(response_row)
                chat_history_display.controls.append(ft.Text(f"API Error: {api_error_message}", color=ft.Colors.RED))
                status_bar.value = "API Error occurred."
            elif full_response_text is not None and final_model_content is not None:
                logging.debug(f"Stream finished. Full raw length: {len(full_response_text)}")

                thinking_text, main_text = extract_thinking(full_response_text)
                logging.info(f"Final extracted thinking: {'Yes' if thinking_text else 'None'}")
                logging.info(f"Final extracted main text (first 200): {main_text[:200]}...")

                gemini_response_md.value = f"**Gemini:**\n{main_text}"

                thinking_panel_widget = None
                if thinking_text:
                    thinking_panel_widget = ft.ExpansionPanelList(
                        expand_icon_color=ft.colors.with_opacity(0.6, ft.Colors.ON_SURFACE), elevation=1, divider_color=ft.Colors.OUTLINE_VARIANT,
                        controls=[ft.ExpansionPanel(
                                header=ft.ListTile(title=ft.Text("<Thinking>", italic=True, weight=ft.FontWeight.W_600)),
                                content=ft.Container(ft.Text(thinking_text, selectable=True, italic=True), padding=ft.padding.only(left=15, right=15, bottom=10)))])
                    chat_history_display.controls.append(thinking_panel_widget)
                    logging.info("Added thinking panel dynamically.")

                output_info_display_widget = ft.Text(output_info_text, size=10, italic=True, color=ft.Colors.ON_SURFACE_VARIANT, selectable=True)

                controls_below_response = ft.Row([
                    output_info_display_widget,
                    ft.IconButton(icon=ft.Icons.COPY_ALL_ROUNDED,
                        tooltip="Copy raw response text",
                        on_click=lambda e, text=full_response_text: copy_to_clipboard(e, text)
                   )
                ], alignment=ft.MainAxisAlignment.END, spacing=5)

                try:
                    response_row_index = chat_history_display.controls.index(response_row)
                    chat_history_display.controls.insert(response_row_index + 1, controls_below_response)
                except ValueError:
                    logging.warning("Could not find response_row to insert controls below, appending instead.")
                    chat_history_display.controls.append(controls_below_response)

                try:
                    conversation_history.append(current_content)
                    conversation_history.append(final_model_content)
                    logging.debug(f"Appended to history. New length: {len(conversation_history)}")
                except Exception as history_err:
                    logging.error(f"Error finalizing history: {history_err}")

                status_bar.value = "Response received."
            else:
                logging.warning("Received empty response/content from API client.")
                if response_row in chat_history_display.controls:
                     chat_history_display.controls.remove(response_row)
                empty_response_column = ft.Column([
                    ft.Text("Received empty response.", color=ft.Colors.AMBER),
                    ft.Text(output_info_text, size=10, italic=True, color=ft.Colors.ON_SURFACE_VARIANT) if output_info_text else ft.Container()
                ], spacing=2)
                chat_history_display.controls.append(empty_response_column)
                status_bar.value = "Empty response received."

            scroll_to_bottom()

        except Exception as e:
            error_message = f"Error in send_message: {e}"
            logging.error(error_message, exc_info=True)
            if 'response_row' in locals() and response_row in chat_history_display.controls:
                 chat_history_display.controls.remove(response_row)
            if 'input_tokens_display' in locals():
                input_info_text_exc = ""
                if input_tokens is not None:
                    input_info_text_exc = f"({input_tokens} tokens"
                    if input_cost is not None:
                        input_info_text_exc += f" | Cost: ${input_cost:.6f}"
                    input_info_text_exc += ")"
                else:
                    input_info_text_exc = "(Input tokens unavailable)"
                input_tokens_display.value = input_info_text_exc
                try:
                    input_tokens_display.update()
                except: pass

            chat_history_display.controls.append(ft.Text(f"App Error: {error_message}", color=ft.Colors.RED))
            status_bar.value = "Application Error occurred."
            scroll_to_bottom()
        finally:
            send_button.disabled = False; reset_button.disabled = False
            try: page.update(); logging.debug("Final page update in send_message.")
            except Exception as final_update_err: logging.error(f"Error during final page update: {final_update_err}")

    send_button.on_click = send_message
    user_input.on_submit = send_message

    parameter_bar = ft.Container(content=ft.Column([ft.Row([model_dropdown, ft.VerticalDivider(width=5), ft.Text("Temp:", width=45, tooltip="Temperature"), temperature_label, temperature_slider, ft.VerticalDivider(width=5), max_tokens_field], alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=5, wrap=False), ft.Row([system_prompt_field], expand=True) ]), padding=ft.padding.symmetric(horizontal=10, vertical=5), border=ft.border.only(bottom=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT)))

    def refresh_file_explorer(e):
        root_dir = config.get("root_directory")
        if root_dir:
            status_bar.value = f"Refreshing files from {root_dir}..."; page.update()
            logging.info(f"Manual refresh triggered for: {root_dir}")
            try:
                populate_file_explorer(root_dir)
                status_bar.value = f"Files reloaded from {root_dir}."; page.update()
            except Exception as populate_err:
                status_bar.value = f"Error refreshing files: {populate_err}"
                logging.error("Refresh error", exc_info=True)
                page.update()
        else:
            status_bar.value = "Set 'root_directory' in config.json to refresh."; page.update()
            logging.warning("Refresh skipped: root_directory not set.")

    refresh_button = ft.IconButton(ft.Icons.REFRESH_ROUNDED, tooltip="Refresh File List", on_click=refresh_file_explorer)

    left_panel = ft.Container(content=ft.Column([
        ft.Row([
            ft.Text("Project Files", style=ft.TextThemeStyle.TITLE_MEDIUM, expand=True),
            refresh_button
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        ft.Divider(),
        file_explorer_controls # Reference the Column control again
    ], expand=True), # Removed scroll=... from Column as it's the default
    width=300, padding=10, border=ft.border.all(1, ft.Colors.OUTLINE), border_radius=ft.border_radius.all(5))
    right_panel = ft.Container(content=ft.Column([chat_history_display, ft.Row([user_input, send_button, reset_button], alignment=ft.MainAxisAlignment.END), status_bar], expand=True), expand=True, padding=10)
    main_row = ft.Row([left_panel, right_panel], expand=True, vertical_alignment=ft.CrossAxisAlignment.STRETCH)
    try: page.add(parameter_bar, main_row); logging.info("Main layout added.")
    except Exception as layout_err: logging.error("Layout construction error", exc_info=True); page.add(ft.Text(f"Fatal Layout Error: {layout_err}", color=ft.Colors.RED))

    root_dir = config.get("root_directory");
    if root_dir:
        try: populate_file_explorer(root_dir)
        except Exception as populate_err: status_bar.value = f"Error populating files: {populate_err}"; logging.error("Populate error", exc_info=True)
    else: status_bar.value = "Set 'root_directory' in config.json"; logging.warning(status_bar.value)
    page.update()

if __name__ == "__main__":
    logging.info("Starting Flet app...")
    ft.app(target=main)
    logging.info("--- Application Finished ---"); print("Flet app finished.")
