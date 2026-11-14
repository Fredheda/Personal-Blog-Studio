# Read API changelog

Changes to `openapi/v1.json`, newest first. A change to the contract needs a new heading here and the matching `info.version` in the file; `backend/tests/test_openapi_contract.py` fails otherwise. Inside `v1` only additive changes are allowed (new optional fields, new endpoints).

## 1.0.0

First release: `GET /v1/posts`, `GET /v1/posts/{slug}`, `GET /v1/media/{mediaId}?post=`, `GET /v1/posts/{slug}/audio` (always 404 until read-aloud ships), `GET /healthz`. Errors are `application/problem+json` (400 bad query, 401, 403, 404). `audio` is `null`.
