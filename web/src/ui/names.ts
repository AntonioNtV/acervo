/** `Condições Gerais 2026.pdf` → name and extension, so the extension can be shown in gray. */
export function splitExt(title: string): { name: string; ext?: string } {
  const dot = title.lastIndexOf(".");
  return dot > 0 ? { name: title.slice(0, dot), ext: title.slice(dot + 1) } : { name: title };
}

/**
 * The folders above a node as "Bradesco / Residencial". The API's `path` ends in the node's own title, which may hold
 * a "/", so the title is cut off whole before splitting.
 */
export function folderPath(path: string, title: string): string {
  const folders = path.endsWith(`/${title}`) ? path.slice(0, -title.length - 1) : path === title ? "" : path;
  return folders.split("/").filter(Boolean).join(" / ");
}
