import { useEffect, useRef, useState } from "react";
import type { NodeDetail, StalePage } from "../../api/client";
import { useDiscardDraft, usePutDraft, useSavePage } from "../../data/pages";
import { ApiError } from "../../data/request";

type Page = NonNullable<NodeDetail["page"]>;
type Edit = { text: string; base: string };

const DRAFT_DELAY_MS = 2000;

/**
 * The text being edited, its autosaved draft, "Concluir" and the stale-save conflict. While `paused` (a draft found
 * on opening is not yet continued or discarded) nothing is saved on its own, so that draft is never overwritten.
 */
export function useEditing(nodeId: string, page: Page, paused: boolean) {
  const [edit, setEdit] = useState<Edit | null>(null);
  const [savedAt, setSavedAt] = useState<number | null>(null);
  const [conflict, setConflict] = useState<StalePage | null>(null);
  const save = useSavePage(nodeId);
  const { mutate: putDraft } = usePutDraft(nodeId);
  const discardDraft = useDiscardDraft(nodeId);
  const dirty = edit !== null && edit.text !== page.markdown;

  useEffect(() => {
    if (!edit || !dirty || paused) return;
    const timer = setTimeout(
      () => putDraft({ markdown: edit.text, base_version_id: edit.base }, { onSuccess: () => setSavedAt(Date.now()) }),
      DRAFT_DELAY_MS,
    );
    return () => clearTimeout(timer);
  }, [edit, dirty, paused, putDraft]);

  // Leaving the page with changes saves them; a refused save keeps them as the draft.
  const latest = useRef({ edit, dirty, paused });
  latest.current = { edit, dirty, paused };
  const { mutateAsync: saveAsync } = save;
  useEffect(
    () => () => {
      const { edit, dirty, paused } = latest.current;
      if (!edit || !dirty || paused) return;
      saveAsync({ markdown: edit.text, base_version_id: edit.base }).catch(() =>
        putDraft({ markdown: edit.text, base_version_id: edit.base }),
      );
    },
    [saveAsync, putDraft],
  );

  function reset() {
    setEdit(null);
    setSavedAt(null);
    setConflict(null);
  }

  function conclude(onDone: () => void, force = false) {
    if (!edit) return onDone();
    const base = force && conflict ? conflict.current_version_id : edit.base;
    save.mutate(
      { markdown: edit.text, base_version_id: base, force },
      {
        onSuccess: () => {
          reset();
          onDone();
        },
        onError: (error) => {
          if (error instanceof ApiError && error.code === "stale_page") setConflict(error.details as StalePage);
        },
      },
    );
  }

  function discard() {
    discardDraft.mutate();
    reset();
  }

  /** Drops the stored draft but keeps what is being typed now. */
  function discardStoredDraft() {
    discardDraft.mutate();
  }

  return {
    text: edit?.text ?? page.markdown,
    base: edit?.base ?? page.version_id,
    editing: edit !== null,
    dirty,
    savedAt,
    conflict,
    saveFailed: save.isError && conflict === null,
    saving: save.isPending,
    change: (text: string) => setEdit((current) => ({ text, base: current?.base ?? page.version_id })),
    resume: (draft: NonNullable<Page["draft"]>) => setEdit({ text: draft.markdown, base: draft.base_version_id }),
    conclude,
    discard,
    discardStoredDraft,
    dismissConflict: () => setConflict(null),
  };
}
