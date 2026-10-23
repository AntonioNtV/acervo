import { createContext, useContext, type ReactNode } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import { Link } from "react-router-dom";
import remarkGfm from "remark-gfm";

const CITE = "#cite-";

type HrefOf = (marker: number) => string | undefined;
const Citations = createContext<HrefOf>(() => undefined);

function Anchor({ href = "", children }: { href?: string; children?: ReactNode }) {
  const hrefOf = useContext(Citations);
  if (!href.startsWith(CITE))
    return (
      <a href={href} target="_blank" rel="noreferrer" className="text-ink underline underline-offset-[3px]">
        {children}
      </a>
    );
  const marker = Number(href.slice(CITE.length));
  return (
    <Link
      to={hrefOf(marker) ?? ""}
      className="inline-flex h-4 min-w-4 items-center justify-center rounded-[4px] bg-accent-soft px-1 align-[1px] text-11 leading-4 font-medium text-ink no-underline"
    >
      {marker}
    </Link>
  );
}

// Fixed, so a streaming reply re-renders its text in place instead of remounting it.
const components: Components = {
  p: ({ children }) => <p className="m-0">{children}</p>,
  ul: ({ children }) => <ul className="m-0 flex flex-col gap-0.5 pl-5">{children}</ul>,
  ol: ({ children }) => <ol className="m-0 flex flex-col gap-0.5 pl-5">{children}</ol>,
  h1: ({ children }) => <h3 className="m-0 text-15 font-medium">{children}</h3>,
  h2: ({ children }) => <h3 className="m-0 text-13 font-medium">{children}</h3>,
  h3: ({ children }) => <h3 className="m-0 text-13 font-medium">{children}</h3>,
  code: ({ children }) => <code className="font-mono text-12">{children}</code>,
  pre: ({ children }) => (
    <pre className="m-0 overflow-x-auto rounded-[7px] border border-line px-2.5 py-2 font-mono text-12">{children}</pre>
  ),
  blockquote: ({ children }) => <blockquote className="m-0 border-l-2 border-line-2 pl-2.5 text-text-2">{children}</blockquote>,
  table: ({ children }) => (
    <div className="overflow-x-auto">
      <table className="border-collapse text-12">{children}</table>
    </div>
  ),
  th: ({ children }) => <th className="border border-line px-2 py-1 text-left font-medium">{children}</th>,
  td: ({ children }) => <td className="border border-line px-2 py-1">{children}</td>,
  a: ({ href, children }) => <Anchor href={href}>{children}</Anchor>,
};

/** A reply's text as Markdown, with no raw HTML. Each `[n]` with a source becomes its citation, opening it. */
export function ReplyText({ text, hrefOf }: { text: string; hrefOf: HrefOf }) {
  const cited = text.replace(/\[(\d+)\](?!\()/g, (marker, n: string) => (hrefOf(Number(n)) ? `[\\[${n}\\]](${CITE}${n})` : marker));
  return (
    <div className="flex flex-col gap-2 break-words">
      <Citations.Provider value={hrefOf}>
        <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
          {cited}
        </ReactMarkdown>
      </Citations.Provider>
    </div>
  );
}
