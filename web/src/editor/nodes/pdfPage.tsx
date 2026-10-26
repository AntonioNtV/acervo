import { Node } from "@tiptap/core";
import { NodeViewWrapper, ReactNodeViewRenderer, type ReactNodeViewProps } from "@tiptap/react";
import { useContext, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { rawFileSource } from "../../data/files";
import { useSearch } from "../../data/tree";
import { useI18n } from "../../i18n";
import { FileName } from "../../ui/FileName";
import { openPdf, type PDFDocumentProxy } from "../../viewer/pdfjs";
import type { BlockKind } from "../blocks";
import { startBefore } from "../tokenize";
import { PageContext } from "./generated";
import { SyncedSource } from "./synced";
import "./pdfPage.css";

declare module "@tiptap/core" {
  interface Commands<ReturnType> {
    pdfPage: { insertPdfPage: () => ReturnType };
  }
}

// A line holding only `[[Name.pdf#p=N]]`; `#p=012` is not a page number and stays a page link, so it reads back the same.
const LINE = /^\[\[([^[\]#]+\.pdf)#p=([1-9]\d*)\]\][ \t]*(?:\n|$)/i;

// Not yet picked: nothing to write, rather than a `[[#p=1]]` that reads back as a page link.
const markdownOf = (attrs: Record<string, unknown> | undefined) =>
  attrs?.title ? `[[${attrs.title}#p=${attrs.page}]]` : "";

// pdf.js scale 1 is 72 dpi.
const CSS_UNITS = 96 / 72;

/** `[[Condições Gerais 2026.pdf#p=12]]`: that page of a PDF of the base, drawn from the original file, never copied. */
export const PdfPage = Node.create({
  name: "pdfPage",
  group: "block",
  atom: true,
  selectable: true,
  addAttributes: () => ({
    title: { default: "" },
    page: { default: 1 },
    // Just inserted: the view asks which PDF and page, once.
    choosing: { default: false, rendered: false },
  }),
  parseHTML: () => [
    {
      tag: "div[data-pdf-page]",
      getAttrs: (el) => ({
        title: (el as HTMLElement).dataset.pdfPage ?? "",
        page: Number((el as HTMLElement).dataset.page) || 1,
      }),
    },
  ],
  renderHTML: ({ node }) => [
    "div",
    { "data-pdf-page": node.attrs.title, "data-page": node.attrs.page, class: "pdf-page" },
    markdownOf(node.attrs),
  ],
  renderText: ({ node }) => markdownOf(node.attrs),
  addCommands() {
    return {
      insertPdfPage:
        () =>
        ({ commands }) =>
          commands.insertContent({ type: this.name, attrs: { choosing: true } }),
    };
  },
  markdownTokenizer: {
    name: "pdfPage",
    level: "block",
    start: startBefore(/^\[\[/m),
    tokenize: (src) => {
      const match = LINE.exec(src);
      return match ? { type: "pdfPage", raw: match[0], title: match[1], page: Number(match[2]) } : undefined;
    },
  },
  parseMarkdown: (token, h) => h.createNode("pdfPage", { title: token.title, page: token.page }),
  renderMarkdown: (node) => markdownOf(node.attrs),
});

/** The PDF search and the page number, until one is picked. */
function Picker({ onPick }: { onPick: (title: string, page: number) => void }) {
  const { t } = useI18n();
  const host = useContext(PageContext);
  const [query, setQuery] = useState("");
  const [page, setPage] = useState("1");
  const hits = useSearch(host?.kbId ?? "", host ? query : "").data ?? [];
  const pdfs = hits.filter((hit) => hit.kind === "file" && /\.pdf$/i.test(hit.title));
  return (
    <div className="pdf-page-picker">
      <div className="flex gap-2">
        <input
          autoFocus
          aria-label={t("editor.pdfPage.pick")}
          placeholder={t("editor.pdfPage.pick")}
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          className="h-[30px] min-w-0 flex-1 rounded-[6px] border border-line-2 bg-bg px-2.5 text-13 text-text focus:border-ink focus:outline-none"
        />
        <input
          aria-label={t("editor.pdfPage.number")}
          inputMode="numeric"
          value={page}
          onChange={(event) => setPage(event.target.value.replace(/\D/g, ""))}
          className="h-[30px] w-16 rounded-[6px] border border-line-2 bg-bg text-center text-13 text-text tabular-nums focus:border-ink focus:outline-none"
        />
      </div>
      {pdfs.length > 0 && (
        <ul className="m-0 mt-1 flex list-none flex-col p-0">
          {pdfs.map((pdf) => (
            <li key={pdf.id}>
              <button
                type="button"
                onClick={() => onPick(pdf.title, Math.max(Number(page) || 1, 1))}
                className="flex h-[30px] w-full cursor-pointer items-center rounded-[6px] border-0 bg-transparent px-2.5 text-left text-13 text-text hover:bg-subtle"
              >
                {pdf.title}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

type Shown = { doc: PDFDocumentProxy } | "loading" | "failed" | "locked";

export function PdfPageView({ node, updateAttributes }: ReactNodeViewProps) {
  const { t } = useI18n();
  const navigate = useNavigate();
  const title = String(node.attrs.title);
  const page = Number(node.attrs.page);
  const target = useContext(SyncedSource)(title);
  const nodeId = typeof target === "object" ? target.nodeId : null;
  const [shown, setShown] = useState<Shown>("loading");
  const canvas = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    if (!nodeId) return;
    let live = true;
    setShown("loading");
    // A password stays in the file screen: the block only says why it cannot draw the page.
    const load = openPdf(rawFileSource(nodeId), () => live && setShown("locked"));
    load.promise.then(
      (doc) => live && setShown({ doc }),
      () => live && setShown((now) => (now === "locked" ? now : "failed")),
    );
    return () => {
      live = false;
      load.destroy();
    };
  }, [nodeId]);

  const doc = typeof shown === "object" ? shown.doc : null;
  const outOfRange = doc !== null && page > doc.numPages;
  const pages = doc?.numPages ?? 0;

  useEffect(() => {
    if (!doc || outOfRange) return;
    let live = true;
    let cancel = () => {};
    void doc.getPage(page).then((pdfPage) => {
      const target = canvas.current;
      if (!live || !target) return;
      // As wide as the text column, sharp on a dense screen.
      const ratio = window.devicePixelRatio || 1;
      const width = target.clientWidth || pdfPage.getViewport({ scale: CSS_UNITS }).width;
      const viewport = pdfPage.getViewport({ scale: (width / pdfPage.getViewport({ scale: 1 }).width) * ratio });
      target.width = Math.floor(viewport.width);
      target.height = Math.floor(viewport.height);
      const task = pdfPage.render({ canvas: target, viewport });
      cancel = () => task.cancel();
      // A newer page cancels this render; that rejection is expected.
      task.promise.catch(() => {});
    });
    return () => {
      live = false;
      cancel();
    };
  }, [doc, page, outOfRange]);

  if (node.attrs.choosing)
    return (
      <NodeViewWrapper contentEditable={false} data-pdf-page-view="">
        <Picker onPick={(picked, number) => updateAttributes({ title: picked, page: number, choosing: false })} />
      </NodeViewWrapper>
    );

  const error =
    typeof target !== "object"
      ? t(target === "missing" ? "editor.pdfPage.missing" : "editor.link.ambiguous")
      : outOfRange
        ? t("editor.pdfPage.outOfRange", { n: pages })
        : shown === "locked"
          ? t("file.password.locked")
          : shown === "failed"
            ? t("file.error.pdf")
            : null;
  const name = title.replace(/\.pdf$/i, "");
  const open = () => typeof target === "object" && navigate(`${target.href}?p=${page}`);

  return (
    <NodeViewWrapper contentEditable={false} data-pdf-page-view="">
      {error ? (
        <div className="pdf-page-desk">
          <p role="alert" className="m-0 text-13 text-err">
            {error}
          </p>
        </div>
      ) : (
        <button type="button" onClick={open} className="pdf-page-desk pdf-page-open" aria-label={title}>
          {doc ? (
            <canvas
              ref={canvas}
              role="img"
              aria-label={t("file.page.label", { page })}
              className="pdf-page-canvas"
            />
          ) : (
            <span className="text-13 text-text-3">{t("file.loading")}</span>
          )}
        </button>
      )}
      <div className="pdf-page-caption">
        <FileName title={name} ext={title.slice(name.length + 1)} />
        <span className="font-mono">· {t("editor.pdfPage.page", { n: page })}</span>
      </div>
    </NodeViewWrapper>
  );
}

/** For `BlockEditor`, as `PageLink` gets its view there; `PdfPage` goes after `RawInline`/`RawBlock`. */
export const PdfPageWithView = PdfPage.extend({
  addNodeView: () =>
    ReactNodeViewRenderer(PdfPageView, {
      // The editor would select the block on mousedown and swallow the click that opens the PDF and the picker's input.
      stopEvent: ({ event }) => event.target instanceof Element && event.target.closest("button, input") !== null,
    }),
});

/** Inserted with `insertPdfPage()`: the block asks for a PDF of the base and a page number. */
export const pdfPageKinds: BlockKind[] = [{ id: "pdfPage", group: "link" }];
