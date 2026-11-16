import re

from conftest import REPO_ROOT

from studio_api.markdown import validate_body

FIXTURES = REPO_ROOT / "frontend" / "tests" / "fixtures" / "crepe-output"


def test_there_are_fixtures() -> None:
    assert sorted(p.name for p in FIXTURES.glob("*.md")) == [
        "basic.md",
        "breaks.md",
        "empty.md",
        "links.md",
        "maths-code-table.md",
    ]


def test_everything_the_editor_writes_passes_the_publish_validator() -> None:
    for path in sorted(FIXTURES.glob("*.md")):
        result = validate_body(path.read_text())
        assert result.problems == [], (path.name, result.problems)


def test_the_editor_writes_no_html_break() -> None:
    for path in sorted(FIXTURES.glob("*.md")):
        assert not re.search(r"<br\s*/?>", path.read_text(), re.I), path.name


def test_code_fences_use_the_lower_case_names_clients_match_on() -> None:
    text = (FIXTURES / "maths-code-table.md").read_text()
    infos = re.findall(r"^```(\S*)\s*$", text, re.M)
    opening = [i for i in infos if i]
    assert opening == ["python", "matlab"], opening
