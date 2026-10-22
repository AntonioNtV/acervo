import type { PDFDocumentLoadingTask, PDFDocumentProxy } from "pdfjs-dist";

export type { PDFDocumentProxy };

/** `submit` hands a password to pdf.js, which decrypts in the browser; `incorrect` after a wrong one. */
export type OnPassword = (submit: (password: string) => void, incorrect: boolean) => void;

export type PdfLoad = { promise: Promise<PDFDocumentProxy>; destroy: () => void };

// pdf.js is loaded only when a PDF is opened, so the rest of the app does not carry it.
async function pdfjs() {
  const [lib, worker] = await Promise.all([import("pdfjs-dist"), import("pdfjs-dist/build/pdf.worker.min.mjs?url")]);
  lib.GlobalWorkerOptions.workerSrc = worker.default;
  return lib;
}

/** Opens the original file by range requests; without visible range headers pdf.js reads it whole. */
export function openPdf(url: string, onPassword: OnPassword): PdfLoad {
  let task: PDFDocumentLoadingTask | null = null;
  let destroyed = false;
  const promise = pdfjs().then((lib) => {
    if (destroyed) throw new lib.AbortException("destroyed");
    task = lib.getDocument({ url, disableAutoFetch: true, disableStream: true });
    task.onPassword = (submit: (password: string) => void, reason: number) =>
      onPassword(submit, reason === lib.PasswordResponses.INCORRECT_PASSWORD);
    return task.promise;
  });
  return {
    promise,
    destroy: () => {
      destroyed = true;
      void task?.destroy();
    },
  };
}
