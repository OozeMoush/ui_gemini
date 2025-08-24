import flet as ft
import time
import pathlib
# Logging and Config are now handled by importing the modules
import logger_setup # Initializes logging
import config_manager # Loads configuration
import logging # Still needed for logging calls within this file
from google import genai
from google.genai.types import GenerateContentConfig, ThinkingConfig
# Import necessary UI components, state variables, and helpers from ui_components
# Ensure ui_components import reflects the reverted state (using file_checkboxes)
import ui_components
from ui_components import (
    model_dropdown, temperature_slider, temperature_label, max_tokens_field,
    system_prompt_field, file_checkboxes, file_explorer_controls,
    chat_history_display, user_input, send_button, cancel_button, reset_button, status_bar,
    populate_file_explorer, scroll_to_bottom, extract_thinking,
    conversation_history,
    files_sent_in_convo, is_sending, cancel_requested,
    thinking_budget_slider, thinking_budget_label, thinking_auto_budget_switch,
    system_prompt_template_dropdown,
    # Session management components
    session_dropdown, new_session_name_field, create_session_button,
    delete_session_button, session_info_text, update_session_dropdown_options,
    update_session_info
)
# Import the new client function
from vertex_ai_client import generate_gemini_response, calculate_cost
# Import conversation manager
from conversation_manager import ConversationManager
# Import common types
from gen_ai_types import Part, Content

config = config_manager.get_config()

# --- Conversation Manager Initialization ---
conversation_manager = ConversationManager()

# --- Helper Functions ---
def format_blockquotes_for_readability(text: str) -> str:
    """
    blockquoteをより読みやすい形式にフォーマット
    Markdownの > 記法を視覚的に改善し、改行も適切に処理
    """
    import re
    
    # まず通常の改行を適切に処理
    # 連続する改行を保持し、単一改行も維持
    text = re.sub(r'\n\n+', '\n\n', text)  # 3つ以上の連続改行を2つに統一
    
    # blockquoteパターンをマッチ
    def replace_blockquote(match):
        quote_content = match.group(1)
        lines = quote_content.strip().split('\n')
        # > を削除して内容を取得
        clean_lines = []
        for line in lines:
            cleaned = line.lstrip('> ').rstrip()
            clean_lines.append(cleaned)
        
        # 改善されたフォーマット：引用符記号を使用
        formatted_lines = []
        for line in clean_lines:
            if line.strip():
                formatted_lines.append(f"💬 {line}")
            else:
                formatted_lines.append("")  # 空行も保持
        
        return '\n'.join(formatted_lines)
    
    # マルチライン blockquote パターン（改良版）
    pattern = r'((?:^|\n)(?:>\s*.*(?:\n|$))+)'
    formatted_text = re.sub(pattern, replace_blockquote, text, flags=re.MULTILINE)
    
    # 改行の正規化：Markdown用の改行処理
    # 単一改行を維持し、段落間の空行も保持
    formatted_text = re.sub(r'([^\n])\n([^\n])', r'\1  \n\2', formatted_text)  # Markdown改行
    
    return formatted_text

# --- Gen AI Initialization ---
gen_ai_initialized = False
init_error_message = ""
try:
    project_id = config.get("vertex_ai_project_id")
    location = config.get("vertex_ai_location")
    if project_id and location and project_id != "YOUR_PROJECT_ID" and location != "YOUR_LOCATION":
        # Test client initialization
        import os
        os.environ['GOOGLE_GENAI_USE_VERTEXAI'] = 'True'
        os.environ['GOOGLE_CLOUD_PROJECT'] = project_id
        os.environ['GOOGLE_CLOUD_LOCATION'] = location
        
        from google.genai.types import HttpOptions
        client = genai.Client(
            http_options=HttpOptions(api_version="v1"),
            vertexai=True,
            project=project_id,
            location=location
        )
        gen_ai_initialized = True
        logging.info(f"Gen AI initialized for project {project_id} in {location}.")
        print(f"Gen AI initialized for project {project_id} in {location}.")
    else:
        init_error_message = "Project ID or location not configured properly in config.json."
        logging.warning(init_error_message); print(f"Warning: {init_error_message}")
except Exception as e:
    init_error_message = f"Error initializing Gen AI: {e}"; logging.error(init_error_message, exc_info=True); print(f"Error: {init_error_message}")

# --- Global variables ---
refresh_button = None
current_session_name = "default"

# --- Main Application Logic ---
def main(page: ft.Page):
    page.title = "Gemini UI Chat"
    page.theme_mode = ft.ThemeMode.DARK # Keep Dark theme
    
    # カスタムダークテーマでblockquoteを改善
    page.theme = ft.Theme(
        color_scheme=ft.ColorScheme(
            # blockquoteのバックグラウンドをより読みやすい色に設定
            surface_variant=ft.Colors.GREY_900,  # blockquoteの背景
            on_surface_variant=ft.Colors.GREY_100,  # blockquote内のテキスト色
        )
    )
    
    logging.info("Main UI function started.")
    # Assign page context to UI elements that need it for updates
    status_bar.page = page; file_explorer_controls.page = page; chat_history_display.page = page
    global files_sent_in_convo

    # Display init error via SnackBar using the correct method
    if init_error_message:
        snackbar = ft.SnackBar(ft.Text(f"Gen AI Init Error: {init_error_message}"), open=True)
        if hasattr(page, 'overlay'):
             page.overlay.append(snackbar)
        else:
             logging.warning("Page overlay not ready for init error snackbar.")

    # --- Load previous conversation on startup ---
    def load_previous_conversation():
        """アプリ起動時に前回の会話を復元"""
        try:
            loaded_history = conversation_manager.load_conversation()
            if loaded_history:
                # グローバルな会話履歴を更新
                ui_components.conversation_history.clear()
                ui_components.conversation_history.extend(loaded_history)
                
                # UIに会話履歴を表示
                for content in loaded_history:
                    if content.role == "user":
                        user_text = "\n".join([part.text for part in content.parts if hasattr(part, 'text')])
                        chat_history_display.controls.append(
                            ft.Text(f"You: {user_text}", selectable=True)
                        )
                    elif content.role == "model":
                        model_text = "\n".join([part.text for part in content.parts if hasattr(part, 'text')])
                        formatted_model_text = format_blockquotes_for_readability(model_text)
                        response_md = ft.Markdown(f"**Gemini:**\n{formatted_model_text}", selectable=True, code_theme="dracula", extension_set=ft.MarkdownExtensionSet.GITHUB_WEB, auto_follow_links=True)
                        chat_history_display.controls.append(response_md)
                
                status_bar.value = f"前回の会話を復元しました ({len(loaded_history)} メッセージ)"
                logging.info(f"前回の会話を復元: {len(loaded_history)} メッセージ")
                scroll_to_bottom()
            else:
                status_bar.value = "新しい会話を開始します"
        except Exception as e:
            logging.error(f"会話復元エラー: {e}")
            status_bar.value = "会話復元に失敗しました"

    def save_current_conversation():
        """現在の会話を保存"""
        try:
            if ui_components.conversation_history:
                success = conversation_manager.save_conversation(ui_components.conversation_history)
                if success:
                    logging.debug("会話履歴を自動保存しました")
                else:
                    logging.warning("会話履歴の自動保存に失敗")
        except Exception as e:
            logging.error(f"自動保存エラー: {e}")

    def update_temp_label(e): temperature_label.value = f"{e.control.value:.2f}"; page.update()
    temperature_slider.on_change = update_temp_label

    # 思考コントロールの初期化
    from ui_components import update_thinking_for_model
    update_thinking_for_model()

    def reset_conversation(e):
        global files_sent_in_convo
        logging.info("Resetting conversation."); 
        
        # 現在の会話を保存してからリセット
        save_current_conversation()
        
        conversation_history.clear(); files_sent_in_convo = False
        chat_history_display.controls.clear()
        # Reset checkboxes stored in the dictionary (Reverted logic)
        # Use the imported file_checkboxes directly
        for checkbox in ui_components.file_checkboxes.keys():
            checkbox.value = False
        try:
            # Update the Column containing checkboxes
            ui_components.file_explorer_controls.update()
        except Exception as control_update_err:
             # Fallback might be needed if column update fails
             logging.warning(f"Failed update on reset trying individuals: {control_update_err}")
             checkbox_update_errors = 0
             for checkbox in ui_components.file_checkboxes.keys():
                 try: checkbox.update()
                 except Exception as cb_err: checkbox_update_errors += 1
             if checkbox_update_errors > 0: logging.warning(f"{checkbox_update_errors} checkboxes failed to update individually on reset.")

        system_prompt_field.value = config.get("default_system_prompt", "")
        status_bar.value = "Conversation reset."
        
        # セッション情報を更新
        current_session = conversation_manager.current_session
        update_session_info(current_session, 0)
        
        page.update()
    reset_button.on_click = reset_conversation

    # --- Copy Button Handler ---
    def copy_to_clipboard(e, text_to_copy):
        logging.info(f"Copying text to clipboard (length: {len(text_to_copy)}).")
        page.set_clipboard(text_to_copy)
        snackbar = ft.SnackBar(ft.Text("Response text copied!"), open=True, duration=2000)
        page.overlay.append(snackbar)
        page.update()

    def cancel_send(e):
        """送信をキャンセルする"""
        ui_components.cancel_requested = True
        status_bar.value = "キャンセル中..."
        logging.info("ユーザーが送信をキャンセルしました")
        page.update()

    def send_message(e):
        global files_sent_in_convo
        
        # 既に送信中の場合は重複送信を防ぐ
        if ui_components.is_sending:
            logging.warning("Send attempt blocked: already sending")
            return
        
        # キャンセルリクエストをリセット
        ui_components.cancel_requested = False
        
        prompt_text = user_input.value.strip()
        system_prompt_text = system_prompt_field.value.strip()
        if not prompt_text: snackbar = ft.SnackBar(ft.Text("Please enter a prompt."), open=True); page.overlay.append(snackbar); page.update(); return
        if not gen_ai_initialized: logging.warning("Send: Gen AI not initialized."); snackbar = ft.SnackBar(ft.Text(f"Gen AI not initialized. Err: {init_error_message}"), open=True); page.overlay.append(snackbar); page.update(); return

        # プロンプト準備
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
                                else:
                                    logging.warning(f"Selected path is not a file: {file_path_str}")
                            except Exception as read_err:
                                file_name = file_path.name if 'file_path' in locals() and hasattr(file_path, 'name') else file_path_str
                                logging.warning(f"Error reading selected file {file_name}: {read_err}")
                                chat_history_display.controls.append(ft.Text(f"Error reading {file_name}: {read_err}", color=ft.Colors.ORANGE))
                                scroll_to_bottom(); page.update()

                if selected_files_this_turn: files_sent_in_convo = True; files_appended_now = True; logging.info(f"Prepending files: {', '.join(selected_files_this_turn)}")
            except Exception as proc_err: 
                logging.error("File processing error.", exc_info=True)
                chat_history_display.controls.append(ft.Text(f"Error processing selected files: {proc_err}", color=ft.Colors.RED))
                # エラー時のボタン状態リセット
                ui_components.is_sending = False
                send_button.visible = True
                cancel_button.visible = False
                reset_button.disabled = False
                status_bar.value = "Error processing files."
                scroll_to_bottom()
                page.update()
                return

        # 事前に入力トークン数を計算
        current_content = Content(parts=current_prompt_parts, role="user")
        system_instruction = Content(parts=[Part.from_text(system_prompt_text)], role="system") if system_prompt_text else None
        
        try:
            # Gen AI クライアント初期化
            from config_manager import get_config
            from google import genai
            from google.genai.types import HttpOptions
            config = get_config()
            project_id = config.get("vertex_ai_project_id")
            location = config.get("vertex_ai_location")
            
            if project_id and location and project_id != "YOUR_PROJECT_ID" and location != "YOUR_LOCATION":
                client = genai.Client(
                    http_options=HttpOptions(api_version="v1"),
                    vertexai=True,
                    project=project_id,
                    location=location
                )
                
                # 入力トークン数を事前計算
                from vertex_ai_client import get_accurate_token_count
                pre_input_tokens, _ = get_accurate_token_count(
                    client, model_dropdown.value, conversation_history + [current_content], system_instruction
                )
            else:
                pre_input_tokens = None
        except Exception as token_calc_err:
            logging.warning(f"Pre-calculation of input tokens failed: {token_calc_err}")
            pre_input_tokens = None

        # 入力トークン表示（事前計算値）
        input_info_text = ""
        if pre_input_tokens is not None:
            input_info_text = f"Input: {pre_input_tokens} tokens (計算中...)"
        else:
            input_info_text = "Input tokens: 計算中..."

        input_tokens_display = ft.Text(input_info_text, size=10, italic=True, color=ft.Colors.ON_SURFACE_VARIANT, selectable=True)
        user_message_column = ft.Column([
            ft.Text(f"You: {prompt_text}", selectable=True),
            input_tokens_display
        ], spacing=2)

        chat_history_display.controls.append(user_message_column); user_input.value = ""; user_input.focus()
        scroll_to_bottom(); page.update()

        # 送信状態を設定してボタンを切り替え（エラーチェック後に設定）
        ui_components.is_sending = True
        send_button.visible = False
        cancel_button.visible = True
        reset_button.disabled = True
        status_bar.value = "Processing..."
        # UIの更新を強制
        try:
            send_button.update()
            cancel_button.update()
            reset_button.update()
            status_bar.update()
            page.update()
        except Exception as ui_update_err:
            logging.warning(f"UI update error during send preparation: {ui_update_err}")
            page.update()

        gemini_response_md = ft.Markdown(f"**Gemini:**\n▌", selectable=True, code_theme="dracula", extension_set=ft.MarkdownExtensionSet.GITHUB_WEB, auto_follow_links=True, on_tap_link=lambda e: page.launch_url(e.data))
        gemini_response_container = ft.Container(content=gemini_response_md, padding=ft.padding.only(bottom=10), expand=True)
        response_row = ft.Row([gemini_response_container], vertical_alignment=ft.CrossAxisAlignment.START)
        chat_history_display.controls.append(response_row)
        scroll_to_bottom(); page.update()

        last_stream_update_time = time.time(); stream_update_interval = 0.05
        def stream_callback(accumulated_text: str):
            nonlocal last_stream_update_time
            # キャンセルがリクエストされた場合は更新をスキップ
            if ui_components.cancel_requested:
                return False  # キャンセル信号を返す
            
            gemini_response_md.value = f"**Gemini:**\n{accumulated_text}▌"
            current_time = time.time()
            if current_time - last_stream_update_time >= stream_update_interval:
                try:
                    page.update(); last_stream_update_time = current_time
                except Exception as update_err: logging.warning(f"Stream update error: {update_err}")
            return True  # 続行信号を返す

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

            # 新しいAPIに合わせて辞書形式で設定
            generation_config = {
                "temperature": selected_temperature,
                "max_output_tokens": selected_max_tokens
            }

            # Thinking設定を取得
            thinking_budget = int(thinking_budget_slider.value)
            logging.debug(f"UI思考バジェット値: {thinking_budget}, 自動バジェット: {thinking_auto_budget_switch.value}")

            status_bar.value = f"Sending to {selected_model_name}..."; page.update()

            full_response_text, final_model_content, api_error_message, input_tokens, output_tokens, input_cost, output_cost, total_cost, thinking_text = generate_gemini_response(
                model_name=selected_model_name, system_instruction=system_instruction,
                contents=conversation_history + [current_content], generation_config=generation_config,
                safety_settings={}, stream_update_callback=stream_callback,
                thinking_budget=thinking_budget,
                thinking_auto_budget=thinking_auto_budget_switch.value
            )

            # 入力トークン表示を更新（正確な値）
            final_input_info_text = ""
            if input_tokens is not None:
                final_input_info_text = f"Input: {input_tokens} tokens"
                if input_cost is not None:
                    final_input_info_text += f" | Cost: ${input_cost:.6f}"
            else:
                final_input_info_text = "Input tokens: 取得できませんでした"

            input_tokens_display.value = final_input_info_text
            try:
                input_tokens_display.update()
            except Exception as input_token_update_err:
                logging.warning(f"Could not update input token/cost display: {input_token_update_err}")

            output_info_text = ""
            cost_breakdown_available = input_cost is not None and output_cost is not None and total_cost is not None

            if output_tokens is not None:
                output_info_text += f"Output: {output_tokens} tokens (推定)"
                if output_cost is not None:
                     output_info_text += f" | Cost: ${output_cost:.6f}"

            if cost_breakdown_available:
                 separator = " | " if output_info_text else ""
                 output_info_text += f"{separator}Total: ${total_cost:.6f}"
            elif total_cost is not None:
                 separator = " | " if output_info_text else ""
                 output_info_text += f"{separator}Total (Input Only): ${total_cost:.6f}"
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

                # 古いextract_thinking関数の代わりに、APIから返されたthinking_textを使用
                if thinking_text:
                    main_text = full_response_text
                    logging.info(f"Thinking text received from API: {'Yes' if thinking_text else 'None'}")
                else:
                    # fallbackとして従来の抽出方法も試す
                    thinking_text, main_text = extract_thinking(full_response_text)
                    logging.info(f"Extracted thinking using regex: {'Yes' if thinking_text else 'None'}")
                
                logging.info(f"Final main text (first 200): {main_text[:200]}...")

                # blockquoteの見た目を改善するために前処理
                formatted_main_text = format_blockquotes_for_readability(main_text)
                gemini_response_md.value = f"**Gemini:**\n{formatted_main_text}"

                thinking_panel_widget = None
                if thinking_text:
                    thinking_panel_widget = ft.ExpansionPanelList(
                        expand_icon_color=ft.Colors.ON_SURFACE_VARIANT, elevation=1, divider_color=ft.Colors.OUTLINE_VARIANT,
                        controls=[ft.ExpansionPanel(
                                header=ft.ListTile(title=ft.Text("🤔 Thinking Process", italic=True, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE)),
                                content=ft.Container(ft.Text(thinking_text, selectable=True, italic=True, color=ft.Colors.ON_SURFACE), padding=ft.padding.only(left=15, right=15, bottom=10)))])
                    chat_history_display.controls.append(thinking_panel_widget)
                    logging.info("Added thinking panel with API thinking text.")

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
                    input_info_text_exc = f"Input: {input_tokens} tokens"
                    if input_cost is not None:
                        input_info_text_exc += f" | Cost: ${input_cost:.6f}"
                else:
                    input_info_text_exc = "Input tokens: エラーが発生しました"
                input_tokens_display.value = input_info_text_exc
                try:
                    input_tokens_display.update()
                except: pass

            chat_history_display.controls.append(ft.Text(f"App Error: {error_message}", color=ft.Colors.RED))
            status_bar.value = "Application Error occurred."
            scroll_to_bottom()
        finally:
            # キャンセル状態を確認（リセット前に）
            was_cancelled = ui_components.cancel_requested
            
            # 送信状態をリセットしてボタンを元に戻す
            ui_components.is_sending = False
            ui_components.cancel_requested = False
            send_button.visible = True
            cancel_button.visible = False
            reset_button.disabled = False
            
            # キャンセルされた場合の処理
            if was_cancelled:
                status_bar.value = "送信がキャンセルされました"
                # 未完了の応答があれば削除
                if 'response_row' in locals() and response_row in chat_history_display.controls:
                    chat_history_display.controls.remove(response_row)
                scroll_to_bottom()
                logging.info("送信処理がキャンセルされました")
            elif not api_error_message:  # エラーがない場合のみ保存
                # メッセージ送信後に自動保存
                save_current_conversation()
                
                # セッション情報を更新
                try:
                    current_session = conversation_manager.current_session
                    message_count = len(ui_components.conversation_history)
                    update_session_info(current_session, message_count)
                except Exception as session_update_err:
                    logging.warning(f"セッション情報更新エラー: {session_update_err}")
            
            try: page.update()
            except Exception as final_update_err: logging.error(f"Error during final page update: {final_update_err}")

    # デバウンス機能付きの送信ハンドラー
    last_submit_time = [0]  # リストを使用してnonlocalスコープを回避
    
    def debounced_send_message(e):
        """デバウンス機能付きの送信処理"""
        current_time = time.time()
        # 200ms以内の連続送信を防ぐ
        if current_time - last_submit_time[0] < 0.2:
            logging.info("Send attempt debounced (too frequent)")
            return
        last_submit_time[0] = current_time
        send_message(e)
    
    send_button.on_click = debounced_send_message
    cancel_button.on_click = cancel_send
    user_input.on_submit = debounced_send_message

    parameter_bar = ft.Container(content=ft.Column([
        ft.Row([
            model_dropdown, 
            ft.VerticalDivider(width=5), 
            ft.Text("Temp:", width=45, tooltip="Temperature"), 
            temperature_label, 
            temperature_slider, 
            ft.VerticalDivider(width=5), 
            max_tokens_field
        ], alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=5, wrap=False), 
        ft.Row([
            thinking_auto_budget_switch,  # 自動バジェットスイッチ
            ft.VerticalDivider(width=5),
            ft.Text("Budget:", width=50, tooltip="思考バジェット (0=無効)", color=ft.Colors.ON_SURFACE),
            thinking_budget_label,
            thinking_budget_slider,
        ], alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=5, wrap=False),
        ft.Row([
            system_prompt_template_dropdown,
            ft.VerticalDivider(width=5),
            system_prompt_field
        ], alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=5, expand=True)
    ]), padding=ft.padding.symmetric(horizontal=10, vertical=5), border=ft.border.only(bottom=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT)))

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

    # --- Session Management Functions ---
    def refresh_session_list():
        """セッション一覧を更新"""
        try:
            session_list = conversation_manager.get_session_list()
            if not session_list:
                session_list = ["default"]
            
            current_session = conversation_manager.current_session
            update_session_dropdown_options(session_list, current_session)
            
            # セッション情報を更新
            session_info = conversation_manager.get_session_info(current_session)
            message_count = session_info.get("total_messages", 0) if session_info else 0
            update_session_info(current_session, message_count)
            
            # UI更新を強制的に実行
            try:
                session_dropdown.update()
                session_info_text.update()
                page.update()
            except Exception as ui_update_err:
                logging.warning(f"セッションUI更新エラー: {ui_update_err}")
            
            logging.info(f"セッション一覧を更新: {session_list}, 現在のセッション: {current_session}")
        except Exception as e:
            logging.error(f"セッション一覧更新エラー: {e}")

    def switch_session(e):
        """セッションを切り替え"""
        try:
            new_session = session_dropdown.value
            if new_session == conversation_manager.current_session:
                return
            
            # 現在の会話を保存
            save_current_conversation()
            
            # セッションを切り替え
            conversation_manager.set_current_session(new_session)
            
            # 会話履歴をクリアしてから新しいセッションを読み込み
            ui_components.conversation_history.clear()
            chat_history_display.controls.clear()
            
            # 新しいセッションの会話を読み込み
            loaded_history = conversation_manager.load_conversation(new_session)
            if loaded_history:
                ui_components.conversation_history.extend(loaded_history)
                
                # UIに表示
                for content in loaded_history:
                    if content.role == "user":
                        user_text = "\n".join([part.text for part in content.parts if hasattr(part, 'text')])
                        chat_history_display.controls.append(
                            ft.Text(f"You: {user_text}", selectable=True)
                        )
                    elif content.role == "model":
                        model_text = "\n".join([part.text for part in content.parts if hasattr(part, 'text')])
                        formatted_model_text = format_blockquotes_for_readability(model_text)
                        response_md = ft.Markdown(f"**Gemini:**\n{formatted_model_text}", selectable=True, code_theme="dracula", extension_set=ft.MarkdownExtensionSet.GITHUB_WEB, auto_follow_links=True)
                        chat_history_display.controls.append(response_md)
            
            # セッション情報を更新
            session_info = conversation_manager.get_session_info(new_session)
            message_count = session_info.get("total_messages", 0) if session_info else 0
            update_session_info(new_session, message_count)
            
            status_bar.value = f"セッション '{new_session}' に切り替えました ({message_count} メッセージ)"
            scroll_to_bottom()
            page.update()
            
        except Exception as e:
            logging.error(f"セッション切り替えエラー: {e}")
            status_bar.value = f"セッション切り替えに失敗: {e}"
            page.update()

    def create_new_session(e):
        """新しいセッションを作成"""
        try:
            new_name = new_session_name_field.value.strip()
            if not new_name:
                snackbar = ft.SnackBar(ft.Text("セッション名を入力してください"), open=True)
                page.overlay.append(snackbar)
                page.update()
                return
            
            # セッション名の重複チェック
            existing_sessions = conversation_manager.get_session_list()
            if new_name in existing_sessions:
                snackbar = ft.SnackBar(ft.Text("そのセッション名は既に存在します"), open=True)
                page.overlay.append(snackbar)
                page.update()
                return
            
            # 現在の会話を保存
            save_current_conversation()
            
            # 新しいセッションに切り替え
            conversation_manager.set_current_session(new_name)
            
            # 会話履歴をクリア
            ui_components.conversation_history.clear()
            chat_history_display.controls.clear()
            
            # 空のセッションファイルを作成
            conversation_manager.save_conversation([])
            
            # セッション一覧を更新
            refresh_session_list()
            
            # 入力フィールドをクリア
            new_session_name_field.value = ""
            if hasattr(new_session_name_field, 'page') and new_session_name_field.page:
                new_session_name_field.update()
            
            status_bar.value = f"新しいセッション '{new_name}' を作成しました"
            update_session_info(new_name, 0)
            
            # UI更新を強制実行
            page.update()
            
        except Exception as e:
            logging.error(f"セッション作成エラー: {e}")
            status_bar.value = f"セッション作成に失敗: {e}"
            page.update()

    def delete_current_session(e):
        """現在のセッションを削除"""
        try:
            current_session = conversation_manager.current_session
            
            # defaultセッションの削除を防ぐ
            if current_session == "default":
                snackbar = ft.SnackBar(ft.Text("defaultセッションは削除できません"), open=True)
                page.overlay.append(snackbar)
                page.update()
                return
            
            # 確認ダイアログを表示
            def confirm_delete(e):
                dialog.open = False
                page.update()
                
                try:
                    # セッションを削除
                    success = conversation_manager.delete_session(current_session)
                    if success:
                        # defaultセッションに切り替え
                        conversation_manager.set_current_session("default")
                        
                        # 会話履歴をクリア
                        ui_components.conversation_history.clear()
                        chat_history_display.controls.clear()
                        
                        # defaultセッションを読み込み
                        loaded_history = conversation_manager.load_conversation("default")
                        if loaded_history:
                            ui_components.conversation_history.extend(loaded_history)
                            
                            for content in loaded_history:
                                if content.role == "user":
                                    user_text = "\n".join([part.text for part in content.parts if hasattr(part, 'text')])
                                    chat_history_display.controls.append(
                                        ft.Text(f"You: {user_text}", selectable=True)
                                    )
                                elif content.role == "model":
                                    model_text = "\n".join([part.text for part in content.parts if hasattr(part, 'text')])
                                    response_md = ft.Markdown(f"**Gemini:**\n{model_text}", selectable=True, code_theme="dracula", extension_set=ft.MarkdownExtensionSet.GITHUB_WEB)
                                    chat_history_display.controls.append(response_md)
                        
                        # UI更新
                        refresh_session_list()
                        status_bar.value = f"セッション '{current_session}' を削除しました"
                        scroll_to_bottom()
                    else:
                        status_bar.value = "セッション削除に失敗しました"
                        page.update()
                        
                except Exception as delete_err:
                    logging.error(f"セッション削除エラー: {delete_err}")
                    status_bar.value = f"セッション削除エラー: {delete_err}"
                    page.update()
            
            def cancel_delete(e):
                dialog.open = False
                page.update()
            
            dialog = ft.AlertDialog(
                modal=True,
                title=ft.Text("セッション削除の確認"),
                content=ft.Text(f"セッション '{current_session}' を削除しますか？\nこの操作は取り消せません。"),
                actions=[
                    ft.TextButton("キャンセル", on_click=cancel_delete),
                    ft.TextButton("削除", on_click=confirm_delete, style=ft.ButtonStyle(color=ft.Colors.ERROR)),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
            
            page.overlay.append(dialog)
            dialog.open = True
            page.update()
            
        except Exception as e:
            logging.error(f"セッション削除準備エラー: {e}")
            status_bar.value = f"セッション削除準備エラー: {e}"
            page.update()

    # セッション管理のイベントハンドラーを設定
    session_dropdown.on_change = switch_session
    create_session_button.on_click = create_new_session
    delete_session_button.on_click = delete_current_session
    new_session_name_field.on_submit = create_new_session

    left_panel = ft.Container(content=ft.Column([
        # Session Management Section
        ft.Row([
            ft.Text("Sessions", style=ft.TextThemeStyle.TITLE_MEDIUM, expand=True),
        ]),
        ft.Row([
            session_dropdown,
            create_session_button,
            delete_session_button
        ], spacing=5),
        ft.Row([
            new_session_name_field
        ], spacing=5),
        session_info_text,
        ft.Divider(),
        
        # File Explorer Section
        ft.Row([
            ft.Text("Project Files", style=ft.TextThemeStyle.TITLE_MEDIUM, expand=True),
            refresh_button
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        ft.Divider(),
        file_explorer_controls # Reference the Column control again
    ], expand=True), # Removed scroll=... from Column as it's the default
    width=300, padding=10, border=ft.border.all(1, ft.Colors.OUTLINE), border_radius=ft.border_radius.all(5))
    
    # 新しいタブベースのチャット表示を使用
    right_panel = ft.Container(content=ft.Column([
        chat_history_display,  # 従来のチャット表示に戻す
        ft.Row([user_input, send_button, cancel_button, reset_button], alignment=ft.MainAxisAlignment.END), 
        status_bar
    ], expand=True), expand=True, padding=10)
    main_row = ft.Row([left_panel, right_panel], expand=True, vertical_alignment=ft.CrossAxisAlignment.STRETCH)
    try: page.add(parameter_bar, main_row)
    except Exception as layout_err: logging.error("Layout construction error", exc_info=True); page.add(ft.Text(f"Fatal Layout Error: {layout_err}", color=ft.Colors.RED))

    root_dir = config.get("root_directory");
    if root_dir:
        try: populate_file_explorer(root_dir)
        except Exception as populate_err: status_bar.value = f"Error populating files: {populate_err}"; logging.error("Populate error", exc_info=True)
    else: status_bar.value = "Set 'root_directory' in config.json"; logging.warning(status_bar.value)
    
    # セッション管理を初期化
    refresh_session_list()
    
    # 思考コントロールの初期化
    from ui_components import update_thinking_for_model
    update_thinking_for_model()
    
    # 前回の会話を復元
    load_previous_conversation()
    
    page.update()

if __name__ == "__main__":
    logging.info("Starting Flet app...")
    ft.app(target=main)
    logging.info("--- Application Finished ---"); print("Flet app finished.")
