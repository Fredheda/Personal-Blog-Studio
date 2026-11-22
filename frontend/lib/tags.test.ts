import { describe, expect, it } from "vitest";

import { addTags, removeLast, removeTag } from "./tags";

describe("addTags", () => {
  it("adds the trimmed, non-empty parts of a comma separated text", () => {
    expect(addTags(["a"], " b , ,c ")).toEqual(["a", "b", "c"]);
  });

  it("skips a tag that is already there, ignoring case", () => {
    expect(addTags(["Maths"], "maths, Physics")).toEqual(["Maths", "Physics"]);
  });

  it("leaves the list alone for an empty text", () => {
    expect(addTags(["a"], "  ")).toEqual(["a"]);
  });
});

describe("removing tags", () => {
  it("removes the last tag, or none from an empty list", () => {
    expect(removeLast(["a", "b"])).toEqual(["a"]);
    expect(removeLast([])).toEqual([]);
  });

  it("removes one named tag", () => {
    expect(removeTag(["a", "b", "c"], "b")).toEqual(["a", "c"]);
  });
});
