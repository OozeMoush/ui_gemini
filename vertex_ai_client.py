import logging
import time
import os
from google import genai
from google.genai.types import GenerateContentConfig, ThinkingConfig, HttpOptions
from vertexai.generative_models import Content, Part
# Import safety settings and initialization status from main module (or state manager later)
# For now, assume safety_settings are defined/imported where this function is called
# and vertex_ai_initialized is checked before calling.

# --- Cost Calculation ---
# Gemini 2.5 Flash料金 (正確な料金、2025年最新)
GEMINI_25_FLASH_INPUT_PRICE = 0.15  # $/1M tokens (text/image/video)
GEMINI_25_FLASH_INPUT_AUDIO_PRICE = 1.0  # $/1M tokens (audio)
GEMINI_25_FLASH_OUTPUT_NON_THINKING_PRICE = 0.60  # $/1M tokens (非思考)
GEMINI_25_FLASH_OUTPUT_THINKING_PRICE = 3.50  # $/1M tokens (思考含む)

# Gemini 2.5 Pro料金
GEMINI_25_PRO_INPUT_PRICE_TIER1 = 1.25  # $/1M tokens for <= 200K input
GEMINI_25_PRO_INPUT_PRICE_TIER2 = 2.5   # $/1M tokens for > 200K input
GEMINI_25_PRO_OUTPUT_PRICE_TIER1 = 10.0 # $/1M tokens for <= 200K output
GEMINI_25_PRO_OUTPUT_PRICE_TIER2 = 15.0 # $/1M tokens for > 200K output

# Gemini 2.0 Flash料金
GEMINI_20_FLASH_INPUT_PRICE = 0.15  # $/1M tokens (text/image/video)
GEMINI_20_FLASH_INPUT_AUDIO_PRICE = 1.0  # $/1M tokens (audio)
GEMINI_20_FLASH_OUTPUT_PRICE = 0.60  # $/1M tokens

TOKEN_THRESHOLD_200K = 200000  # 200K tokenのティア境界

def get_accurate_token_count(client, model_name: str, contents: list, system_instruction: Content = None) -> tuple[int, int]:
    """
    countTokens APIを使用して正確なトークン数を取得する
    
    Returns:
        tuple[input_tokens, output_tokens_estimate]: (入力トークン数, 出力トークン数推定)
    """
    try:
        # Gen AI SDK用のコンテンツ変換
        gen_ai_contents = []
        for content in contents:
            if content.role == "system":
                continue  # system instructionは別途処理
            
            # partsからテキストを抽出
            text_parts = []
            for part in content.parts:
                if hasattr(part, 'text'):
                    text_parts.append(part.text)
            
            combined_text = "\n".join(text_parts)
            gen_ai_contents.append({
                "role": content.role,
                "parts": [{"text": combined_text}]
            })

        # System instructionを含める場合
        if system_instruction and system_instruction.parts:
            prompt_with_system = f"[SYSTEM INSTRUCTION]: {system_instruction.parts[0].text}\n\n"
            if gen_ai_contents and gen_ai_contents[-1]["role"] == "user":
                gen_ai_contents[-1]["parts"][0]["text"] = prompt_with_system + gen_ai_contents[-1]["parts"][0]["text"]

        # countTokens APIを呼び出し
        response = client.models.count_tokens(
            model=model_name,
            contents=gen_ai_contents
        )
        
        input_tokens = response.total_tokens or 0
        # 出力トークンは実際の生成後に正確に分かるため、ここでは推定しない
        output_tokens_estimate = 0
        
        logging.info(f"Accurate token count - Input: {input_tokens} tokens")
        return input_tokens, output_tokens_estimate
        
    except Exception as e:
        logging.error(f"Failed to get accurate token count: {e}")
        # フォールバック：推定計算
        estimated_input_tokens = sum(len(content["parts"][0]["text"]) for content in gen_ai_contents) // 4
        return estimated_input_tokens, 0

def calculate_cost_accurate(model_name: str, input_tokens: int, output_tokens: int, has_thinking: bool = False) -> tuple[float, float, float]:
    """
    正確な料金体系に基づいてコストを計算する
    
    Args:
        model_name: モデル名
        input_tokens: 入力トークン数
        output_tokens: 出力トークン数  
        has_thinking: 思考トークンが含まれているか
        
    Returns:
        tuple[input_cost, output_cost, total_cost]
    """
    if input_tokens is None or input_tokens <= 0:
        return 0.0, 0.0, 0.0
    
    input_cost = 0.0
    output_cost = 0.0
    
    # モデル別料金計算
    model_lower = model_name.lower()
    
    if "gemini-2.5-flash" in model_lower:
        # Gemini 2.5 Flash料金
        input_cost = (input_tokens / 1_000_000) * GEMINI_25_FLASH_INPUT_PRICE
        
        if output_tokens > 0:
            if has_thinking:
                output_cost = (output_tokens / 1_000_000) * GEMINI_25_FLASH_OUTPUT_THINKING_PRICE
            else:
                output_cost = (output_tokens / 1_000_000) * GEMINI_25_FLASH_OUTPUT_NON_THINKING_PRICE
                
    elif "gemini-2.5-pro" in model_lower:
        # Gemini 2.5 Pro料金（ティア制）
        if input_tokens <= TOKEN_THRESHOLD_200K:
            input_cost = (input_tokens / 1_000_000) * GEMINI_25_PRO_INPUT_PRICE_TIER1
        else:
            input_cost = (input_tokens / 1_000_000) * GEMINI_25_PRO_INPUT_PRICE_TIER2
            
        if output_tokens > 0:
            if input_tokens <= TOKEN_THRESHOLD_200K:
                output_cost = (output_tokens / 1_000_000) * GEMINI_25_PRO_OUTPUT_PRICE_TIER1
            else:
                output_cost = (output_tokens / 1_000_000) * GEMINI_25_PRO_OUTPUT_PRICE_TIER2
                
    elif "gemini-2.0-flash" in model_lower:
        # Gemini 2.0 Flash料金
        input_cost = (input_tokens / 1_000_000) * GEMINI_20_FLASH_INPUT_PRICE
        if output_tokens > 0:
            output_cost = (output_tokens / 1_000_000) * GEMINI_20_FLASH_OUTPUT_PRICE
            
    else:
        # その他のモデル（従来の推定料金を使用）
        price_per_million = GEMINI_25_FLASH_INPUT_PRICE if input_tokens <= TOKEN_THRESHOLD_200K else GEMINI_25_PRO_INPUT_PRICE_TIER2
        input_cost = (input_tokens / 1_000_000) * price_per_million
        
        if output_tokens > 0:
            output_price = GEMINI_25_FLASH_OUTPUT_NON_THINKING_PRICE if output_tokens <= TOKEN_THRESHOLD_200K else GEMINI_25_PRO_OUTPUT_PRICE_TIER2
            output_cost = (output_tokens / 1_000_000) * output_price

    total_cost = input_cost + output_cost
    return input_cost, output_cost, total_cost

def setup_gen_ai_env():
    """Set up environment variables for Google Gen AI SDK with Vertex AI"""
    if not os.getenv('GOOGLE_GENAI_USE_VERTEXAI'):
        os.environ['GOOGLE_GENAI_USE_VERTEXAI'] = 'True'
    # プロジェクトIDと場所は既にVertex AIの初期化で設定されているはず

def calculate_cost(input_tokens: int | None, output_tokens: int | None) -> tuple[float | None, float | None, float | None]:
    """
    Calculates the estimated input, output, and total costs based on token counts.

    Returns:
        A tuple containing (input_cost, output_cost, total_cost).
        Costs are None if input_tokens is None. output_cost is 0 if output_tokens is None.
    """
    if input_tokens is None:
        # If input tokens are unknown, we can't calculate any cost reliably.
        return None, None, None

    input_cost = 0.0
    if input_tokens > 0:
        price_per_million = GEMINI_25_FLASH_INPUT_PRICE if input_tokens <= TOKEN_THRESHOLD_200K else GEMINI_25_PRO_INPUT_PRICE_TIER2
        input_cost = (input_tokens / 1_000_000) * price_per_million

    output_cost = 0.0
    if output_tokens is not None and output_tokens > 0:
        # Assuming the same threshold applies to output tokens
        price_per_million = GEMINI_25_FLASH_OUTPUT_NON_THINKING_PRICE if output_tokens <= TOKEN_THRESHOLD_200K else GEMINI_25_PRO_OUTPUT_PRICE_TIER2
        output_cost = (output_tokens / 1_000_000) * price_per_million
    # If output_tokens is None but input_tokens is known, output_cost remains 0.

    total_cost = input_cost + output_cost
    # Return individual costs and the total
    return input_cost, output_cost, total_cost

# --- API Client Function ---
def generate_gemini_response(
    model_name: str,
    system_instruction: Content | None,
    contents: list[Content],
    generation_config: dict,  # 簡素化
    safety_settings: dict,
    stream_update_callback,
    thinking_budget: int = 0,  # 0 = 思考無効、それ以外 = 思考有効（バジェット）
    thinking_auto_budget: bool = False,  # 自動バジェット設定
    ):
    """
    Sends request to Vertex AI Gemini model using Google Gen AI SDK and streams the response.

    Args:
        model_name: The name of the Gemini model to use.
        system_instruction: Optional system instruction content.
        contents: The conversation history and current user prompt.
        generation_config: Configuration for generation (temp, tokens, etc.).
        safety_settings: Safety settings dictionary (for compatibility, but Gen AI SDK handles this differently).
        stream_update_callback: A function to call with each received text chunk.
        thinking_budget: Token budget for thinking (0 to disable thinking).
        thinking_auto_budget: Whether to use automatic thinking budget optimization.

    Returns:
        A tuple containing:
        - The full accumulated response text (str).
        - The final model Content object (or None if error).
        - Any error message encountered (str or None).
        - Input token count (int or None).
        - Output token count (int or None).
        - Estimated input cost (float or None).
        - Estimated output cost (float or None).
        - Estimated total cost (float or None).
        - Thinking text (str or None).
    """
    full_response_text = ""
    full_thinking_text = ""
    final_model_content = None
    error_message = None
    input_token_count = None
    output_token_count = None
    input_cost = None
    output_cost = None
    total_cost = None
    last_update_time = time.time()
    update_interval = 0.05

    try:
        # 環境変数設定
        setup_gen_ai_env()
        
        # Gen AI クライアント初期化 - プロジェクトIDと場所を明示的に設定
        try:
            # configから設定を取得
            from config_manager import get_config
            config = get_config()
            project_id = config.get("vertex_ai_project_id")
            location = config.get("vertex_ai_location")
            
            if not project_id or project_id == "YOUR_PROJECT_ID":
                raise ValueError("Project ID not properly configured in config.json")
            if not location or location == "YOUR_LOCATION":
                raise ValueError("Location not properly configured in config.json")
                
            # Vertex AI環境での認証設定
            client = genai.Client(
                http_options=HttpOptions(api_version="v1"),
                vertexai=True,
                project=project_id,
                location=location
            )
            
            logging.info(f"Initialized Gen AI client for project: {project_id}, location: {location}")
            
        except Exception as client_init_err:
            logging.error(f"Failed to initialize Gen AI client: {client_init_err}")
            raise ValueError(f"Gen AI client initialization failed: {client_init_err}")

        logging.info(f"Sending request to model: {model_name}")

        # --- Log Input Content ---
        try:
            input_summary_log = f"Input Summary (model: {model_name}): "
            if system_instruction:
                input_summary_log += f"System Prompt (len: {len(system_instruction.parts[0].text)}), "
            input_summary_log += f"History+Prompt ({len(contents)} items), "
            current_prompt_len = len(contents[-1].parts[0].text) if contents and contents[-1].role == "user" else 0
            input_summary_log += f"Current Prompt (len: {current_prompt_len})"
            logging.info(input_summary_log)
        except Exception as log_summary_err:
            logging.warning(f"Could not format input summary for logging: {log_summary_err}")

        # Gen AI SDK用のコンテンツ変換
        gen_ai_contents = []
        for content in contents:
            if content.role == "system":
                continue  # system instructionは別途処理
            
            # partsからテキストを抽出
            text_parts = []
            for part in content.parts:
                if hasattr(part, 'text'):
                    text_parts.append(part.text)
            
            combined_text = "\n".join(text_parts)
            gen_ai_contents.append({
                "role": content.role,
                "parts": [{"text": combined_text}]
            })

        # System instructionを含める場合
        prompt_with_system = ""
        if system_instruction and system_instruction.parts:
            prompt_with_system = f"[SYSTEM INSTRUCTION]: {system_instruction.parts[0].text}\n\n"
        
        # 最新のユーザープロンプトに追加
        if gen_ai_contents and gen_ai_contents[-1]["role"] == "user":
            gen_ai_contents[-1]["parts"][0]["text"] = prompt_with_system + gen_ai_contents[-1]["parts"][0]["text"]

        # Generate content configの設定
        config_kwargs = {}
        
        # Thinking設定 - budgetのみで制御
        thinking_enabled = thinking_budget > 0
        has_thinking = thinking_enabled
        if thinking_enabled:
            thinking_config = {"include_thoughts": True}
            
            # 自動バジェット設定
            if thinking_auto_budget:
                # Gemini 2.5では自動最適化を使用（バジェット指定なし）
                logging.info("Using automatic thinking budget optimization")
            else:
                # 手動バジェット設定（Flash以外のモデルでは無視される場合があります）
                if "flash" in model_name.lower():
                    thinking_config["thinking_budget"] = thinking_budget
                logging.info(f"Thinking enabled with budget: {thinking_budget}")
            
            config_kwargs["thinking_config"] = ThinkingConfig(**thinking_config)
        else:
            logging.info("Thinking disabled (budget = 0)")
        
        # Generation config
        if generation_config:
            config_kwargs.update(generation_config)

        generation_config_obj = GenerateContentConfig(**config_kwargs) if config_kwargs else None

        # ストリーミング生成
        if generation_config_obj:
            response_stream = client.models.generate_content_stream(
                model=model_name,
                contents=gen_ai_contents,
                config=generation_config_obj
            )
        else:
            response_stream = client.models.generate_content_stream(
                model=model_name,
                contents=gen_ai_contents
            )

        # ストリーミング処理 - キャンセル対応付き
        for chunk in response_stream:
            try:
                # 通常のテキスト応答の処理
                if hasattr(chunk, 'text') and chunk.text:
                    chunk_text = chunk.text
                    full_response_text += chunk_text
                    
                    # コールバックを呼び出し、キャンセルがリクエストされていればFalseが返される
                    continue_streaming = stream_update_callback(full_response_text)
                    if continue_streaming is False:
                        logging.info("Stream cancelled by user request")
                        error_message = "キャンセルされました"
                        break
                        
                elif hasattr(chunk, 'candidates') and chunk.candidates:
                    # 代替的な応答テキスト取得方法
                    for candidate in chunk.candidates:
                        if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                            for part in candidate.content.parts:
                                if hasattr(part, 'text') and part.text:
                                    chunk_text = part.text
                                    full_response_text += chunk_text
                                    
                                    # キャンセルチェック
                                    continue_streaming = stream_update_callback(full_response_text)
                                    if continue_streaming is False:
                                        logging.info("Stream cancelled by user request")
                                        error_message = "キャンセルされました"
                                        break
                        if error_message:  # 内側のループから抜けた場合、外側のループも抜ける
                            break
                    if error_message:
                        break

            except Exception as chunk_proc_err:
                logging.error(f"Error processing stream chunk: {chunk_proc_err}", exc_info=True)

        # 思考テキストの抽出 - 最終レスポンスから
        if thinking_enabled and full_response_text:
            # <thinking>...</thinking>タグがあるかチェック
            import re
            thinking_pattern = re.compile(r"<thinking>(.*?)</thinking>", re.DOTALL | re.IGNORECASE)
            thinking_matches = thinking_pattern.findall(full_response_text)
            if thinking_matches:
                full_thinking_text = "\n---\n".join(thinking_matches)
                # 思考部分を除去してメインテキストを取得
                full_response_text = thinking_pattern.sub("", full_response_text).strip()
                logging.info(f"Extracted thinking text: {len(full_thinking_text)} chars")

        logging.debug(f"Stream finished. Response length: {len(full_response_text)}, Thinking length: {len(full_thinking_text)}")

        # 最終コンテンツオブジェクト構築
        try:
            final_model_content = Content(parts=[Part.from_text(full_response_text)], role="model")
        except Exception as final_content_err:
            logging.error(f"Could not construct final model Content: {final_content_err}")
            final_model_content = Content(parts=[Part.from_text("Error constructing final content.")], role="model")

    except Exception as api_err:
        error_message = f"Error during API call/streaming: {api_err}"
        logging.error(error_message, exc_info=True)

    # ログ出力
    if error_message:
        logging.info(f"Output: API Error - {error_message}")
    elif full_response_text:
        logging.info(f"Output: Success - Response length: {len(full_response_text)}")
        if full_thinking_text:
            logging.info(f"Thinking: Success - Thinking length: {len(full_thinking_text)}")
        # 応答テキストの詳細はDEBUGレベルでより少なく
        if logging.getLogger().isEnabledFor(logging.DEBUG):
            logging.debug(f"Response preview: {full_response_text[:100]}{'...' if len(full_response_text) > 100 else ''}")
    else:
        logging.info("Output: Empty response received.")

    # トークン数の推定（Gen AI SDKはまだ詳細なメタデータを提供しない場合があります）
    if full_response_text:
        input_token_count, output_token_count = get_accurate_token_count(client, model_name, contents, system_instruction)
        logging.info(f"Token Count (estimated): Input={input_token_count}, Output={output_token_count}")

    # コスト計算
    input_cost, output_cost, total_cost = calculate_cost_accurate(
        model_name, 
        input_token_count or 0, 
        output_token_count or 0, 
        has_thinking and bool(full_thinking_text)
    )

    if total_cost is not None:
        log_cost_detail = f"Input: ${input_cost:.6f} ({input_token_count} tokens), Output: ${output_cost:.6f} ({output_token_count} tokens - estimated)"
        logging.info(f"Estimated Total Cost: ${total_cost:.6f} ({log_cost_detail})")
    else:
        logging.warning("Could not calculate estimated cost (input tokens unavailable).")

    # Return calculated/estimated tokens, costs, and thinking text
    return full_response_text, final_model_content, error_message, input_token_count, output_token_count, input_cost, output_cost, total_cost, full_thinking_text
