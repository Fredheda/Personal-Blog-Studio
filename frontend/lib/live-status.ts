import type { ListItem } from "./studio-api";

export function postStatus(item: Pick<ListItem, "published" | "version">): string {
  return item.published ? `Published, version ${item.version}` : "Draft";
}

export function publishedNotice(version: number, slug: string): string {
  return `Published as version ${version}. It is live at /blog/${slug}.`;
}

export function unpublishedNotice(slug: string): string {
  const what = slug ? `/blog/${slug}` : "The post";
  return `Unpublished. ${what} can stay on the live site for a few seconds.`;
}
