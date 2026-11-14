from utils.errors import RepoNotFound, friendly_error


class AuthenticationError(Exception):
    pass


class RateLimitError(Exception):
    pass


def test_user_facing_errors_pass_through():
    assert friendly_error(RepoNotFound("nope")) == "nope"


def test_openai_errors_get_actionable_messages():
    assert "API key" in friendly_error(AuthenticationError("401"))
    assert "out of credit" in friendly_error(RateLimitError("insufficient_quota"))
    assert "rate limit" in friendly_error(RateLimitError("slow down"))


def test_unknown_errors_do_not_crash():
    assert friendly_error(RuntimeError("boom"))
