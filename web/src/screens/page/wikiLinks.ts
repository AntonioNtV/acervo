import type { NodeDetail } from "../../api/client";
import { normalizeLinkTarget } from "../../data/pages";

export type Links = NonNullable<NodeDetail["page"]>["links"];

type MdNode = {
  type: string;
  value?: string;
  url?: string;
  children?: MdNode[];
  data?: { hName?: string; hProperties?: Record<string, unknown> };
};

type Options = { links: Links; href: (nodeId: string) => string; titles: Record<"missing" | "ambiguous", string> };

// The server's rule (pages/links.py): no brackets inside the target.
const LINK = /\[\[([^[\]]+)\]\]/g;

/** Turns `[[Título]]` into a link to the page the API resolved, or a gray span when it is missing or ambiguous. */
export function remarkWikiLinks({ links, href, titles }: Options) {
  function split(value: string): MdNode[] {
    const out: MdNode[] = [];
    let last = 0;
    for (const match of value.matchAll(LINK)) {
      const target = match[1] ?? "";
      const key = normalizeLinkTarget(target);
      if (!key) continue;
      if (match.index > last) out.push({ type: "text", value: value.slice(last, match.index) });
      // A link typed since the last save is not in `links` yet: gray until the page is saved.
      const resolved = links[key] ?? "missing";
      const label = { type: "text", value: target };
      out.push(
        resolved === "missing" || resolved === "ambiguous"
          ? {
              type: "wikiLink",
              data: { hName: "span", hProperties: { className: ["text-ghost"], title: titles[resolved] } },
              children: [label],
            }
          : { type: "link", url: href(resolved), children: [label] },
      );
      last = match.index + match[0].length;
    }
    if (last === 0) return [{ type: "text", value }];
    if (last < value.length) out.push({ type: "text", value: value.slice(last) });
    return out;
  }

  function walk(node: MdNode) {
    if (!node.children || node.type === "link") return;
    node.children = node.children.flatMap((child) => {
      if (child.type === "text" && child.value) return split(child.value);
      walk(child);
      return [child];
    });
  }

  return walk;
}
