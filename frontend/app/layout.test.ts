import { expect, test } from "vitest";

import { metadata } from "./layout";

test("studio pages are not indexed by search engines", () => {
  expect(metadata.robots).toEqual({ index: false, follow: false });
});
