// @vitest-environment node
import { afterEach, beforeEach, expect, test, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  created: vi.fn(),
  getToken: vi.fn(async () => ({ token: "t0k" })),
}));

vi.mock("@azure/identity", () => ({
  ManagedIdentityCredential: class {
    constructor(options: unknown) {
      mocks.created(options);
    }
    getToken = mocks.getToken;
  },
}));

beforeEach(() => {
  vi.resetModules();
  mocks.created.mockClear();
  mocks.getToken.mockClear();
});
afterEach(() => vi.unstubAllEnvs());

async function load() {
  return (await import("./token")).getStudioToken;
}

test("no audience means no token and no identity lookup (a local run)", async () => {
  vi.stubEnv("STUDIO_API_AUDIENCE", "");
  vi.stubEnv("AZURE_CLIENT_ID", "client-1");
  expect(await (await load())()).toBeNull();
  expect(mocks.created).not.toHaveBeenCalled();
});

test("an audience without a client id is a configuration error, not a silent no-token", async () => {
  vi.stubEnv("STUDIO_API_AUDIENCE", "api://studio");
  vi.stubEnv("AZURE_CLIENT_ID", "");
  await expect((await load())()).rejects.toThrow("the studio API identity is not configured");
});

test("with both set the managed identity is asked for the audience's default scope", async () => {
  vi.stubEnv("STUDIO_API_AUDIENCE", "api://studio");
  vi.stubEnv("AZURE_CLIENT_ID", "client-1");
  expect(await (await load())()).toBe("t0k");
  expect(mocks.created).toHaveBeenCalledWith({ clientId: "client-1" });
  expect(mocks.getToken).toHaveBeenCalledWith("api://studio/.default");
});
