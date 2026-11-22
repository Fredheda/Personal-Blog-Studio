import { describe, expect, it } from "vitest";

import { slugInput } from "./slug";

describe("slugInput", () => {
  it("lower-cases, turns spaces into hyphens and drops other characters", () => {
    expect(slugInput("Hello World_2!")).toBe("hello-world2");
  });

  it("keeps hyphens so a slug can be typed one character at a time", () => {
    expect(slugInput("a-")).toBe("a-");
  });
});
