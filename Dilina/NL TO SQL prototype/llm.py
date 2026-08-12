import os
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types
from groq import Groq
from openai import OpenAI

from profiler import time_block, log_step

# Load environment variables
load_dotenv()

PROVIDER = os.getenv("LLM_PROVIDER", "groq").lower().strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "qwen/qwen-2.5-coder-32b-instruct:free")

# Lazy Client Initialization
_gemini_client = None
_groq_client = None
_openrouter_client = None
_sambanova_client = None
_cerebras_client = None

def get_client(provider_override: str = None):
    global _gemini_client, _groq_client, _openrouter_client, _sambanova_client, _cerebras_client
    active_provider = provider_override or PROVIDER
    if active_provider == "gemini":
        if _gemini_client is None:
            gemini_key = os.getenv("GEMINI_API_KEY")
            if not gemini_key:
                raise ValueError("GEMINI_API_KEY is not set correctly in .env")
            _gemini_client = genai.Client(api_key=gemini_key)
        return _gemini_client
    elif active_provider == "groq":
        if _groq_client is None:
            groq_key = os.getenv("GROQ_API_KEY")
            if not groq_key:
                raise ValueError("GROQ_API_KEY is not set correctly in .env")
            _groq_client = Groq(api_key=groq_key)
        return _groq_client
    elif active_provider == "openrouter":
        if _openrouter_client is None:
            openrouter_key = os.getenv("OPENROUTER_API_KEY")
            if not openrouter_key:
                raise ValueError("OPENROUTER_API_KEY is not set correctly in .env")
            _openrouter_client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=openrouter_key
            )
        return _openrouter_client
    elif active_provider == "sambanova":
        if _sambanova_client is None:
            sambanova_key = os.getenv("SAMBANOVA_API_KEY")
            if not sambanova_key:
                raise ValueError("SAMBANOVA_API_KEY is not set correctly in .env")
            _sambanova_client = OpenAI(
                base_url="https://api.sambanova.ai/v1",
                api_key=sambanova_key
            )
        return _sambanova_client
    elif active_provider == "cerebras":
        if _cerebras_client is None:
            cerebras_key = os.getenv("CEREBRAS_API_KEY")
            if not cerebras_key:
                raise ValueError("CEREBRAS_API_KEY is not set correctly in .env")
            _cerebras_client = OpenAI(
                base_url="https://api.cerebras.ai/v1",
                api_key=cerebras_key
            )
        return _cerebras_client
    else:
        raise ValueError(f"Unsupported LLM_PROVIDER: {active_provider}")


def call_llm(prompt_string: str, model_name: str = None, retries: int = 3, profiler=None) -> tuple[str, dict]:
    """
    Executes an LLM request with automatic retry-on-failure and exact token usage tracking.
    """
    if model_name:
        if model_name.startswith("sambanova/") or "DeepSeek" in model_name or model_name.startswith("Meta-"):
            current_provider = "sambanova"
            active_model = model_name.replace("sambanova/", "")
        elif ":" in model_name or "/" in model_name:
            current_provider = "openrouter"
            active_model = model_name
        else:
            current_provider = PROVIDER
            active_model = model_name
    else:
        current_provider = PROVIDER
        active_model = "gemma-4-31b" if PROVIDER == "cerebras" else GROQ_MODEL

    client = get_client(provider_override=current_provider)
    
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
                    
                    usage = getattr(response, 'usage_metadata', None)
                    prompt_tokens = getattr(usage, 'prompt_token_count', 0) if usage else 0
                    completion_tokens = getattr(usage, 'candidates_token_count', 0) if usage else 0
                    total_tokens = getattr(usage, 'total_token_count', 0) if usage else (prompt_tokens + completion_tokens)
                    
                elif current_provider in ("groq", "openrouter", "sambanova", "cerebras"):
                    response = client.chat.completions.create(
                        model=active_model,
                        messages=[
                            {"role": "system", "content": "You are an expert SQL assistant. Your only goal is to generate correct SQL queries."},
                            {"role": "user", "content": prompt_string}
                        ],
                        temperature=0.0
                    )
                    raw_output = response.choices[0].message.content.strip() if response.choices else ""
                    
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
            if "429" in err_msg or "rate_limit" in err_msg or "too_many_requests" in err_msg:
                log_step("    [RATE-LIMIT 429] Waiting 15s before retrying same query sample...", level="WARN")
                time.sleep(15.0)
            else:
                if attempt >= retries:
                    log_step(f"All {retries} attempts failed for LLM Call.", level="ERROR")
                    raise e
                time.sleep(2.0)
                
    raise RuntimeError("LLM execution failed after retries.")
