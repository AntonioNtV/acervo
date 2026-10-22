import { useEffect, useRef, useState } from "react";
import {
  ApiError,
  useDiscardDraft,
  usePutDraft,
  useSavePage,
  type NodeDetail,
  type StalePage,
} from "../../api/queries";

type Page = NonNullable<NodeDetail["page"]>;
type Edit = { text: string; base: string };

const DRAFT_DELAY_MS = 2000;

/** The text being edited, its autosaved draft, "Concluir" and the stale-save conflict. */
export function useEditing(nodeId: string, page: Page) {
  const [edit, setEdit] = useState<Edit | null>(null);
  const [savedAt, setSavedAt] = useState<number | null>(null);
  const [conflict, setConflict] = useState<StalePage | null>(null);
  const save = useSavePage(nodeId);
  const { mutate: putDraft } = usePutDraft(nodeId);
  const discardDraft = useDiscardDraft(nodeId);
  const dirty = edit !== null && edit.text !== page.markdown;

  useEffect(() => {
    if (!edit || !dirty) return;
    const timer = setTimeout(
      () => putDraft({ markdown: edit.text, base_version_id: edit.base }, { onSuccess: () => setSavedAt(Date.now()) }),
      DRAFT_DELAY_MS,
    );
    return () => clearTimeout(timer);
  }, [edit, dirty, putDraft]);

  // Leaving the page with changes saves them; a refused save keeps them as the draft.
  const latest = useRef({ edit, dirty });
  latest.current = { edit, dirty };
  const { mutateAsync: saveAsync } = save;
  useEffect(
    () => () => {
      const { edit, dirty } = latest.current;
      if (!edit || !dirty) return;
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
          if (error instanceof ApiError && error.status === 409) setConflict(error.body.detail as StalePage);
        },
      },
    );
  }

  function discard() {
    discardDraft.mutate();
    reset();
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
    dismissConflict: () => setConflict(null),
  };
}
