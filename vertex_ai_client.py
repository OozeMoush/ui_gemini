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
INPUT_PRICE_TIER1 = 1.25  # $/1M tokens for <= 200K input
INPUT_PRICE_TIER2 = 2.5   # $/1M tokens for > 200K input
OUTPUT_PRICE_TIER1 = 10.0 # $/1M tokens for <= 200K output (assumed)
OUTPUT_PRICE_TIER2 = 15.0 # $/1M tokens for > 200K output (assumed)
TOKEN_THRESHOLD = 200000  # Threshold for price change

# 環境変数設定（必要に応じて）
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
        price_per_million = INPUT_PRICE_TIER1 if input_tokens <= TOKEN_THRESHOLD else INPUT_PRICE_TIER2
        input_cost = (input_tokens / 1_000_000) * price_per_million

    output_cost = 0.0
    if output_tokens is not None and output_tokens > 0:
        # Assuming the same threshold applies to output tokens
        price_per_million = OUTPUT_PRICE_TIER1 if output_tokens <= TOKEN_THRESHOLD else OUTPUT_PRICE_TIER2
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
    thinking_enabled: bool = True,
    thinking_budget: int = 8192
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
        thinking_enabled: Whether to enable thinking mode.
        thinking_budget: Token budget for thinking (0 to disable, max 24576 for Flash).

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
    final_model_content = None
    error_message = None
    input_token_count = None
    output_token_count = None
    input_cost = None
    output_cost = None
    total_cost = None
    thinking_text = None
    last_update_time = time.time()
    update_interval = 0.05

    try:
        # 環境変数設定
        setup_gen_ai_env()
        
        # Gen AI クライアント初期化
        client = genai.Client(http_options=HttpOptions(api_version="v1"))
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
        
        # Thinking設定
        if thinking_enabled and thinking_budget > 0:
            config_kwargs["thinking_config"] = ThinkingConfig(include_thoughts=True)
            if "flash" in model_name.lower() and thinking_budget != 8192:
                # Flashモデルの場合はthinking_budgetを設定可能
                # Note: 実際のAPIでは別の方法かもしれません
                logging.info(f"Setting thinking budget for Flash model: {thinking_budget}")
        
        # Generation config
        if generation_config:
            config_kwargs.update(generation_config)

        generation_config_obj = GenerateContentConfig(**config_kwargs) if config_kwargs else None

        logging.info(f"Thinking enabled: {thinking_enabled}, Budget: {thinking_budget}")

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

        # ストリーミング処理
        for chunk in response_stream:
            try:
                if hasattr(chunk, 'text') and chunk.text:
                    chunk_text = chunk.text
                    full_response_text += chunk_text
                    # UI更新
                    stream_update_callback(full_response_text)

            except Exception as chunk_proc_err:
                logging.error(f"Error processing stream chunk: {chunk_proc_err}", exc_info=True)

        # Thinking情報を取得（非ストリーミングレスポンスから）
        if thinking_enabled and thinking_budget > 0:
            try:
                # 同じリクエストを非ストリーミングで再実行してthinking情報を取得
                full_response = client.models.generate_content(
                    model=model_name,
                    contents=gen_ai_contents,
                    config=generation_config_obj
                )
                
                # Thinking情報を抽出
                if hasattr(full_response, 'candidates') and full_response.candidates:
                    for candidate in full_response.candidates:
                        if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                            for part in candidate.content.parts:
                                if hasattr(part, 'thought') and part.thought:
                                    thinking_text = part.text
                                    logging.info("Thinking text extracted from response")
                                    break
                            if thinking_text:
                                break
                
            except Exception as thinking_err:
                logging.warning(f"Could not extract thinking information: {thinking_err}")

        logging.debug(f"Stream finished. Full response length: {len(full_response_text)}")

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
        # 応答テキストの詳細はDEBUGレベルでより少なく
        if logging.getLogger().isEnabledFor(logging.DEBUG):
            logging.debug(f"Response preview: {full_response_text[:100]}{'...' if len(full_response_text) > 100 else ''}")
    else:
        logging.info("Output: Empty response received.")

    # トークン数の推定（Gen AI SDKはまだ詳細なメタデータを提供しない場合があります）
    if full_response_text:
        estimated_input_tokens = sum(len(content["parts"][0]["text"]) for content in gen_ai_contents) // 4
        estimated_output_tokens = len(full_response_text) // 4
        input_token_count = estimated_input_tokens
        output_token_count = estimated_output_tokens
        logging.info(f"Token Count (estimated): Input={input_token_count}, Output={output_token_count}")

    # コスト計算
    input_cost, output_cost, total_cost = calculate_cost(input_token_count, output_token_count)

    if total_cost is not None:
        log_cost_detail = f"Input: ${input_cost:.6f} ({input_token_count} tokens), Output: ${output_cost:.6f} ({output_token_count} tokens - estimated)"
        logging.info(f"Estimated Total Cost: ${total_cost:.6f} ({log_cost_detail})")
    else:
        logging.warning("Could not calculate estimated cost (input tokens unavailable).")

    # Return calculated/estimated tokens, costs, and thinking text
    return full_response_text, final_model_content, error_message, input_token_count, output_token_count, input_cost, output_cost, total_cost, thinking_text
