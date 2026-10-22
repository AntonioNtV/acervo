import { useMemo } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import { Link } from "react-router-dom";
import remarkGfm from "remark-gfm";
import { useI18n } from "../../i18n";
import { remarkWikiLinks, type Links } from "./wikiLinks";

/** react-markdown hands each element its `node`, which is not a DOM attribute. */
function withoutNode<T extends { node?: unknown }>(props: T): Omit<T, "node"> {
  const rest = { ...props };
  delete rest.node;
  return rest;
}

const components: Components = {
  h1: (props) => <h1 className="mt-0 mb-1.5 text-24 font-medium tracking-[-0.03em]" {...withoutNode(props)} />,
  h2: (props) => <h2 className="mt-7 mb-2 text-15 font-medium tracking-[-0.01em]" {...withoutNode(props)} />,
  h3: (props) => <h3 className="mt-5 mb-1.5 text-13 font-medium" {...withoutNode(props)} />,
  p: (props) => <p className="my-2 text-[14px] leading-[22px] text-text-2" {...withoutNode(props)} />,
  ul: (props) => (
    <ul className="my-0 flex list-disc flex-col gap-1.5 pl-[18px] text-[14px] leading-[22px]" {...withoutNode(props)} />
  ),
  ol: (props) => (
    <ol className="my-0 flex list-decimal flex-col gap-1.5 pl-[18px] text-[14px] leading-[22px]" {...withoutNode(props)} />
  ),
  blockquote: (props) => (
    <blockquote className="mx-0 my-3 border-l-2 border-line-2 pl-3 text-text-2" {...withoutNode(props)} />
  ),
  code: (props) => <code className="font-mono text-12" {...withoutNode(props)} />,
  pre: (props) => (
    <pre className="my-3 overflow-x-auto rounded-[7px] border border-line p-3 font-mono text-12" {...withoutNode(props)} />
  ),
  hr: () => <hr className="my-6 border-0 border-t border-line" />,
  table: (props) => <table className="my-3 border-collapse text-13" {...withoutNode(props)} />,
  th: (props) => <th className="border-b border-line-2 px-2 py-1.5 text-left font-medium" {...withoutNode(props)} />,
  td: (props) => <td className="border-b border-line px-2 py-1.5" {...withoutNode(props)} />,
  a: ({ href = "", ...props }) =>
    href.startsWith("/") ? (
      <Link to={href} className="text-text" {...withoutNode(props)} />
    ) : (
      <a href={href} target="_blank" rel="noreferrer" className="text-text" {...withoutNode(props)} />
    ),
};

export function Markdown({ markdown, links, kbId }: { markdown: string; links: Links; kbId: string }) {
  const { t } = useI18n();
  const missing = t("page.link.missing");
  const ambiguous = t("page.link.ambiguous");
  const remarkPlugins = useMemo(() => {
    const href = (nodeId: string) => `/kbs/${encodeURIComponent(kbId)}/n/${encodeURIComponent(nodeId)}`;
    return [remarkGfm, () => remarkWikiLinks({ links, href, titles: { missing, ambiguous } })];
  }, [links, kbId, missing, ambiguous]);
  return (
    <ReactMarkdown remarkPlugins={remarkPlugins} components={components}>
      {markdown}
    </ReactMarkdown>
  );
}
