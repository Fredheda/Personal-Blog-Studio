import pytest

from blog_core import layout

P = "01ARZ3NDEKTSV4RRFFQ69G5FAV"


def test_container_names_and_index() -> None:
    assert (layout.DRAFTS, layout.PUBLISHED, layout.INDEX) == ("blog-drafts", "blog-published", "index.json")


def test_draft_paths() -> None:
    assert layout.post_folder(P) == f"posts/{P}/"
    assert layout.draft_body(P) == f"posts/{P}/draft.md"
    assert layout.draft_meta(P) == f"posts/{P}/draft.json"
    assert layout.revision_prefix(P) == f"posts/{P}/rev/"
    assert layout.revision_body(P, "20261110T120000123Z") == f"posts/{P}/rev/20261110T120000123Z.md"
    assert layout.media_original("m_1", "png") == "media/m_1/original.png"
    assert layout.media_meta("m_1") == "media/m_1/meta.json"


def test_published_paths() -> None:
    assert layout.slug_ref("hello-world") == "slugs/hello-world.json"
    assert layout.versions_prefix(P) == f"posts/{P}/"
    assert layout.version_body(P, 2) == f"posts/{P}/v2/post.md"
    assert layout.version_meta(P, 2) == f"posts/{P}/v2/meta.json"
    assert layout.version_media(P, 2, "m_1", "png") == f"posts/{P}/v2/media/m_1.png"


@pytest.mark.parametrize("bad", ["", "../x", "a/b", P[:-1], P + "A", P.lower()])
def test_a_bad_post_id_raises(bad: str) -> None:
    for build in (layout.post_folder, layout.draft_body, layout.draft_meta, layout.revision_prefix, layout.versions_prefix):
        with pytest.raises(ValueError):
            build(bad)
    with pytest.raises(ValueError):
        layout.version_body(bad, 1)


@pytest.mark.parametrize("bad", ["", "..", "a/b", "a.b", "x" * 65])
def test_a_bad_media_id_raises(bad: str) -> None:
    with pytest.raises(ValueError):
        layout.media_meta(bad)
    with pytest.raises(ValueError):
        layout.media_original(bad, "png")


@pytest.mark.parametrize("bad", ["", "../x", "A", "a/b", "a--b"])
def test_a_bad_slug_raises(bad: str) -> None:
    with pytest.raises(ValueError):
        layout.slug_ref(bad)


@pytest.mark.parametrize("bad", ["", "a.b", "../x", "PNG"])
def test_a_bad_extension_raises(bad: str) -> None:
    with pytest.raises(ValueError):
        layout.media_original("m", bad)
    with pytest.raises(ValueError):
        layout.version_media(P, 1, "m", bad)


@pytest.mark.parametrize("bad", ["", "../x", "a/b", "a.b"])
def test_a_bad_revision_raises(bad: str) -> None:
    with pytest.raises(ValueError):
        layout.revision_body(P, bad)


@pytest.mark.parametrize("bad", [0, -1])
def test_a_bad_version_raises(bad: int) -> None:
    with pytest.raises(ValueError):
        layout.version_body(P, bad)
