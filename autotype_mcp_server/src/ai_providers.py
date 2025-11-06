import os
import logging
import re
import textwrap
from typing import Optional, Dict, Any, List

try:
    import requests

    REQUESTS_AVAILABLE = True
except ImportError:
    logging.warning("'requests' library not found. API features will be disabled.")
    REQUESTS_AVAILABLE = False


def extract_code(response_text: str) -> List[Dict[str, str]]:
    """Extract all fenced code blocks (```) from response text.

    Args:
        response_text (str): The raw text response from the AI model.

    Returns:
        List[Dict[str, str]]: A list of dictionaries, each representing a code block
            with keys 'language' (str, lowercase) and 'code' (str).
            Returns an empty list if no blocks are found.
    """
    extracted_blocks: List[Dict[str, str]] = []
    # Pattern: ```[lang]\n<code>\n```
    pattern = r"```(\w*)\s*\n(.*?)\s*```"
    matches = re.finditer(pattern, response_text, re.DOTALL | re.IGNORECASE)
    for match in matches:
        language = match.group(1).lower().strip()
        code = match.group(2)
        dedented_code = textwrap.dedent(code).strip()
        extracted_blocks.append({"language": language, "code": dedented_code})
        logging.debug(
            f"Extracted code block. Language: '{language if language else '[none]'}', Length: {len(dedented_code)}"
        )
    if not extracted_blocks:
        logging.debug("No fenced code blocks found in the text.")
    return extracted_blocks


def ai_generate_code(
    task_description: str,
    test_path: Optional[str],
    config: Dict[str, Any],
    model_override: Optional[str] = None,
) -> str:
    """Generate code or text using a configured API provider (e.g., Ollama via OpenAI endpoint).

    Args:
        task_description (str): The textual description of the coding task or planning prompt.
        test_path (Optional[str]): The path to an existing test file (if any, relevant for code gen).
        config (Dict[str, Any]): Configuration dictionary containing API keys, URLs, model settings.
        model_override (Optional[str]): Specific model name to use, bypassing fallback list.

    Returns:
        str: The generated code/text string (extracted from AI response), or an error message string.

    Note: Ollama does NOT require an API key. The Authorization header is only set for cloud providers.
    Preferred models for Ollama: 'phi3:mini-4k-instruct-q4_K_M', then 'phi:latest'.
    """
    if not REQUESTS_AVAILABLE:
        logging.error(
            "'requests' library is required for AI code generation but not installed."
        )
        return "# ERROR: 'requests' library not installed."

    api_key_env: str = config.get("GROK_API_KEY_ENV", "XAI_API_KEY")
    api_url_env: str = config.get("GROK_API_URL_ENV", "XAI_API_URL")
    api_key: str = os.environ.get(api_key_env, "ollama")
    api_url: Optional[str] = os.environ.get(api_url_env)

    # If no api_url is set, default to Ollama's standard local endpoint
    if not api_url:
        api_url = "http://localhost:11434"
        logging.info(
            f"API URL environment variable '{api_url_env}' not set. Defaulting to '{api_url}' for Ollama."
        )

    # Determine the model(s) to use
    models_to_try: List[str] = []
    if model_override:
        models_to_try.append(model_override)
    else:
        fallback_list = config.get("AI_MODEL_FALLBACK_LIST")
        if isinstance(fallback_list, list) and fallback_list:
            models_to_try.extend(fallback_list)
        else:
            default_models = ["phi3:mini-4k-instruct-q4_K_M", "phi:latest", "phi"]
            logging.warning(
                f"AI_MODEL_FALLBACK_LIST not found or invalid in config. "
                f"Using default models: {default_models}"
            )
            models_to_try.extend(default_models)

    if not models_to_try:
        logging.error("No valid AI models configured or defaulted.")
        return "# ERROR: No AI models configured."

    selected_model: str = models_to_try[0]

    max_retries: int = config.get("AI_MAX_RETRIES", 3)
    max_tokens: int = config.get("AI_MAX_TOKENS", 8192)
    temperature: float = config.get("AI_TEMPERATURE", 0.1)
    timeout: int = config.get("AI_TIMEOUT", 180)

    prompt: str = task_description

    # Optionally append test file context if relevant
    test_code: str = ""
    if (
        test_path
        and os.path.exists(test_path)
        and "generate the complete, corrected python code" in prompt.lower()
    ):
        try:
            with open(test_path, "r", encoding="utf-8") as tf:
                test_code = tf.read()
            if test_code:
                prompt += (
                    f"\n\nRelevant Test File ({os.path.basename(test_path)}):\n"
                    f"```python\n{test_code}\n```"
                )
            else:
                logging.warning(f"Test file {test_path} is empty.")
        except Exception as e:
            logging.error(f"Error reading test file {test_path}: {e}", exc_info=True)

    headers: Dict[str, str] = {"Content-Type": "application/json"}
    # Only set Authorization if api_key is present and not 'ollama' (Ollama does not require a key)
    if api_key and api_key.lower() != "ollama":
        headers["Authorization"] = f"Bearer {api_key}"
    else:
        logging.info(
            "Using Ollama. No API key required, skipping Authorization header."
        )

    payload: Dict[str, Any] = {
        "model": selected_model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    logging.info(f"Sending request to AI API: {api_url} (Model: {selected_model})")
    logging.debug(
        f"Payload (prompt truncated): {{'model': '{selected_model}', 'messages': [{{'role': 'user', 'content': '{prompt[:200]}...'}}], ...}}"
    )

    response_data: Optional[Dict[str, Any]] = None
    generated_content: Optional[str] = None
    error_message: Optional[str] = None
    status_code: Optional[int] = None

    # --- Try OpenAI Compatible Endpoint Only ---
    # Ensure api_base never ends with /v1, and always append exactly one /v1/chat/completions
    api_base = api_url.rstrip("/")
    if api_base.endswith("/v1"):
        api_base = api_base[:-3]
    endpoint_v1 = f"{api_base}/v1/chat/completions"
    logging.debug(f"[AI PROVIDERS] Final endpoint_v1: {endpoint_v1}")
    try:
        logging.info(f"Attempting OpenAI endpoint: {endpoint_v1}")
        response = requests.post(
            endpoint_v1, headers=headers, json=payload, timeout=timeout
        )
        status_code = response.status_code
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
        response_data = response.json()
        logging.info(f"Success with OpenAI endpoint ({status_code}).")
        # Parse OpenAI-compatible response
        if "choices" in response_data and len(response_data["choices"]) > 0:
            if "message" in response_data["choices"][0]:
                generated_content = response_data["choices"][0]["message"].get(
                    "content", ""
                )
            elif "text" in response_data["choices"][0]:
                generated_content = response_data["choices"][0]["text"]
    except Exception as e:
        status_code_from_response = getattr(
            getattr(e, "response", None), "status_code", "unknown"
        )
        error_message = (
            f"OpenAI endpoint {endpoint_v1} failed ({status_code_from_response}): {e}"
        )
        logging.error(error_message, exc_info=True)

    # --- Process Response (if successful) ---
    if response_data and not error_message:
        # If generated_content is already set (from legacy endpoint), use it
        if not generated_content:
            # Try OpenAI-style response
            if "choices" in response_data and response_data["choices"]:
                message = response_data["choices"][0].get("message", {})
                generated_content = message.get("content")
            # Try Gemini-style response (less likely for Ollama but keep for flexibility)
            elif "candidates" in response_data and response_data["candidates"]:
                candidate = response_data["candidates"][0]
                generated_content = (
                    candidate.get("content", {}).get("parts", [{}])[0].get("text")
                )

        if generated_content:
            logging.info(
                f"Successfully received response from AI model {selected_model}. Endpoint used: OpenAI v1"
            )
            extracted_blocks = extract_code(generated_content)
            if extracted_blocks:
                first_block_code = extracted_blocks[0]["code"]
                logging.info(
                    f"Extracted code length (first block): {len(first_block_code)}"
                )
                return first_block_code
            else:
                # If it was a planning prompt, maybe return the raw content?
                # Check if the prompt asked for JSON
                if "Output the plan as a JSON object" in prompt:
                    logging.info(
                        "Planning prompt detected, returning raw JSON content."
                    )
                    return generated_content.strip()
                logging.warning(
                    "AI response received, but no code blocks found after extraction."
                )
                return "# ERROR: AI response contained no recognizable code blocks."
        else:
            logging.error(
                f"AI response from {selected_model} seems empty or lacks expected content structure."
            )
            logging.debug(f"Raw AI Response Data: {response_data}")
            error_message = (
                f"AI response from {selected_model} missing expected content."
            )

    # --- Return Error Message if anything failed ---
    if error_message:
        return f"# ERROR: {error_message}. Status: {status_code if status_code else 'N/A'} (If using Ollama, no API key is required.)"
    else:
        # Should ideally not reach here if successful, but as a fallback
        logging.error(
            "Reached end of ai_generate_code without success or specific error."
        )
        return "# ERROR: Unknown error during AI processing."
