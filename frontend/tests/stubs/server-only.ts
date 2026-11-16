// `server-only` throws outside Next's server build; unit tests import the
// token module directly, so they get an empty stand-in. The real marker is
// pinned by tests/hardening.test.ts, which reads lib/token.ts itself.
export {};
