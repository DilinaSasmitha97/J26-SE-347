import os
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types
from groq import Groq

from profiler import time_block, log_step

# Load environment variables
load_dotenv()

PROVIDER = os.getenv("LLM_PROVIDER", "groq").lower().strip()
GROQ_MODEL = "llama-3.3-70b-versatile"
GEMINI_MODEL = "gemini-3.5-flash"

# Lazy Client Initialization
_gemini_client = None
_groq_client = None

def get_client():
    global _gemini_client, _groq_client
    if PROVIDER == "gemini":
        if _gemini_client is None:
            gemini_key = os.getenv("GEMINI_API_KEY")
            if not gemini_key:
                raise ValueError("GEMINI_API_KEY is not set correctly in .env")
            _gemini_client = genai.Client(api_key=gemini_key)
        return _gemini_client
    elif PROVIDER == "groq":
        if _groq_client is None:
            groq_key = os.getenv("GROQ_API_KEY")
            if not groq_key:
                raise ValueError("GROQ_API_KEY is not set correctly in .env")
            _groq_client = Groq(api_key=groq_key)
        return _groq_client
    else:
        raise ValueError(f"Unsupported LLM_PROVIDER: {PROVIDER}")


def call_llm(prompt_string: str, retries: int = 3, profiler=None) -> tuple[str, dict]:
    """
    Executes an LLM request with automatic retry-on-failure and exact token usage tracking.
    
    Returns:
        tuple[str, dict]: (response_text, token_stats)
        where token_stats = {"prompt_tokens": int, "completion_tokens": int, "total_tokens": int}
    """
    client = get_client()
    active_model = GEMINI_MODEL if PROVIDER == "gemini" else GROQ_MODEL
    
    attempt = 0
    backoff_delay = 1.0
    
    while attempt < retries:
        attempt += 1
        try:
            with time_block(f"LLM Call ({PROVIDER.upper()} - {active_model}, attempt {attempt}/{retries})", 
                            parent_summary=profiler.categories if profiler else None, 
                            category="LLM API Inference"):
                if PROVIDER == "gemini":
                    response = client.models.generate_content(
                        model=GEMINI_MODEL,
                        contents=prompt_string,
                        config=types.GenerateContentConfig(temperature=0.0)
                    )
                    raw_output = response.text.strip() if response.text else ""
                    
                    # Extract token stats
                    usage = getattr(response, 'usage_metadata', None)
                    prompt_tokens = getattr(usage, 'prompt_token_count', 0) if usage else 0
                    completion_tokens = getattr(usage, 'candidates_token_count', 0) if usage else 0
                    total_tokens = getattr(usage, 'total_token_count', 0) if usage else (prompt_tokens + completion_tokens)
                    
                elif PROVIDER == "groq":
                    response = client.chat.completions.create(
                        model=GROQ_MODEL,
                        messages=[
                            {"role": "system", "content": "You are an expert SQL assistant. Your only goal is to generate correct SQL queries."},
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
            log_step(f"LLM Call attempt {attempt}/{retries} failed: {e}", level="WARN")
            if attempt >= retries:
                log_step(f"All {retries} retries failed for LLM Call.", level="ERROR")
                raise e
            time.sleep(backoff_delay)
            backoff_delay *= 2.0  # Exponential backoff
            
    raise RuntimeError("LLM execution failed after retries.")
