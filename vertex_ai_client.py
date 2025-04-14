import logging
import time
from vertexai.generative_models import GenerativeModel, Part, FinishReason, GenerationConfig, Content
# Import safety settings and initialization status from main module (or state manager later)
# For now, assume safety_settings are defined/imported where this function is called
# and vertex_ai_initialized is checked before calling.

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
    """
    full_response_text = ""
    final_model_content = None
    error_message = None
    last_update_time = time.time()
    update_interval = 0.05 # Throttle UI updates

    try:
        gemini_model = GenerativeModel(
            model_name,
            safety_settings=safety_settings,
            system_instruction=system_instruction
        )
        logging.info(f"Streaming request to model: {model_name}")
        stream_response = gemini_model.generate_content(
            contents=contents,
            generation_config=generation_config,
            stream=True,
            tools=None,
        )

        for chunk in stream_response:
            try:
                chunk_text = chunk.text
                logging.debug(f"Stream chunk received: '{chunk_text}'")
                full_response_text += chunk_text
                # Call the callback to update UI
                stream_update_callback(full_response_text)

                # Callback should handle throttling/page update
                # current_time = time.time()
                # if current_time - last_update_time >= update_interval:
                #     last_update_time = current_time

            except AttributeError:
                logging.warning(f"Chunk structure issue (no text): {chunk}")
            except Exception as chunk_proc_err:
                 logging.error(f"Error processing stream chunk: {chunk_proc_err}", exc_info=True)

        logging.debug(f"Stream finished. Full raw: {full_response_text}")

        # Construct final content object from accumulated text
        try:
             final_model_content = Content(parts=[Part.from_text(full_response_text)], role="model")
        except Exception as final_content_err:
             logging.error(f"Could not construct final model Content: {final_content_err}")
             final_model_content = Content(parts=[Part.from_text("Error constructing final content.")]) # Fallback


    except Exception as api_err:
        error_message = f"Error during API call/streaming: {api_err}"
        logging.error(error_message, exc_info=True)

    return full_response_text, final_model_content, error_message
