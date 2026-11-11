import pytest

from blog_core import ids

ULID = "01ARZ3NDEKTSV4RRFFQ69G5FAV"


def test_new_id_is_a_valid_post_id_and_unique() -> None:
    a, b = ids.new_id(), ids.new_id()
    assert ids.is_post_id(a) and a != b


@pytest.mark.parametrize("value", [ULID, "7ZZZZZZZZZZZZZZZZZZZZZZZZZ"])
def test_post_id_accepts_ulids(value: str) -> None:
    assert ids.is_post_id(value)


@pytest.mark.parametrize(
    "value",
    [
        "",
        ULID[:-1],
        ULID + "A",
        ULID.lower(),
        "../" + ULID[3:],
        ULID[:-1] + "U",
        ULID[:-1] + "I",
        f"{ULID[:-1]}/",
    ],
)
def test_post_id_rejects_everything_else(value: str) -> None:
    assert not ids.is_post_id(value)


@pytest.mark.parametrize("value", ["a", "hello-world", "a1-b2-c3", "x" * 100])
def test_slug_accepts(value: str) -> None:
    assert ids.is_slug(value)


@pytest.mark.parametrize(
    "value", ["", "-a", "a-", "a--b", "A", "a_b", "a b", "a/b", "x" * 101, "ä"]
)
def test_slug_rejects(value: str) -> None:
    assert not ids.is_slug(value)


@pytest.mark.parametrize("value", ["a", "A_b-9", "x" * 64])
def test_media_id_accepts(value: str) -> None:
    assert ids.is_media_id(value)


@pytest.mark.parametrize("value", ["", "a.b", "a/b", "a b", "x" * 65, "..", "ä"])
def test_media_id_rejects(value: str) -> None:
    assert not ids.is_media_id(value)


def test_extension_and_tag_rules() -> None:
    assert (
        ids.is_extension("png")
        and not ids.is_extension("")
        and not ids.is_extension("a.b")
    )
    assert not ids.is_extension("PNG") and not ids.is_extension("x" * 9)
    assert (
        ids.is_tag("ml")
        and ids.is_tag("data-2")
        and not ids.is_tag("-x")
        and not ids.is_tag("A")
    )
    assert not ids.is_tag("x" * 51)


def test_a_trailing_newline_is_not_accepted() -> None:
    assert (
        not ids.is_slug("a\n")
        and not ids.is_media_id("a\n")
        and not ids.is_post_id(ULID + "\n")
    )
