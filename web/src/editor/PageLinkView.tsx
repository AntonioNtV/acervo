import { NodeViewWrapper, type ReactNodeViewProps } from "@tiptap/react";
import { createContext, useContext } from "react";
import { Link } from "react-router-dom";
import { useI18n } from "../i18n";
import { Icon } from "./icons";

/** Where `[[Título]]` leads: the page's address, or why there is none. */
export type LinkTarget = { href: string } | "missing" | "ambiguous";

export const ResolveLink = createContext<(title: string) => LinkTarget>(() => "missing");

export function PageLinkView({ node }: ReactNodeViewProps) {
  const { t } = useI18n();
  const title = String(node.attrs.title);
  const target = useContext(ResolveLink)(title);
  return (
    <NodeViewWrapper as="span">
      {typeof target === "object" ? (
        <Link to={target.href} className="page-link" contentEditable={false}>
          <Icon name="subpage" size={14} />
          {title}
        </Link>
      ) : (
        <span className="text-ghost" title={t(`editor.link.${target}`)}>
          {title}
        </span>
      )}
    </NodeViewWrapper>
  );
}
