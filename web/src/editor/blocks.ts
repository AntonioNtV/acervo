import type { ChainedCommands } from "@tiptap/core";
import { blockMathKinds } from "./nodes/blockMath";
import { columnsKinds } from "./nodes/columns";
import { diagramKinds } from "./nodes/diagram";
import { fileMediaKinds } from "./nodes/fileMedia";
import { footnoteKinds } from "./nodes/footnote";
import { GENERATED_KINDS } from "./nodes/generated";
import { imageKinds } from "./nodes/image";
import { linkBlockKinds } from "./nodes/linkBlock";
import { MATH_KINDS } from "./nodes/math";
import { pdfPageKinds } from "./nodes/pdfPage";
import { syncedKinds } from "./nodes/synced";
import { toggleHeadingKinds } from "./nodes/toggleHeading";

/** A kind of block the "/" menu inserts and the handle's menu turns a block into. */
export type BlockKind = {
  id: string;
  group: "blocks" | "link";
  /** The Markdown typed to get it, shown at the right of the menu. */
  shortcut?: string;
  /** Turns the block holding the selection into this kind; absent for the kinds that insert something. */
  turn?: (chain: ChainedCommands) => ChainedCommands;
  /** For a list kind, its node: a list turned into another keeps its items and their nesting. */
  list?: "bulletList" | "orderedList" | "taskList";
};

export const BLOCK_KINDS: BlockKind[] = [
  { id: "text", group: "blocks", turn: (c) => c.clearNodes().setParagraph() },
  { id: "h1", group: "blocks", shortcut: "#", turn: (c) => c.clearNodes().setHeading({ level: 1 }) },
  { id: "h2", group: "blocks", shortcut: "##", turn: (c) => c.clearNodes().setHeading({ level: 2 }) },
  { id: "h3", group: "blocks", shortcut: "###", turn: (c) => c.clearNodes().setHeading({ level: 3 }) },
  { id: "h4", group: "blocks", shortcut: "####", turn: (c) => c.clearNodes().setHeading({ level: 4 }) },
  { id: "h5", group: "blocks", shortcut: "#####", turn: (c) => c.clearNodes().setHeading({ level: 5 }) },
  { id: "h6", group: "blocks", shortcut: "######", turn: (c) => c.clearNodes().setHeading({ level: 6 }) },
  ...toggleHeadingKinds,
  {
    id: "bullet",
    group: "blocks",
    shortcut: "-",
    turn: (c) => c.clearNodes().toggleBulletList(),
    list: "bulletList",
  },
  {
    id: "numbered",
    group: "blocks",
    shortcut: "1.",
    turn: (c) => c.clearNodes().toggleOrderedList(),
    list: "orderedList",
  },
  {
    id: "todo",
    group: "blocks",
    shortcut: "[]",
    turn: (c) => c.clearNodes().toggleTaskList(),
    list: "taskList",
  },
  { id: "quote", group: "blocks", shortcut: ">", turn: (c) => c.clearNodes().setBlockquote() },
  { id: "callout", group: "blocks", turn: (c) => c.clearNodes().setCallout() },
  { id: "toggle", group: "blocks", turn: (c) => c.clearNodes().setDetails() },
  { id: "code", group: "blocks", shortcut: "```", turn: (c) => c.clearNodes().setCodeBlock() },
  { id: "table", group: "blocks" },
  { id: "divider", group: "blocks", shortcut: "---" },
  ...columnsKinds,
  ...GENERATED_KINDS,
  ...footnoteKinds,
  ...MATH_KINDS,
  ...imageKinds,
  ...fileMediaKinds,
  ...blockMathKinds,
  ...diagramKinds,
  { id: "subpage", group: "blocks" },
  { id: "pageLink", group: "link", shortcut: "[[" },
  ...syncedKinds,
  ...linkBlockKinds,
  ...pdfPageKinds,
];

const fold = (text: string) =>
  text
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase();

/** The kinds whose name (in the reader's language) or id contains `query`, ignoring case and accents. */
export function findKinds(query: string, label: (kind: BlockKind) => string): BlockKind[] {
  const q = fold(query.trim());
  return BLOCK_KINDS.filter((kind) => !q || fold(label(kind)).includes(q) || fold(kind.id).includes(q));
}

export function findPages(query: string, titles: string[]): string[] {
  const q = fold(query.trim());
  return titles.filter((title) => fold(title).includes(q)).slice(0, 8);
}
