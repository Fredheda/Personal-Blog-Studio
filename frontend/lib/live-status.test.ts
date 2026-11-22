import { expect, test } from "vitest";

import { postStatus, publishedNotice, unpublishedNotice } from "./live-status";

test("a published post says Published and its version", () => {
  expect(postStatus({ published: true, version: 2 })).toBe("Published, version 2");
});

test("an unpublished post says Draft", () => {
  expect(postStatus({ published: false, version: null })).toBe("Draft");
});

test("publishing says what is live and where", () => {
  expect(publishedNotice(1, "hello")).toBe("Published as version 1. Live at /blog/hello.");
});

test("unpublishing says the post can stay on the live site for a few seconds", () => {
  expect(unpublishedNotice("hello")).toBe(
    "Unpublished. /blog/hello can stay on the live site for a few seconds.",
  );
});

test("unpublishing a post without a slug does not print an empty path", () => {
  expect(unpublishedNotice("")).toBe(
    "Unpublished. The post can stay on the live site for a few seconds.",
  );
});
