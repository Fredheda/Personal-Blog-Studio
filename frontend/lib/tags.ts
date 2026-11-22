export function addTags(list: string[], text: string): string[] {
  const next = [...list];
  for (const part of text.split(",")) {
    const tag = part.trim();
    if (tag !== "" && !next.some((t) => t.toLowerCase() === tag.toLowerCase())) next.push(tag);
  }
  return next;
}

export function removeLast(list: string[]): string[] {
  return list.slice(0, -1);
}

export function removeTag(list: string[], tag: string): string[] {
  return list.filter((t) => t !== tag);
}
