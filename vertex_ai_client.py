import logging
import time
from vertexai.generative_models import GenerativeModel, Part, FinishReason, GenerationConfig, Content
# Import safety settings and initialization status from main module (or state manager later)
# For now, assume safety_settings are defined/imported where this function is called
# and vertex_ai_initialized is checked before calling.

# --- Cost Calculation ---
INPUT_PRICE_TIER1 = 1.25  # $/1M tokens for <= 200K input
INPUT_PRICE_TIER2 = 2.5   # $/1M tokens for > 200K input
OUTPUT_PRICE_TIER1 = 10.0 # $/1M tokens for <= 200K output (assumed)
OUTPUT_PRICE_TIER2 = 15.0 # $/1M tokens for > 200K output (assumed)
TOKEN_THRESHOLD = 200000  # Threshold for price change

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
# This function will now handle the core API interaction including streaming
def generate_gemini_response(
    model_name: str,
    system_instruction: Content | None,
    contents: list[Content],
    generation_config: GenerationConfig,
    safety_settings: dict, # Pass safety settings explicitly
    stream_update_callback # Function to call with text chunks
    ):
    """
    Sends request to Vertex AI Gemini model and streams the response.

    Args:
        model_name: The name of the Gemini model to use.
        system_instruction: Optional system instruction content.
        contents: The conversation history and current user prompt.
        generation_config: Configuration for generation (temp, tokens, etc.).
        safety_settings: Safety settings dictionary.
        stream_update_callback: A function to call with each received text chunk.

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
    """
    full_response_text = ""
    final_model_content = None
    error_message = None
    usage_metadata = None
    input_token_count = None
    output_token_count = None
    input_cost = None  # Initialize costs
    output_cost = None
    total_cost = None
    last_update_time = time.time()
    update_interval = 0.05 # Throttle UI updates

    try:
        gemini_model = GenerativeModel(
            model_name,
            safety_settings=safety_settings,
            system_instruction=system_instruction
        )
        logging.info(f"Sending request to model: {model_name}")

        # --- Log Input Content ---
        # INFO level: Log a summary
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

        # DEBUG level: Log the full input details
        if logging.getLogger().isEnabledFor(logging.DEBUG):
            try:
                full_input_log = f"--- Full Input to {model_name} ---"
                if system_instruction:
                    full_input_log += f"\n[SYSTEM]\n{system_instruction.parts[0].text}"
                full_input_log += "\n[HISTORY & PROMPT]"
                for i, content_item in enumerate(contents):
                    full_input_log += f"\n[{i}] Role: {content_item.role}"
                    for part in content_item.parts:
                         # Assuming text part for now, adjust if handling multimodal
                         full_input_log += f"\n{part.text}" # Log full text of each part
                full_input_log += "\n--- End of Full Input ---"
                logging.debug(full_input_log)
            except Exception as log_full_err:
                logging.warning(f"Could not format full input contents for DEBUG logging: {log_full_err}")

        # --- Count Input Tokens ---
        try:
            # Use the same model instance to count tokens
            count_response = gemini_model.count_tokens(contents=contents)
            input_token_count = count_response.total_tokens
            logging.info(f"Input Token Count (calculated): {input_token_count}")
        except Exception as count_err:
            logging.warning(f"Could not count input tokens: {count_err}")
            input_token_count = None # Indicate failure

        stream_response = gemini_model.generate_content(
            contents=contents,
            generation_config=generation_config,
            stream=True,
            tools=None,
        )

        for chunk in stream_response:
            try:
                # Check if chunk has text content before proceeding
                if hasattr(chunk, 'text'):
                    chunk_text = chunk.text
                    # logging.debug(f"Stream chunk received: '{chunk_text}'") # Removed for less noise
                    full_response_text += chunk_text
                    # Call the callback to update UI
                    stream_update_callback(full_response_text)
                # else: # Log if chunk structure is unexpected but maybe not critical
                #     logging.debug(f"Received stream chunk without 'text' attribute: {chunk}")

                # Callback should handle throttling/page update
                # current_time = time.time()
                # if current_time - last_update_time >= update_interval:
                #     last_update_time = current_time

                # Callback should handle throttling/page update
                # current_time = time.time()
                # if current_time - last_update_time >= update_interval:
                #     last_update_time = current_time

            except AttributeError:
                logging.warning(f"Chunk structure issue (no text): {chunk}")
            except Exception as chunk_proc_err:
                 logging.error(f"Error processing stream chunk: {chunk_proc_err}", exc_info=True)

        # After loop, try to get usage metadata from the stream response object
        try:
            # Accessing usage_metadata after the stream is consumed
            if hasattr(stream_response, 'usage_metadata'):
                 usage_metadata = stream_response.usage_metadata
                 logging.info(f"Usage Metadata: {usage_metadata}")
            else:
                 # Sometimes it might be in the last chunk, less common with streaming
                 # last_chunk = stream_response._chunks[-1] # This is hypothetical, API might differ
                 # if hasattr(last_chunk, 'usage_metadata'):
                 #    usage_metadata = last_chunk.usage_metadata
                 #    logging.info(f"Usage Metadata from last chunk: {usage_metadata}")
                 # else:
                 logging.warning("Could not find usage_metadata in stream response.")
        except Exception as usage_err:
             logging.warning(f"Error retrieving usage metadata: {usage_err}")

        # Try to get output token count from metadata if found
        if usage_metadata:
             try:
                 output_token_count = getattr(usage_metadata, 'candidates_token_count', None) # Use getattr for safety
                 if output_token_count is not None:
                     logging.info(f"Output Token Count (from metadata): {output_token_count}")
                 else:
                     logging.warning("usage_metadata found but 'candidates_token_count' attribute missing or None.")
             except Exception as meta_parse_err:
                  logging.warning(f"Error parsing candidates_token_count from usage_metadata: {meta_parse_err}")


        logging.debug(f"Stream finished. Full raw length: {len(full_response_text)}")

        # Construct final content object from accumulated text
        try:
             final_model_content = Content(parts=[Part.from_text(full_response_text)], role="model")
        except Exception as final_content_err:
             logging.error(f"Could not construct final model Content: {final_content_err}")
             final_model_content = Content(parts=[Part.from_text("Error constructing final content.")]) # Fallback


    except Exception as api_err:
        error_message = f"Error during API call/streaming: {api_err}"
        logging.error(error_message, exc_info=True)

    # Log final output at INFO level
    if error_message:
        logging.info(f"Output: API Error - {error_message}")
    elif full_response_text:
        logging.info(f"Output: Success - Response length: {len(full_response_text)}")
        logging.debug(f"Full Output Text (DEBUG): {full_response_text[:500]}{'...' if len(full_response_text) > 500 else ''}") # Log more details in DEBUG
    else:
        logging.info("Output: Empty response received.")

    # --- Estimate Output Tokens if not provided by API ---
    output_token_source = "metadata" # Track where the count came from
    if output_token_count is None and full_response_text:
        estimated_count = int(len(full_response_text) * 0.8)
        output_token_count = estimated_count # Use the estimate
        output_token_source = "estimated (x0.8 char)"
        logging.info(f"Output Token Count ({output_token_source}): {output_token_count}")

    # Calculate costs after getting token counts (actual or estimated)
    input_cost, output_cost, total_cost = calculate_cost(input_token_count, output_token_count)

    if total_cost is not None:
        log_cost_detail = f"Input: ${input_cost:.6f} ({input_token_count} tokens), Output: ${output_cost:.6f} ({output_token_count} tokens - {output_token_source})"
        logging.info(f"Estimated Total Cost: ${total_cost:.6f} ({log_cost_detail})")
    else:
        logging.warning("Could not calculate estimated cost (input tokens unavailable).")

    # Return calculated/estimated tokens and costs
    return full_response_text, final_model_content, error_message, input_token_count, output_token_count, input_cost, output_cost, total_cost
