import logging
import time
import os
from google import genai
from google.genai.types import GenerateContentConfig, ThinkingConfig, HttpOptions, Tool, GoogleSearch
from config_manager import get_config
from google.oauth2 import service_account

# リトライ設定
MAX_RETRIES = 3  # 最大リトライ回数
INITIAL_RETRY_DELAY = 1.0  # 初回リトライ待機時間（秒）
MAX_RETRY_DELAY = 10.0  # 最大リトライ待機時間（秒）

def is_retryable_error(error: Exception) -> bool:
    """リトライ可能なエラーかどうかを判定"""
    error_str = str(error).lower()
    error_type = type(error).__name__
    
    # HTTPエラーコードのチェック
    retryable_codes = ['443', '429', '503', '500', '502', '504']
    for code in retryable_codes:
        if code in error_str:
            return True
    
    # ネットワークエラーのチェック
    network_errors = ['timeout', 'connection', 'network', 'unavailable', 'refused', 'reset']
    for err_keyword in network_errors:
        if err_keyword in error_str.lower():
            return True
    
    # 特定の例外タイプのチェック
    retryable_exceptions = ['TimeoutError', 'ConnectionError', 'OSError', 'HTTPError']
    if error_type in retryable_exceptions:
        return True
    
    return False

class Part:
    """メッセージの一部を表すクラス"""
    def __init__(self, text: str = ""):
        self.text = text
    
    @classmethod
    def from_text(cls, text: str):
        """テキストからPartオブジェクトを作成"""
        return cls(text)

class Content:
    """会話コンテンツを表すクラス"""
    def __init__(self, parts: list[Part], role: str):
        self.parts = parts
        self.role = role

# --- Cost Calculation ---

def get_model_pricing(model_name: str) -> dict:
    """Configからモデルの価格設定を取得する"""
    config = get_config()
    pricing_config = config.get("model_pricing", {})
    
    if not pricing_config:
        # フォールバック用のデフォルト設定
        return {"input": 0.0, "output": 0.0}
    
    # 1. 完全一致
    if model_name in pricing_config:
        return pricing_config[model_name]
        
    # 2. 部分一致 (長いキーを優先)
    model_lower = model_name.lower()
    sorted_keys = sorted(pricing_config.keys(), key=len, reverse=True)
    
    for key in sorted_keys:
        if key == "default": continue
        if key in model_lower:
            return pricing_config[key]
            
    # 3. デフォルト
    return pricing_config.get("default", {"input": 0.0, "output": 0.0})

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

def calculate_cost_accurate(model_name: str, input_tokens: int, output_tokens: int, has_thinking: bool = False, cached_tokens: int = 0, use_google_search: bool = False) -> tuple[float, float, float]:
    """
    正確な料金体系に基づいてコストを計算する
    
    Args:
        model_name: モデル名
        input_tokens: 入力トークン数
        output_tokens: 出力トークン数  
        has_thinking: 思考トークンが含まれているか
        cached_tokens: キャッシュされたトークン数（通常のInputトークンの約1/10の価格）
        use_google_search: Google Search Toolを使用しているか
        
    Returns:
        tuple[input_cost, output_cost, total_cost]
    """
    if input_tokens is None or input_tokens <= 0:
        return 0.0, 0.0, 0.0
    
    input_cost = 0.0
    output_cost = 0.0
    
    # 価格設定を取得
    pricing = get_model_pricing(model_name)
    
    # キャッシュトークン数を考慮
    cached_tokens = max(0, cached_tokens) if cached_tokens else 0
    non_cached_input_tokens = max(0, input_tokens - cached_tokens)
    
    # 入力価格の決定 (Tier対応)
    input_price = 0.0
    cached_price = 0.0
    
    if "tier1" in pricing:
        tier1 = pricing["tier1"]
        tier2 = pricing["tier2"]
        limit = tier1.get("limit", 200000)
        
        if input_tokens <= limit:
            input_price = tier1["input"]
            cached_price = tier1.get("cached_input", tier1["input"] * 0.1) # Default to 10% if not set
        else:
            input_price = tier2["input"]
            cached_price = tier2.get("cached_input", tier2["input"] * 0.1) # Default to 10% if not set
    else:
        input_price = pricing.get("input", 0.0)
        cached_price = pricing.get("cached_input", input_price * 0.1) # Default to 10% if not set
    
    # 入力コスト計算
    non_cached_cost = (non_cached_input_tokens / 1_000_000) * input_price
    cached_cost = (cached_tokens / 1_000_000) * cached_price
    input_cost = non_cached_cost + cached_cost
    
    # 出力コスト計算
    if output_tokens > 0:
        output_price = 0.0
        
        # Thinking価格のチェック
        if has_thinking and "output_thinking" in pricing:
            output_price = pricing["output_thinking"]
        elif "tier1" in pricing:
            # Tier制の場合 (Inputトークン数に基づく)
            tier1 = pricing["tier1"]
            tier2 = pricing["tier2"]
            limit = tier1.get("limit", 200000)
            
            if input_tokens <= limit:
                output_price = tier1["output"]
            else:
                output_price = tier2["output"]
        else:
            output_price = pricing.get("output", 0.0)
            
        output_cost = (output_tokens / 1_000_000) * output_price

    # Google Search Toolの追加料金を計算
    google_search_cost = 0.0
    if use_google_search:
        # Google Search Toolの料金設定を取得
        config = get_config()
        google_search_pricing = config.get("google_search_pricing", {})
        # デフォルト値: 1,000リクエストごとに$35 → 1リクエストあたり$0.035
        # 無料枠（1日あたり1,500リクエスト）の考慮は実装が複雑なため、ここでは全リクエストに課金
        # 実際の使用量に応じて調整が必要な場合は、別途実装が必要
        cost_per_request = google_search_pricing.get("cost_per_request", 0.035)  # $0.035 per request
        google_search_cost = cost_per_request
        logging.info(f"Google Search Tool cost: ${google_search_cost:.6f} per request")

    total_cost = input_cost + output_cost + google_search_cost
    return input_cost, output_cost, total_cost

def setup_gen_ai_env():
    """Set up environment variables for Google Gen AI SDK with Vertex AI"""
    if not os.getenv('GOOGLE_GENAI_USE_VERTEXAI'):
        os.environ['GOOGLE_GENAI_USE_VERTEXAI'] = 'True'
    # プロジェクトIDと場所は既にVertex AIの初期化で設定されているはず

def get_credentials():
    """
    Google Cloud認証情報を取得する
    
    優先順位:
    1. 環境変数 GOOGLE_APPLICATION_CREDENTIALS が設定されている場合
    2. config.json の service_account_key_path が設定されている場合
    3. Application Default Credentials (ADC) を使用（デフォルト）
    
    Returns:
        credentials: Google認証情報オブジェクト、またはNone（ADCを使用する場合）
    """
    # 1. 環境変数をチェック
    env_credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    if env_credentials_path and os.path.exists(env_credentials_path):
        logging.info(f"Using credentials from environment variable: {env_credentials_path}")
        try:
            credentials, _ = load_credentials_from_file(env_credentials_path)
            return credentials
        except Exception as e:
            logging.warning(f"Failed to load credentials from environment variable: {e}")
    
    # 2. config.jsonからサービスアカウントキーパスを取得
    try:
        config = get_config()
        service_account_path = config.get("service_account_key_path")
        if service_account_path and os.path.exists(service_account_path):
            logging.info(f"Using credentials from config.json: {service_account_path}")
            try:
                credentials = service_account.Credentials.from_service_account_file(
                    service_account_path
                )
                return credentials
            except Exception as e:
                logging.warning(f"Failed to load credentials from config.json: {e}")
    except Exception as e:
        logging.warning(f"Error reading config for credentials: {e}")
    
    # 3. Application Default Credentials (ADC) を使用
    logging.info("Using Application Default Credentials (ADC)")
    return None

def calculate_cost(input_tokens: int | None, output_tokens: int | None) -> tuple[float | None, float | None, float | None]:
    """
    Calculates the estimated input, output, and total costs based on token counts.
    NOTE: This function uses default pricing. Use calculate_cost_accurate with model_name for better accuracy.

    Returns:
        A tuple containing (input_cost, output_cost, total_cost).
    """
    if input_tokens is None:
        return None, None, None

    # デフォルト価格設定を使用
    config = get_config()
    pricing = config.get("model_pricing", {}).get("default", {"input": 0.0, "output": 0.0})
    input_price = pricing.get("input", 0.0)
    output_price = pricing.get("output", 0.0)

    input_cost = 0.0
    if input_tokens > 0:
        input_cost = (input_tokens / 1_000_000) * input_price

    output_cost = 0.0
    if output_tokens is not None and output_tokens > 0:
        output_cost = (output_tokens / 1_000_000) * output_price

    total_cost = input_cost + output_cost
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
    thinking_level_high: bool = True,  # Gemini 3.0 Pro用: True=HIGH, False=LOW
    use_google_search: bool = False,  # Google Search Toolを使用するか
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
        thinking_budget: Token budget for thinking (0 to disable thinking). Not used for Gemini 3.0 Pro.
        thinking_auto_budget: Whether to use automatic thinking budget optimization. Not used for Gemini 3.0 Pro.
        thinking_level_high: For Gemini 3.0 Pro only: True for HIGH level, False for LOW level.
        use_google_search: Whether to enable Google Search Tool for grounding.

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
        - Grounding sources (list of dict with 'uri' and optional 'title').
    """
    full_response_text = ""
    full_thinking_text = ""
    final_model_content = None
    error_message = None
    input_token_count = None
    output_token_count = None
    cached_token_count = 0  # キャッシュされたトークン数
    input_cost = None
    output_cost = None
    total_cost = None
    last_update_time = time.time()
    update_interval = 0.05
    grounding_sources = []  # グラウンディングソース情報

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
            
            # 認証情報を取得
            credentials = get_credentials()
            
            # Vertex AI環境での認証設定
            client_kwargs = {
                "http_options": HttpOptions(api_version="v1"),
                "vertexai": True,
                "project": project_id,
                "location": location
            }
            
            # 認証情報が取得できた場合は明示的に設定
            if credentials:
                client_kwargs["credentials"] = credentials
                logging.info("Using explicit credentials for authentication")
            else:
                logging.info("Using Application Default Credentials (ADC) for authentication")
            
            client = genai.Client(**client_kwargs)
            
            logging.info(f"Initialized Gen AI client for project: {project_id}, location: {location}")
            
        except Exception as client_init_err:
            error_str = str(client_init_err)
            # Application Default Credentials エラーの場合、詳細な案内を表示
            if "DefaultCredentialsError" in str(type(client_init_err).__name__) or "default credentials" in error_str.lower():
                helpful_msg = (
                    f"認証エラー: Application Default Credentials (ADC) が設定されていません。\n"
                    f"以下のコマンドを実行して認証を設定してください:\n"
                    f"  gcloud auth application-default login\n\n"
                    f"WSL環境の場合:\n"
                    f"  1. 上記コマンドを実行すると認証URLが表示されます\n"
                    f"  2. Windows側のブラウザでそのURLを開いてください\n"
                    f"  3. 表示された認証コードをターミナルに入力してください\n\n"
                    f"元のエラー: {error_str}"
                )
                logging.error(helpful_msg)
                raise ValueError(helpful_msg)
            else:
                logging.error(f"Failed to initialize Gen AI client: {client_init_err}")
                raise ValueError(f"Gen AI client initialization failed: {client_init_err}")

        logging.info(f"Sending request to model: {model_name}")

        # --- 事前に入力トークンを計算 ---
        input_token_count, _ = get_accurate_token_count(client, model_name, contents, system_instruction)
        logging.info(f"Pre-calculated input tokens: {input_token_count}")

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
        
        # Thinking設定 - モデル別に対応
        model_lower = model_name.lower()
        is_gemini_3_pro = "3-pro" in model_lower or "gemini-3-pro" in model_lower
        
        if is_gemini_3_pro:
            # Gemini 3.0 Pro: thinking_levelを使用（文字列リテラル）
            # 注意: 現在のSDKではThinkingConfigにthinking_levelパラメータが存在しないため、
            # ThinkingConfigを作成してからmodel_dump()で辞書化し、thinking_levelを追加
            thinking_enabled = thinking_budget != 0  # 0以外で有効
            if thinking_enabled:
                thinking_level_value = "high" if thinking_level_high else "low"
                # ThinkingConfigを作成（includeThoughts=Trueで有効化）
                thinking_config_obj = ThinkingConfig(includeThoughts=True)
                # model_dump()で辞書化し、thinking_levelを追加
                thinking_config_dict = thinking_config_obj.model_dump()
                thinking_config_dict["thinking_level"] = thinking_level_value
                # 辞書をThinkingConfigとして再構築（thinking_levelは無視されるが、後で追加される）
                # 実際のAPIリクエストでは辞書が使用されるため、thinking_levelが含まれる
                config_kwargs["thinking_config"] = thinking_config_dict
                logging.info(f"Thinking enabled for {model_name} with level: {thinking_level_value}")
            else:
                logging.info(f"Thinking disabled for {model_name} (budget = 0)")
            has_thinking = thinking_enabled
        else:
            # その他のモデル: thinking_budgetを使用
            thinking_enabled = thinking_budget != 0  # 0以外で有効（-1も含む）
            has_thinking = thinking_enabled
            
            if thinking_enabled:
                thinking_config = {"include_thoughts": True}
                
                if thinking_budget == -1 or thinking_auto_budget:
                    # 自動バジェット設定（-1で自動制御）
                    logging.info(f"Using automatic thinking budget (-1) for {model_name}")
                    # thinking_budgetは設定しない（デフォルトで自動）
                elif thinking_budget > 0:
                    # 手動バジェット設定
                    thinking_config["thinking_budget"] = thinking_budget
                    logging.info(f"Thinking enabled with manual budget: {thinking_budget} for {model_name}")
                
                config_kwargs["thinking_config"] = ThinkingConfig(**thinking_config)
            else:
                logging.info("Thinking disabled (budget = 0)")
        
        # Google Search Tool設定
        if use_google_search:
            config_kwargs["tools"] = [Tool(google_search=GoogleSearch())]
            logging.info(f"Google Search Tool enabled for {model_name}")
        
        # Generation config
        if generation_config:
            config_kwargs.update(generation_config)

        # Gemini 3.0 Proの場合、thinking_levelを後で追加するため、辞書形式を保持
        thinking_level_to_add = None
        if is_gemini_3_pro and thinking_enabled:
            # thinking_configが辞書形式の場合、thinking_levelを保存
            if isinstance(config_kwargs.get("thinking_config"), dict):
                thinking_level_to_add = config_kwargs["thinking_config"].get("thinking_level")
                # thinking_configからthinking_levelを一時的に削除（GenerateContentConfig作成のため）
                thinking_config_dict = config_kwargs["thinking_config"].copy()
                thinking_config_dict.pop("thinking_level", None)
                # ThinkingConfigオブジェクトを作成
                config_kwargs["thinking_config"] = ThinkingConfig(**thinking_config_dict)

        generation_config_obj = GenerateContentConfig(**config_kwargs) if config_kwargs else None
        
        # Gemini 3.0 Proの場合、thinking_levelを追加
        # 注意: SDKの制限により、thinking_levelはGenerateContentConfigのスキーマに含まれない
        # そのため、model_dump()で辞書を取得し、thinking_levelを追加してからmodel_constructで再構築
        # model_constructは検証をスキップするため、thinking_levelが含まれたままになる
        if is_gemini_3_pro and thinking_level_to_add and generation_config_obj:
            # model_dump()で辞書を取得し、thinking_levelを追加
            config_dict = generation_config_obj.model_dump()
            if "thinking_config" in config_dict and isinstance(config_dict["thinking_config"], dict):
                # thinking_levelを辞書に追加
                config_dict["thinking_config"]["thinking_level"] = thinking_level_to_add
                # model_constructを使用して再構築（検証をスキップ）
                # thinking_configは辞書形式のまま（SDKが内部的に辞書に変換する際にthinking_levelが含まれる）
                generation_config_obj = GenerateContentConfig.model_construct(**config_dict)
                logging.info(f"Added thinking_level={thinking_level_to_add} to config using model_construct")

        # リトライループでストリーミング生成を実行
        thinking_token_count = 0
        retry_count = 0
        last_error = None
        
        while retry_count <= MAX_RETRIES:
            try:
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

                # 実際のストリーミング処理
                logging.info(f"Starting real-time streaming... (attempt {retry_count + 1}/{MAX_RETRIES + 1})")
                
                # リアルタイムストリーミング処理
                stream_completed = False
                last_chunk = None  # 最後のチャンクを保存（グラウンディングメタデータ用）
                for chunk in response_stream:
                    try:
                        last_chunk = chunk  # 最後のチャンクを保存
                        
                        # チャンクからテキストを抽出
                        chunk_text = ""
                        if hasattr(chunk, 'text') and chunk.text:
                            chunk_text = chunk.text
                            logging.info(f"Streaming chunk: {len(chunk_text)} chars, total: {len(full_response_text)} chars")
                        
                        if chunk_text:
                            full_response_text += chunk_text
                            
                            # リアルタイムでコールバックを呼び出し
                            continue_streaming = stream_update_callback(full_response_text)
                            if continue_streaming is False:
                                logging.info("Stream cancelled by user request")
                                error_message = "キャンセルされました"
                                break
                        
                        # 使用統計の取得を試行
                        if hasattr(chunk, 'usage_metadata'):
                            if hasattr(chunk.usage_metadata, 'thoughts_token_count'):
                                thinking_token_count = chunk.usage_metadata.thoughts_token_count
                                logging.info(f"Thinking tokens used: {thinking_token_count}")
                            # キャッシュされたトークン数を取得
                            if hasattr(chunk.usage_metadata, 'cached_content_token_count'):
                                cached_token_count = chunk.usage_metadata.cached_content_token_count
                                logging.info(f"Cached tokens: {cached_token_count}")
                            elif hasattr(chunk.usage_metadata, 'cached_tokens'):
                                cached_token_count = chunk.usage_metadata.cached_tokens
                                logging.info(f"Cached tokens: {cached_token_count}")
                        
                        # グラウンディングメタデータの取得を試行
                        if use_google_search and hasattr(chunk, 'candidates') and chunk.candidates:
                            try:
                                for candidate in chunk.candidates:
                                    if hasattr(candidate, 'grounding_metadata'):
                                        grounding_metadata = candidate.grounding_metadata
                                        if hasattr(grounding_metadata, 'grounding_chunks'):
                                            for gc in grounding_metadata.grounding_chunks:
                                                if hasattr(gc, 'web') and hasattr(gc.web, 'uri'):
                                                    source_info = {'uri': gc.web.uri}
                                                    if hasattr(gc.web, 'title') and gc.web.title:
                                                        source_info['title'] = gc.web.title
                                                    # 重複を避ける
                                                    if source_info not in grounding_sources:
                                                        grounding_sources.append(source_info)
                                                        logging.info(f"Found grounding source: {source_info.get('uri', 'N/A')}")
                            except Exception as grounding_err:
                                logging.warning(f"Error extracting grounding metadata: {grounding_err}")
                        
                    except Exception as chunk_proc_err:
                        logging.error(f"Error processing stream chunk: {chunk_proc_err}", exc_info=True)
                        continue
                
                # ストリーミング完了後、最後のチャンクからもグラウンディングメタデータを取得
                if use_google_search and last_chunk and not grounding_sources:
                    try:
                        if hasattr(last_chunk, 'candidates') and last_chunk.candidates:
                            for candidate in last_chunk.candidates:
                                if hasattr(candidate, 'grounding_metadata'):
                                    grounding_metadata = candidate.grounding_metadata
                                    if hasattr(grounding_metadata, 'grounding_chunks'):
                                        for gc in grounding_metadata.grounding_chunks:
                                            if hasattr(gc, 'web') and hasattr(gc.web, 'uri'):
                                                source_info = {'uri': gc.web.uri}
                                                if hasattr(gc.web, 'title') and gc.web.title:
                                                    source_info['title'] = gc.web.title
                                                if source_info not in grounding_sources:
                                                    grounding_sources.append(source_info)
                                                    logging.info(f"Found grounding source from last chunk: {source_info.get('uri', 'N/A')}")
                    except Exception as last_chunk_err:
                        logging.warning(f"Error extracting grounding metadata from last chunk: {last_chunk_err}")
                
                # キャンセルされた場合はループを抜ける
                if error_message == "キャンセルされました":
                    break
                
                # ストリーミングが正常に完了した場合はループを抜ける
                stream_completed = True
                break
                
            except Exception as stream_err:
                last_error = stream_err
                error_str = str(stream_err)
                
                # キャンセルされた場合はリトライしない
                if "キャンセル" in error_str or "cancel" in error_str.lower():
                    error_message = "キャンセルされました"
                    break
                
                # リトライ可能なエラーかチェック
                if is_retryable_error(stream_err) and retry_count < MAX_RETRIES:
                    retry_count += 1
                    # 指数バックオフで待機時間を計算
                    delay = min(INITIAL_RETRY_DELAY * (2 ** (retry_count - 1)), MAX_RETRY_DELAY)
                    logging.warning(f"Retryable error occurred (attempt {retry_count}/{MAX_RETRIES}): {error_str}")
                    logging.info(f"Retrying in {delay:.1f} seconds...")
                    
                    # リトライ前に少し待機（キャンセルチェックも行う）
                    for _ in range(int(delay * 10)):  # 0.1秒ごとにチェック
                        time.sleep(0.1)
                        # キャンセルチェック（stream_update_callbackがFalseを返すかチェック）
                        # 注: この時点ではコールバックが利用できないため、スキップ
                    
                    # リトライ可能なエラーの場合、エラーメッセージをクリア
                    error_message = None
                    continue
                else:
                    # リトライ不可能なエラー、または最大リトライ回数に達した場合
                    logging.error(f"Error during streaming (non-retryable or max retries reached): {stream_err}", exc_info=True)
                    
                    # Application Default Credentials エラーの場合、詳細な案内を表示
                    if "DefaultCredentialsError" in str(type(stream_err).__name__) or "default credentials" in error_str.lower():
                        helpful_msg = (
                            f"認証エラー: Application Default Credentials (ADC) が設定されていません。\n"
                            f"以下のコマンドを実行して認証を設定してください:\n"
                            f"  gcloud auth application-default login\n\n"
                            f"WSL環境の場合:\n"
                            f"  1. 上記コマンドを実行すると認証URLが表示されます\n"
                            f"  2. Windows側のブラウザでそのURLを開いてください\n"
                            f"  3. 表示された認証コードをターミナルに入力してください\n\n"
                            f"元のエラー: {error_str}"
                        )
                        error_message = helpful_msg
                    else:
                        error_message = f"Streaming error: {stream_err}"
                        if retry_count >= MAX_RETRIES:
                            error_message += f" (リトライ {MAX_RETRIES}回試行しましたが失敗しました)"
                    break

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

        logging.info(f"Stream finished. Response length: {len(full_response_text)}, Thinking length: {len(full_thinking_text)}")

        # 出力トークン数を推定（ストリーミングでは正確な値は取得困難）
        if full_response_text:
            # 簡単な推定：4文字=1トークン
            estimated_output_tokens = len(full_response_text) // 4
            
            # 思考トークンも含める
            if full_thinking_text:
                estimated_thinking_tokens = len(full_thinking_text) // 4
                estimated_output_tokens += estimated_thinking_tokens
            
            output_token_count = estimated_output_tokens
            logging.info(f"Estimated output tokens: {output_token_count} (including thinking)")

        # 最終コンテンツオブジェクト構築
        try:
            final_model_content = Content(parts=[Part.from_text(full_response_text)], role="model")
        except Exception as final_content_err:
            logging.error(f"Could not construct final model Content: {final_content_err}")
            final_model_content = Content(parts=[Part.from_text("Error constructing final content.")], role="model")

    except Exception as api_err:
        error_str = str(api_err)
        # Application Default Credentials エラーの場合、詳細な案内を表示
        if "DefaultCredentialsError" in str(type(api_err).__name__) or "default credentials" in error_str.lower():
            helpful_msg = (
                f"認証エラー: Application Default Credentials (ADC) が設定されていません。\n"
                f"以下のコマンドを実行して認証を設定してください:\n"
                f"  gcloud auth application-default login\n\n"
                f"WSL環境の場合:\n"
                f"  1. 上記コマンドを実行すると認証URLが表示されます\n"
                f"  2. Windows側のブラウザでそのURLを開いてください\n"
                f"  3. 表示された認証コードをターミナルに入力してください\n\n"
                f"元のエラー: {error_str}"
            )
            error_message = helpful_msg
            logging.error(helpful_msg, exc_info=True)
        else:
            error_message = f"Error during API call/streaming: {api_err}"
            logging.error(error_message, exc_info=True)

    # ログ出力
    if error_message:
        logging.info(f"Output: API Error - {error_message}")
    elif full_response_text:
        logging.info(f"Output: Success - Response length: {len(full_response_text)}")
        if full_thinking_text:
            logging.info(f"Thinking: Success - Thinking length: {len(full_thinking_text)}")
        # 応答テキストの詳細はDEBUGレベルで表示
        if logging.getLogger().isEnabledFor(logging.DEBUG):
            logging.debug(f"Response preview: {full_response_text[:150]}{'...' if len(full_response_text) > 150 else ''}")
    else:
        logging.info("Output: Empty response received.")

    # コスト計算（キャッシュトークン数とGoogle Search Toolを考慮）
    input_cost, output_cost, total_cost = calculate_cost_accurate(
        model_name, 
        input_token_count or 0, 
        output_token_count or 0, 
        has_thinking and bool(full_thinking_text),
        cached_token_count,
        use_google_search
    )

    if total_cost is not None:
        cache_info = f" (cached: {cached_token_count})" if cached_token_count and cached_token_count > 0 else ""
        google_search_info = f", Google Search: ${total_cost - input_cost - output_cost:.6f}" if use_google_search else ""
        log_cost_detail = f"Input: ${input_cost:.6f} ({input_token_count} tokens{cache_info}), Output: ${output_cost:.6f} ({output_token_count} tokens - estimated){google_search_info}"
        logging.info(f"Estimated Total Cost: ${total_cost:.6f} ({log_cost_detail})")
    else:
        logging.warning("Could not calculate estimated cost (input tokens unavailable).")

    # Return calculated/estimated tokens, costs, thinking text, thinking token count, and grounding sources
    return full_response_text, final_model_content, error_message, input_token_count, output_token_count, input_cost, output_cost, total_cost, full_thinking_text, thinking_token_count, grounding_sources
