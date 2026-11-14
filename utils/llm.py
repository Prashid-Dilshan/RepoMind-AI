import os
from functools import lru_cache

from langchain_openai import ChatOpenAI

from utils.config import LANGUAGE_MODEL, MAX_NEW_TOKENS, TEMPERATURE


@lru_cache(maxsize=4)
def _build(model_name, api_key):
    return ChatOpenAI(
        model=model_name,
        api_key=api_key,
        temperature=TEMPERATURE,
        max_tokens=MAX_NEW_TOKENS,
        timeout=90,
        max_retries=3,
    )


def get_llm(model_name=LANGUAGE_MODEL):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is missing. Add it to the server's environment and restart it.")
    return _build(model_name, api_key)
