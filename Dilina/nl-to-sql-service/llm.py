import os
import sys
import platform
import time

# Prevent Python 3.12 Windows WMI query hang in platform module called by OpenAI SDK
if sys.platform == "win32":
    platform.win32_ver = lambda *args, **kwargs: ('10', '10.0.19045', 'SP0', 'Multiprocessor Free')
    platform.platform = lambda *args, **kwargs: 'Windows-10-10.0.19045-SP0'
    platform.system = lambda *args, **kwargs: 'Windows'
    platform.uname = lambda *args, **kwargs: platform.uname_result('Windows', 'PC', '10', '10.0.19045', 'AMD64')
from dotenv import load_dotenv
from google import genai
from google.genai import types
from groq import Groq
from openai import OpenAI

from profiler import time_block, log_step

# Load environment variables
load_dotenv()

PROVIDER = os.getenv("LLM_PROVIDER", "cerebras").lower().strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
CEREBRAS_MODEL = os.getenv("CEREBRAS_MODEL", "gemma-4-31b")
SAMBANOVA_MODEL = os.getenv("SAMBANOVA_MODEL", "gemma-4-31B-it")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# Lazy Client Initialization
_gemini_client = None
_groq_client = None
_cerebras_client = None
_sambanova_client = None
_openrouter_client = None
_openai_client = None

def get_client():
    global _gemini_client, _groq_client, _cerebras_client, _sambanova_client, _openrouter_client, _openai_client
    current_provider = os.getenv("LLM_PROVIDER", "cerebras").lower().strip()
    
    if current_provider == "gemini":
        if _gemini_client is None:
            gemini_key = os.getenv("GEMINI_API_KEY")
            if not gemini_key:
                raise ValueError("GEMINI_API_KEY is not set correctly in .env")
            _gemini_client = genai.Client(api_key=gemini_key)
        return _gemini_client
    elif current_provider == "groq":
        if _groq_client is None:
            groq_key = os.getenv("GROQ_API_KEY")
            if not groq_key:
                raise ValueError("GROQ_API_KEY is not set correctly in .env")
            _groq_client = Groq(api_key=groq_key)
        return _groq_client
    elif current_provider == "cerebras":
        if _cerebras_client is None:
            key = os.getenv("CEREBRAS_API_KEY")
            if not key:
                raise ValueError("CEREBRAS_API_KEY is not set in .env")
            _cerebras_client = OpenAI(api_key=key, base_url="https://api.cerebras.ai/v1")
        return _cerebras_client
    elif current_provider == "sambanova":
        if _sambanova_client is None:
            key = os.getenv("SAMBANOVA_API_KEY")
            if not key:
                raise ValueError("SAMBANOVA_API_KEY is not set in .env")
            _sambanova_client = OpenAI(api_key=key, base_url="https://api.sambanova.ai/v1")
        return _sambanova_client
    elif current_provider == "openrouter":
        if _openrouter_client is None:
            key = os.getenv("OPENROUTER_API_KEY")
            if not key:
                raise ValueError("OPENROUTER_API_KEY is not set in .env")
            _openrouter_client = OpenAI(api_key=key, base_url="https://openrouter.ai/api/v1")
        return _openrouter_client
    elif current_provider == "openai":
        if _openai_client is None:
            key = os.getenv("OPENAI_API_KEY")
            if not key:
                raise ValueError("OPENAI_API_KEY is not set in .env")
            _openai_client = OpenAI(api_key=key)
        return _openai_client
    else:
        raise ValueError(f"Unsupported LLM_PROVIDER: {current_provider}")


def call_llm(prompt_string: str, retries: int = 3, profiler=None) -> tuple[str, dict]:
    """
    Executes an LLM request with automatic retry-on-failure and exact token usage tracking.
    
    Returns:
        tuple[str, dict]: (response_text, token_stats)
        where token_stats = {"prompt_tokens": int, "completion_tokens": int, "total_tokens": int, "model": str}
    """
    current_provider = os.getenv("LLM_PROVIDER", "cerebras").lower().strip()
    client = get_client()

    if current_provider == "gemini":
        active_model = os.getenv("GEMINI_MODEL", GEMINI_MODEL)
    elif current_provider == "groq":
        active_model = os.getenv("GROQ_MODEL", GROQ_MODEL)
    elif current_provider == "cerebras":
        active_model = os.getenv("CEREBRAS_MODEL", CEREBRAS_MODEL)
    elif current_provider == "sambanova":
        active_model = os.getenv("SAMBANOVA_MODEL", SAMBANOVA_MODEL)
    elif current_provider == "openrouter":
        active_model = os.getenv("OPENROUTER_MODEL", OPENROUTER_MODEL)
    elif current_provider == "openai":
        active_model = os.getenv("OPENAI_MODEL", OPENAI_MODEL)
    else:
        active_model = "default-model"
    
    attempt = 0
    while True:
        attempt += 1
        try:
            with time_block(f"LLM Call ({current_provider.upper()} - {active_model}, attempt {attempt})", 
                            parent_summary=profiler.categories if profiler else None, 
                            category="LLM API Inference"):
                if current_provider == "gemini":
                    response = client.models.generate_content(
                        model=active_model,
                        contents=prompt_string,
                        config=types.GenerateContentConfig(temperature=0.0)
                    )
                    raw_output = response.text.strip() if response.text else ""
                    
                    # Extract token stats
                    usage = getattr(response, 'usage_metadata', None)
                    prompt_tokens = getattr(usage, 'prompt_token_count', 0) if usage else 0
                    completion_tokens = getattr(usage, 'candidates_token_count', 0) if usage else 0
                    total_tokens = getattr(usage, 'total_token_count', 0) if usage else (prompt_tokens + completion_tokens)
                    
                elif current_provider in ("groq", "cerebras", "sambanova", "openrouter", "openai"):
                    response = client.chat.completions.create(
                        model=active_model,
                        messages=[
                            {"role": "system", "content": "You are an expert database assistant. Your goal is to generate accurate, syntactically valid SQL queries adhering strictly to the provided database schema."},
                            {"role": "user", "content": prompt_string}
                        ],
                        temperature=0.0
                    )
                    raw_output = response.choices[0].message.content.strip() if response.choices else ""
                    
                    # Extract token stats
                    usage = getattr(response, 'usage', None)
                    prompt_tokens = getattr(usage, 'prompt_tokens', 0) if usage else 0
                    completion_tokens = getattr(usage, 'completion_tokens', 0) if usage else 0
                    total_tokens = getattr(usage, 'total_tokens', 0) if usage else (prompt_tokens + completion_tokens)

                token_stats = {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens
                }
                
                log_step(f"LLM Call Successful | Tokens: {prompt_tokens} in / {completion_tokens} out / {total_tokens} total")
                return raw_output, token_stats
                
        except Exception as e:
            err_msg = str(e)
            log_step(f"LLM Call attempt {attempt} failed: {e}", level="WARN")
            # If rate limited (429), pause 15 seconds and retry same sample indefinitely until success
            if "429" in err_msg or "rate_limit" in err_msg or "too_many_requests" in err_msg:
                log_step("    [RATE-LIMIT 429] Waiting 15s before retrying same query sample...", level="WARN")
                time.sleep(15.0)
            else:
                # If non-rate-limit error (e.g. fatal syntax), max 3 attempts then re-raise
                if attempt >= retries:
                    log_step(f"All {retries} attempts failed for LLM Call.", level="ERROR")
                    raise e
                time.sleep(2.0)
            
    raise RuntimeError("LLM execution failed after retries.")
