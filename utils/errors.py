"""Errors whose message is safe and useful to show to the person using the app."""
from utils.config import IS_PRODUCTION


class UserFacingError(Exception):
    status_code = 400


class InvalidRepoURL(UserFacingError, ValueError):
    status_code = 400


class RepoNotFound(UserFacingError):
    status_code = 404


class RepoTooLarge(UserFacingError):
    status_code = 413


class CloneFailed(UserFacingError):
    status_code = 502


class ServerBusy(UserFacingError):
    status_code = 503


def friendly_error(exc):
    """Turn any exception into a message a person can act on. Details go to the server log."""
    if isinstance(exc, UserFacingError):
        return str(exc)

    name = type(exc).__name__
    text = str(exc)
    low = text.lower()

    if isinstance(exc, ValueError) and "OPENAI_API_KEY" in text:
        return text
    if name == "AuthenticationError" or "invalid_api_key" in low or "incorrect api key" in low:
        return "OpenAI rejected the API key. Check OPENAI_API_KEY on the server and restart it."
    if "insufficient_quota" in low:
        return "The OpenAI account is out of credit. Add credit or use a different API key."
    if name == "RateLimitError":
        return "OpenAI's rate limit was reached. Wait a minute, then try again."
    if name in ("APIConnectionError", "APITimeoutError"):
        return "The server couldn't reach OpenAI. Check its internet connection and try again."
    if name == "BadRequestError" and "context_length" in low:
        return "The question and context were too long for the model. Ask a shorter question."

    if IS_PRODUCTION:
        return "Something went wrong on the server. Try again, and check the server logs if it keeps happening."
    return f"{name}: {text[:300]}"
