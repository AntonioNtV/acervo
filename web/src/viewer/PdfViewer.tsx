import { useEffect, useRef, useState, type ReactNode } from "react";
import { useSearchParams } from "react-router-dom";
import type { NodeDetail } from "../api/client";
import { rawFileSource } from "../data/files";
import { useI18n } from "../i18n";
import { Button } from "../ui/Button";
import { FileHeader } from "../screens/file/FileHeader";
import { PasswordDialog } from "./Password";
import { openPdf, type PdfSource, type PDFDocumentProxy } from "./pdfjs";

const ZOOMS = [0.5, 0.75, 1, 1.25, 1.5, 2];
// pdf.js scale 1 is 72 dpi; 100% means the page at its printed size on a 96 dpi screen.
const CSS_UNITS = 96 / 72;
// Browsers refuse bigger canvases (iOS Safari first); pdf.js's own viewer caps at the same `maxCanvasPixels`.
const MAX_CANVAS_PIXELS = 2 ** 24;

type Ask = { submit: (password: string) => void; incorrect: boolean };

function Chevron({ d }: { d: string }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="size-[15px] fill-none stroke-current stroke-[1.5]">
      <path d={d} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

type Props =
  | { node: NodeDetail }
  /** A PDF outside the tree (a page's attachment): read only, its bar shows `title` and ends with `children`. */
  | { source: PdfSource; title: string; children?: ReactNode };

export function PdfViewer(props: Props) {
  const { t } = useI18n();
  const node = "node" in props ? props.node : null;
  const attached = "source" in props ? props : null;
  const [params, setParams] = useSearchParams();
  // Only a file of the tree keeps its page in the address.
  const [ownPage, setOwnPage] = useState(1);
  const [doc, setDoc] = useState<PDFDocumentProxy | null>(null);
  const [failed, setFailed] = useState(false);
  const [ask, setAsk] = useState<Ask | null>(null);
  const [asking, setAsking] = useState(false);
  const [zoom, setZoom] = useState(2);
  const canvas = useRef<HTMLCanvasElement>(null);

  const sha = node?.file?.sha256;
  const nodeId = node?.id;
  const url = attached?.source.url;
  const headers = attached?.source.httpHeaders;
  const total = doc?.numPages ?? node?.file?.pages ?? 1;
  const asked = node ? Math.trunc(Number(params.get("p"))) || 1 : ownPage;
  const page = Math.min(Math.max(asked, 1), total);
  const scale = ZOOMS[zoom] ?? 1;

  useEffect(() => {
    let live = true;
    setDoc(null);
    setFailed(false);
    setAsk(null);
    setAsking(false);
    const source = nodeId ? rawFileSource(nodeId) : { url: url!, httpHeaders: headers! };
    const load = openPdf(source, (submit, incorrect) => {
      if (!live) return;
      setAsk({ submit, incorrect });
      setAsking(true);
    });
    load.promise.then(
      (opened) => live && setDoc(opened),
      () => live && setFailed(true),
    );
    return () => {
      live = false;
      load.destroy();
    };
  }, [nodeId, sha, url, headers]);

  useEffect(() => {
    if (!doc) return;
    let live = true;
    let cancel = () => {};
    void doc.getPage(page).then((pdfPage) => {
      const target = canvas.current;
      if (!live || !target) return;
      const css = pdfPage.getViewport({ scale: scale * CSS_UNITS });
      const ratio = Math.min(window.devicePixelRatio || 1, Math.sqrt(MAX_CANVAS_PIXELS / (css.width * css.height)));
      const viewport = pdfPage.getViewport({ scale: scale * CSS_UNITS * ratio });
      target.width = Math.floor(viewport.width);
      target.height = Math.floor(viewport.height);
      target.style.width = `${Math.floor(viewport.width / ratio)}px`;
      const task = pdfPage.render({ canvas: target, viewport });
      cancel = () => task.cancel();
      // A newer page or zoom cancels this render; that rejection is expected.
      task.promise.catch(() => {});
    });
    return () => {
      live = false;
      cancel();
    };
  }, [doc, page, scale]);

  function goTo(next: number) {
    if (!node) return setOwnPage(Math.min(Math.max(next, 1), total));
    setParams(
      (current) => {
        current.set("p", String(Math.min(Math.max(next, 1), total)));
        return current;
      },
      { replace: true },
    );
  }

  function submitPassword(password: string) {
    ask?.submit(password);
    setAsking(false);
  }

  const pages = t(total === 1 ? "file.pages.one" : "file.pages.other", { n: total });
  const controls = (
    <>
      <Button
        variant="quiet"
        size="sm"
        icon
        aria-label={t("file.prev")}
        disabled={!doc || page <= 1}
        onClick={() => goTo(page - 1)}
      >
        <Chevron d="m15 6-6 6 6 6" />
      </Button>
      <PageInput page={page} total={total} disabled={!doc} onCommit={goTo} />
      <Button
        variant="quiet"
        size="sm"
        icon
        aria-label={t("file.next")}
        disabled={!doc || page >= total}
        onClick={() => goTo(page + 1)}
      >
        <Chevron d="m9 6 6 6-6 6" />
      </Button>
      <span aria-hidden="true" className="mx-1.5 h-4 w-px bg-line-2" />
      <Button
        variant="quiet"
        size="sm"
        icon
        aria-label={t("file.zoom.out")}
        disabled={zoom === 0}
        onClick={() => setZoom(zoom - 1)}
      >
        <Chevron d="M6 12h12" />
      </Button>
      <span className="w-10 text-center text-12 text-text-2 tabular-nums">{Math.round(scale * 100)}%</span>
      <Button
        variant="quiet"
        size="sm"
        icon
        aria-label={t("file.zoom.in")}
        disabled={zoom === ZOOMS.length - 1}
        onClick={() => setZoom(zoom + 1)}
      >
        <Chevron d="M6 12h12M12 6v12" />
      </Button>
    </>
  );
  return (
    <>
      {node ? (
        <FileHeader node={node} detail={doc || node.file?.pages ? pages : undefined}>
          {controls}
        </FileHeader>
      ) : (
        <div className="flex h-11 shrink-0 items-center gap-3 bg-bg pr-2.5 pl-3.5">
          <span className="min-w-0 flex-1 truncate text-13">{attached?.title}</span>
          <div className="flex items-center">{controls}</div>
          {attached?.children}
        </div>
      )}
      <div className="flex min-h-0 flex-1 items-start justify-center overflow-auto px-6 py-8">
        {doc ? (
          <canvas
            ref={canvas}
            role="img"
            aria-label={t("file.page.label", { page })}
            className="block max-w-none bg-bg shadow-[0_0_0_1px_var(--line-2)]"
          />
        ) : failed ? (
          <p className="m-0 text-err">{t("file.error.pdf")}</p>
        ) : ask && !asking ? (
          <div className="flex flex-col items-center gap-3">
            <p className="m-0 text-text-2">{t("file.password.locked")}</p>
            <Button onClick={() => setAsking(true)}>{t("file.password.enter")}</Button>
          </div>
        ) : (
          <p className="m-0 text-text-3">{t("file.loading")}</p>
        )}
      </div>
      <PasswordDialog
        open={asking}
        incorrect={ask?.incorrect ?? false}
        onSubmit={submitPassword}
        onCancel={() => setAsking(false)}
      />
    </>
  );
}

function PageInput({
  page,
  total,
  disabled,
  onCommit,
}: {
  page: number;
  total: number;
  disabled: boolean;
  onCommit: (page: number) => void;
}) {
  const { t } = useI18n();
  const [draft, setDraft] = useState(String(page));
  useEffect(() => setDraft(String(page)), [page]);

  function commit() {
    const next = Number(draft);
    if (Number.isInteger(next) && next !== page) onCommit(next);
    else setDraft(String(page));
  }

  return (
    <span className="flex items-center gap-1 px-1 text-12 text-text-2 tabular-nums">
      <input
        aria-label={t("file.page")}
        inputMode="numeric"
        disabled={disabled}
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
        onBlur={commit}
        onKeyDown={(event) => event.key === "Enter" && commit()}
        className="h-[26px] w-9 rounded-[6px] border border-line-2 bg-bg text-center text-12 text-text focus:border-ink focus:outline-none"
      />
      <span>{t("file.page.of", { total })}</span>
    </span>
  );
}
