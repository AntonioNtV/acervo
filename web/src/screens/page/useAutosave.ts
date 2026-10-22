import { useCallback, useEffect, useRef, useState } from "react";
import { leavePage, useSavePageText, type StaleText } from "../../data/pages";
import { ApiError } from "../../data/request";

const SAVE_DELAY_MS = 1000;

export type SaveStatus = "saving" | "saved" | "failed";

type Opened = { markdown: string; key: number };

/**
 * The page's working text, saved a second after typing stops with the revision it was typed on. `opened` is the text
 * the editor opens with; its `key` changes when another text replaces it (a refused save, a restore).
 */
export function useAutosave(nodeId: string, page: { markdown: string; revision: number }) {
  const [opened, setOpened] = useState<Opened>({ markdown: page.markdown, key: 0 });
  const [status, setStatus] = useState<SaveStatus>("saved");
  const [reloaded, setReloaded] = useState(false);
  const { mutateAsync: save } = useSavePageText(nodeId);
  const state = useRef({
    text: page.markdown,
    saved: page.markdown,
    revision: page.revision,
    inFlight: false,
    timer: undefined as ReturnType<typeof setTimeout> | undefined,
  });

  /** Replaces the text everywhere: the editor reopens on it and the next save starts from `revision`. */
  const replace = useCallback((markdown: string, revision: number) => {
    const s = state.current;
    clearTimeout(s.timer);
    Object.assign(s, { text: markdown, saved: markdown, revision });
    setOpened((current) => ({ markdown, key: current.key + 1 }));
  }, []);

  const flush = useCallback(
    async (keepalive = false): Promise<void> => {
      const s = state.current;
      clearTimeout(s.timer);
      if (s.inFlight || s.text === s.saved) return;
      s.inFlight = true;
      setStatus("saving");
      const markdown = s.text;
      try {
        s.revision = (await save({ markdown, revision: s.revision, keepalive })).revision;
        s.saved = markdown;
        setStatus("saved");
      } catch (error) {
        s.inFlight = false;
        if (error instanceof ApiError && error.code === "stale_page") {
          const newest = error.details as StaleText;
          replace(newest.markdown, newest.revision);
          setReloaded(true);
          setStatus("saved");
        } else {
          setStatus("failed");
        }
        return;
      }
      s.inFlight = false;
      // Typed while the save was on its way.
      if (s.text !== s.saved) await flush(keepalive);
    },
    [save, replace],
  );

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

  // Leaving the page or hiding the tab saves what is pending and cuts the working text as a version.
  useEffect(() => {
    const leave = () => void flush(true).finally(() => leavePage(nodeId));
    const onVisibility = () => {
      if (document.visibilityState === "hidden") leave();
    };
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      document.removeEventListener("visibilitychange", onVisibility);
      leave();
    };
  }, [nodeId, flush]);

  return { opened, status, reloaded, dismissReloaded: () => setReloaded(false), change, flush, replace };
}
