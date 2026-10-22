import { useCallback, useEffect, useRef, useState } from "react";
import { leavePage, useSavePageText, type StaleText } from "../../data/pages";
import { ApiError } from "../../data/request";

const SAVE_DELAY_MS = 1000;
// Browsers refuse a keepalive request whose body is over 64 KB.
const KEEPALIVE_MAX_BYTES = 60_000;

export type SaveStatus = "saving" | "saved" | "failed";

type Opened = { markdown: string; key: number };

/**
 * The page's working text, saved a second after typing stops with the revision it was typed on. `opened` is the text
 * the editor opens with; its `key` changes when another text replaces it (a refused save, a restore, a newer revision).
 */
export function useAutosave(nodeId: string, page: { markdown: string; revision: number }) {
  const [opened, setOpened] = useState<Opened>({ markdown: page.markdown, key: 0 });
  const [status, setStatus] = useState<SaveStatus>("saved");
  const [reloaded, setReloaded] = useState(false);
  const save = useSavePageText(nodeId);
  const state = useRef({
    text: page.markdown,
    saved: page.markdown,
    revision: page.revision,
    /** The save on its way; it never rejects. */
    inFlight: null as Promise<void> | null,
    timer: undefined as ReturnType<typeof setTimeout> | undefined,
  });

  /** Replaces the text everywhere: the editor reopens on it and the next save starts from `revision`. */
  const replace = useCallback((markdown: string, revision: number) => {
    const s = state.current;
    clearTimeout(s.timer);
    Object.assign(s, { text: markdown, saved: markdown, revision });
    setOpened((current) => ({ markdown, key: current.key + 1 }));
  }, []);

  /** Sends `markdown` typed on `revision`; resolves once its answer is handled. */
  const send = useCallback(
    (markdown: string, revision: number, keepalive: boolean): Promise<void> => {
      const s = state.current;
      return save({ markdown, revision }, keepalive).then(
        (saved) => {
          s.revision = saved.revision;
          s.saved = markdown;
          setStatus(s.text === markdown ? "saved" : "saving");
        },
        (error: unknown) => {
          if (!(error instanceof ApiError && error.code === "stale_page")) return setStatus("failed");
          // The API keeps a refused text as a version: what was typed while it was on its way is kept the same way,
          // until nothing new was typed during a resend.
          if (s.text !== markdown) return send(s.text, revision, false);
          const newest = error.details as StaleText;
          replace(newest.markdown, newest.revision);
          setReloaded(true);
          setStatus("saved");
        },
      );
    },
    [save, replace],
  );

  /** Sends the current text now, as the save on its way. */
  const start = useCallback(
    (keepalive: boolean): Promise<void> => {
      const s = state.current;
      setStatus("saving");
      const landed: Promise<void> = send(s.text, s.revision, keepalive).finally(() => {
        if (s.inFlight === landed) s.inFlight = null;
      });
      s.inFlight = landed;
      return landed;
    },
    [send],
  );

  /** Waits for the save on its way, then sends what is still unsaved; resolves once that lands too. */
  const flush = useCallback(async (): Promise<void> => {
    const s = state.current;
    clearTimeout(s.timer);
    while (s.inFlight) await s.inFlight;
    if (s.text !== s.saved) await start(false);
  }, [start]);

  const change = useCallback(
    (markdown: string) => {
      const s = state.current;
      s.text = markdown;
      setStatus("saving");
      clearTimeout(s.timer);
      s.timer = setTimeout(() => void flush(), SAVE_DELAY_MS);
    },
    [flush],
  );

  // A newer text from the API (a rename fixed a link in it, another tab restored a version) replaces an idle editor.
  useEffect(() => {
    const s = state.current;
    if (page.revision > s.revision && s.text === s.saved && !s.inFlight) replace(page.markdown, page.revision);
  }, [page.revision, page.markdown, replace]);

  // Leaving the page or hiding the tab saves what is pending and cuts the working text as a version.
  useEffect(() => {
    const onVisibility = () => {
      if (document.visibilityState !== "hidden") return;
      const s = state.current;
      clearTimeout(s.timer);
      // A closing tab never runs what waits for an answer, not even a save on its way: the text and the leave go out
      // now, in that order. If the save on its way lands first, this one is refused and kept as a version.
      if (s.text !== s.saved) {
        const body = new Blob([JSON.stringify({ markdown: s.text, revision: s.revision })]);
        void start(body.size < KEEPALIVE_MAX_BYTES);
      }
      void leavePage(nodeId);
    };
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      document.removeEventListener("visibilitychange", onVisibility);
      void flush().then(() => leavePage(nodeId));
    };
  }, [nodeId, flush, start]);

  return { opened, status, reloaded, dismissReloaded: () => setReloaded(false), change, flush, replace };
}
