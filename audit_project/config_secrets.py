import os
from typing import Optional, Dict, Any

try:
    import streamlit as st
except ImportError:
    st = None

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def get_secret(key: str, default: Optional[str] = "") -> str:
    """
    Mengambil kredensial dengan urutan prioritas:
    1. Streamlit Secrets (st.secrets)
    2. Environment Variables (os.getenv)
    3. Default value
    """
    if st is not None:
        try:
            if hasattr(st, "secrets") and key in st.secrets:
                val = str(st.secrets[key]).strip()
                if val:
                    return val
        except Exception:
            pass

    env_val = os.getenv(key)
    if env_val is not None and env_val.strip() != "":
        return env_val.strip()

    return default if default is not None else ""


def get_llm_config() -> Dict[str, Any]:
    """
    Mengembalikan konfigurasi lengkap untuk provider LLM (Gemini & Claude).
    """
    return {
        "provider": get_secret("DEFAULT_LLM_PROVIDER", "gemini").lower(),
        "gemini_api_key": get_secret("GEMINI_API_KEY", ""),
        "gemini_model": get_secret("GEMINI_MODEL", "gemini-2.5-flash"),
        "anthropic_api_key": get_secret("ANTHROPIC_API_KEY", ""),
        "claude_model": get_secret("CLAUDE_MODEL", "claude-3-5-sonnet-20241022"),
    }


def get_gemini_api_key() -> str:
    return get_secret("GEMINI_API_KEY", "")


def get_smtp_config() -> Dict[str, Any]:
    port_str = get_secret("SMTP_PORT", "587")
    try:
        port = int(port_str)
    except ValueError:
        port = 587
    return {
        "server": get_secret("SMTP_SERVER", "smtp.gmail.com"),
        "port": port,
        "sender_email": get_secret("SMTP_SENDER_EMAIL", ""),
        "sender_password": get_secret("SMTP_SENDER_PASSWORD", ""),
    }


def get_n8n_webhook_url() -> str:
    return get_secret("N8N_WA_WEBHOOK_URL", get_secret("N8N_WEBHOOK_URL", ""))
