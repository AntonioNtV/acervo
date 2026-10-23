import type { Payload, Proposal, ProposalSummary } from "../../data/proposals";
import { locale, type Lang } from "../../i18n";

type T = (key: string, vars?: Record<string, string | number>) => string;

/** "Bradesco/Residencial" as the person reads a path: "Bradesco / Residencial". */
export function spaced(path: string): string {
  return path.split("/").filter(Boolean).join(" / ");
}

function join(parent: string, name: string): string {
  return parent ? `${parent}/${name}` : name;
}

function section(path: string, heading: string): string {
  return heading ? `${spaced(path)}.md § ${heading}` : `${spaced(path)}.md`;
}

/** What a proposal does, its person's version when edited. */
export function payloadOf(proposal: Proposal | ProposalSummary): Payload {
  return proposal.edited_payload ?? proposal.payload;
}

/** Where it goes, in the mono line every proposal shows before its buttons. */
export function whereOf(payload: Payload, t: T): string {
  switch (payload.kind) {
    case "append":
    case "edit":
    case "conflict":
      return section(payload.path, payload.heading);
    case "create_page":
      return `${spaced(join(payload.parent_path, payload.title))}.md`;
    case "save_pdf":
      return spaced(join(payload.parent_path, payload.name));
    case "move":
      return `${spaced(payload.from_path)} → ${spaced(payload.to_path) || t("chat.root")}`;
    case "rename":
      return `${spaced(payload.path)} → ${payload.title}`;
    case "replace_pdf":
    case "undo":
      return spaced(payload.path);
  }
}

export function lastPart(path: string): string {
  return path.split("/").filter(Boolean).at(-1) ?? path;
}

/**
 * An input with no clear place: its page or file was put under the likeliest of the places it hesitated between,
 * which the API keeps as its first alternative; a placed one keeps only the runner-up, elsewhere.
 */
export function isUnplaced(proposal: Proposal | ProposalSummary): boolean {
  const { payload, alternatives, edited_payload } = proposal;
  if (edited_payload || (payload.kind !== "create_page" && payload.kind !== "save_pdf")) return false;
  const first = alternatives?.[0];
  if (!first) return false;
  return (alternatives?.length ?? 0) > 1 || (first.node_id === payload.parent_id && first.path === payload.parent_path);
}

/** A probability as the boards write it: "0,86". */
export function probability(value: number, lang: Lang): string {
  return value.toLocaleString(locale(lang), { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
