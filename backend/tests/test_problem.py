import json

from blog_core.problem import PROBLEM_JSON, problem


def test_problem_is_rfc_9457_json() -> None:
    response = problem(409, "Conflict", "the draft changed; reload it")
    assert response.status_code == 409
    assert response.media_type == PROBLEM_JSON == "application/problem+json"
    assert json.loads(bytes(response.body)) == {
        "type": "about:blank",
        "title": "Conflict",
        "status": 409,
        "detail": "the draft changed; reload it",
    }


def test_problem_omits_a_missing_detail_and_carries_extra_members() -> None:
    body = json.loads(
        bytes(problem(422, "Invalid", problems=[{"line": 3, "message": "x"}]).body)
    )
    assert "detail" not in body
    assert body["problems"] == [{"line": 3, "message": "x"}]


def test_problem_can_carry_headers() -> None:
    response = problem(405, "Method Not Allowed", headers={"Allow": "GET"})
    assert response.headers["allow"] == "GET"
    assert response.media_type == PROBLEM_JSON
