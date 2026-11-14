import pytest

from utils.errors import InvalidRepoURL
from utils.github_loader import get_repo_id, normalize_repo_url, parse_repo_url


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/pallets/click",
        "https://github.com/pallets/click.git",
        "github.com/pallets/click/",
        "https://www.github.com/pallets/click/tree/main/src?x=1#y",
        "  https://github.com/pallets/click  ",
    ],
)
def test_accepts_common_github_links(url):
    assert normalize_repo_url(url) == "https://github.com/pallets/click.git"
    assert parse_repo_url(url) == ("pallets", "click")


@pytest.mark.parametrize(
    "url",
    [
        "",
        "https://github.com/pallets",
        "https://gitlab.com/a/b",
        "ext::sh -c touch /tmp/x",
        "file:///etc/passwd",
        "/etc/passwd",
        "https://github.com/../x",
    ],
)
def test_rejects_everything_else(url):
    with pytest.raises(InvalidRepoURL):
        normalize_repo_url(url)


def test_repo_id_is_stable_and_case_insensitive():
    a = get_repo_id("https://github.com/Pallets/Click")
    b = get_repo_id("github.com/pallets/click.git")
    assert a == b
    assert len(a) == 10
