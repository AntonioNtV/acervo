import { useMemo } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import { Link } from "react-router-dom";
import remarkGfm from "remark-gfm";
import { useI18n } from "../../i18n";
import { remarkWikiLinks, type Links } from "./wikiLinks";

const components: Components = {
  h1: ({ node: _, ...props }) => <h1 className="mt-0 mb-1.5 text-24 font-medium tracking-[-0.03em]" {...props} />,
  h2: ({ node: _, ...props }) => <h2 className="mt-7 mb-2 text-15 font-medium tracking-[-0.01em]" {...props} />,
  h3: ({ node: _, ...props }) => <h3 className="mt-5 mb-1.5 text-13 font-medium" {...props} />,
  p: ({ node: _, ...props }) => <p className="my-2 text-[14px] leading-[22px] text-text-2" {...props} />,
  ul: ({ node: _, ...props }) => (
    <ul className="my-0 flex list-disc flex-col gap-1.5 pl-[18px] text-[14px] leading-[22px]" {...props} />
  ),
  ol: ({ node: _, ...props }) => (
    <ol className="my-0 flex list-decimal flex-col gap-1.5 pl-[18px] text-[14px] leading-[22px]" {...props} />
  ),
  blockquote: ({ node: _, ...props }) => (
    <blockquote className="mx-0 my-3 border-l-2 border-line-2 pl-3 text-text-2" {...props} />
  ),
  code: ({ node: _, ...props }) => <code className="font-mono text-12" {...props} />,
  pre: ({ node: _, ...props }) => (
    <pre className="my-3 overflow-x-auto rounded-[7px] border border-line p-3 font-mono text-12" {...props} />
  ),
  hr: () => <hr className="my-6 border-0 border-t border-line" />,
  table: ({ node: _, ...props }) => <table className="my-3 border-collapse text-13" {...props} />,
  th: ({ node: _, ...props }) => <th className="border-b border-line-2 px-2 py-1.5 text-left font-medium" {...props} />,
  td: ({ node: _, ...props }) => <td className="border-b border-line px-2 py-1.5" {...props} />,
  a: ({ node: _, href = "", ...props }) =>
    href.startsWith("/") ? (
      <Link to={href} className="text-text" {...props} />
    ) : (
      <a href={href} target="_blank" rel="noreferrer" className="text-text" {...props} />
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
