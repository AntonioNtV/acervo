import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import type { NodeDetail } from "../api/client";
import { rawFileSource } from "../data/files";
import { useI18n } from "../i18n";
import { Button } from "../ui/Button";
import { FileHeader } from "../screens/file/FileHeader";
import { PasswordDialog } from "./Password";
import { openPdf, type PDFDocumentProxy } from "./pdfjs";

const ZOOMS = [0.5, 0.75, 1, 1.25, 1.5, 2];
// pdf.js scale 1 is 72 dpi; 100% means the page at its printed size on a 96 dpi screen.
const CSS_UNITS = 96 / 72;
// Browsers refuse bigger canvases (iOS Safari first); pdf.js's own viewer caps at the same `maxCanvasPixels`.
const MAX_CANVAS_PIXELS = 2 ** 24;

type Ask = { submit: (password: string) => void; incorrect: boolean };
type Box = { left: number; top: number; width: number; height: number };

/** `?hl=x0,y0,x1,y1`: a cited block's box in PDF points, from the page's top left (as the index reads it). */
function boxOf(hl: string | null): number[] | null {
  const box = hl?.split(",").map(Number);
  return box?.length === 4 && box.every(Number.isFinite) ? box : null;
}

function Chevron({ d }: { d: string }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="size-[15px] fill-none stroke-current stroke-[1.5]">
      <path d={d} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function PdfViewer({ node }: { node: NodeDetail }) {
  const { t } = useI18n();
  const [params, setParams] = useSearchParams();
  const [doc, setDoc] = useState<PDFDocumentProxy | null>(null);
  const [failed, setFailed] = useState(false);
  const [ask, setAsk] = useState<Ask | null>(null);
  const [asking, setAsking] = useState(false);
  const [zoom, setZoom] = useState(2);
  const [mark, setMark] = useState<Box | null>(null);
  const canvas = useRef<HTMLCanvasElement>(null);

  const sha = node.file?.sha256;
  const total = doc?.numPages ?? node.file?.pages ?? 1;
  const page = Math.min(Math.max(Math.trunc(Number(params.get("p"))) || 1, 1), total);
  const scale = ZOOMS[zoom] ?? 1;
  const hl = params.get("hl");

  useEffect(() => {
    let live = true;
    setDoc(null);
    setFailed(false);
    setAsk(null);
    setAsking(false);
    const load = openPdf(rawFileSource(node.id), (submit, incorrect) => {
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
  }, [node.id, sha]);

  useEffect(() => {
    if (!doc) return;
    let live = true;
    let cancel = () => {};
    setMark(null);
    void doc.getPage(page).then((pdfPage) => {
      const target = canvas.current;
      if (!live || !target) return;
      const css = pdfPage.getViewport({ scale: scale * CSS_UNITS });
      const ratio = Math.min(window.devicePixelRatio || 1, Math.sqrt(MAX_CANVAS_PIXELS / (css.width * css.height)));
      const viewport = pdfPage.getViewport({ scale: scale * CSS_UNITS * ratio });
      target.width = Math.floor(viewport.width);
      target.height = Math.floor(viewport.height);
      target.style.width = `${Math.floor(viewport.width / ratio)}px`;
      const box = boxOf(hl);
      if (box) {
        const [x0 = 0, y0 = 0, x1 = 0, y1 = 0] = box;
        // pdf.js wants user space (origin at the bottom left of the crop box); it then applies zoom and rotation.
        const [left = 0, , , top = 0] = pdfPage.view;
        const [a = 0, b = 0] = css.convertToViewportPoint(left + x0, top - y0) as number[];
        const [c = 0, d = 0] = css.convertToViewportPoint(left + x1, top - y1) as number[];
        setMark({ left: Math.min(a, c), top: Math.min(b, d), width: Math.abs(c - a), height: Math.abs(d - b) });
      }
      const task = pdfPage.render({ canvas: target, viewport });
      cancel = () => task.cancel();
      // A newer page or zoom cancels this render; that rejection is expected.
      task.promise.catch(() => {});
    });
    return () => {
      live = false;
      cancel();
    };
  }, [doc, page, scale, hl]);

  function goTo(next: number) {
    setParams(
      (current) => {
        current.set("p", String(Math.min(Math.max(next, 1), total)));
        current.delete("hl");
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
  return (
    <>
      <FileHeader node={node} detail={doc || node.file?.pages ? pages : undefined}>
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
      </FileHeader>
      <div className="flex min-h-0 flex-1 items-start justify-center overflow-auto px-6 py-8">
        {doc ? (
          <div className="relative">
            <canvas
              ref={canvas}
              role="img"
              aria-label={t("file.page.label", { page })}
              className="block max-w-none bg-bg shadow-[0_0_0_1px_var(--line-2)]"
            />
            {mark && (
              <mark
                aria-hidden="true"
                style={mark}
                className="pointer-events-none absolute rounded-[2px] bg-warn/25 mix-blend-multiply"
              />
            )}
          </div>
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
