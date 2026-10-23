import { useEffect, useRef, useState, type ReactNode } from "react";
import type { Outgoing } from "../../data/chat";
import { useSearch } from "../../data/tree";
import { useEditorSelection } from "../../editor/BlockEditor";
import { useI18n } from "../../i18n";
import { FileName } from "../../ui/FileName";
import { Icon } from "../../ui/Icon";
import { IconButton } from "../../ui/IconButton";
import { Input } from "../../ui/Input";
import { folderPath, splitExt } from "../../ui/names";

const SEARCH_DELAY_MS = 200;

export type PageRef = { id: string; title: string };

function Chip({ children, remove, label }: { children: ReactNode; remove: () => void; label: string }) {
  return (
    <span className="inline-flex h-6 max-w-full min-w-0 items-center gap-1.5 rounded-[6px] bg-subtle pr-1 pl-2 text-12 text-text-2">
      {children}
      <IconButton size="sm" aria-label={label} onClick={remove} className="size-[18px] text-text-3">
        <Icon name="close" size={12} />
      </IconButton>
    </span>
  );
}

/** `@`: a page of the base to keep as the message's context, found by title. */
function PagePicker({ kbId, onPick, onClose }: { kbId: string; onPick: (page: PageRef) => void; onClose: () => void }) {
  const { t } = useI18n();
  const [query, setQuery] = useState("");
  const [searched, setSearched] = useState("");
  const pages = (useSearch(kbId, searched).data ?? []).filter((hit) => hit.kind === "page");

  useEffect(() => {
    const timer = setTimeout(() => setSearched(query.trim()), SEARCH_DELAY_MS);
    return () => clearTimeout(timer);
  }, [query]);

  return (
    <div
      role="dialog"
      aria-label={t("chat.mention.title")}
      className="absolute right-0 bottom-full left-0 mb-1.5 flex flex-col gap-1 rounded-[8px] border border-line-2 bg-bg p-1.5"
      onKeyDown={(event) => event.key === "Escape" && onClose()}
    >
      <Input
        autoFocus
        aria-label={t("chat.mention.search")}
        placeholder={t("chat.mention.search")}
        value={query}
        onChange={(event) => setQuery(event.target.value)}
      />
      <ul className="m-0 flex max-h-[220px] list-none flex-col overflow-y-auto p-0">
        {pages.map((page) => (
          <li key={page.id}>
            <button
              type="button"
              onClick={() => onPick({ id: page.id, title: page.title })}
              className="flex min-h-8 w-full min-w-0 cursor-pointer items-center gap-2 rounded-[6px] border-0 bg-transparent px-2 text-left font-[inherit] text-13 text-text hover:bg-subtle"
            >
              <FileName title={page.title} ext="md" className="shrink-0 truncate" />
              <span className="min-w-0 truncate text-12 text-ghost">{folderPath(page.path, page.title)}</span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

/**
 * One box for everything: the open page and the selected text come along as removable chips, files are attached or
 * dropped, `@` points at another page. Enter sends, ⇧Enter breaks the line.
 */
export function Composer({
  kbId,
  openPage,
  files,
  setFiles,
  sending,
  onSend,
}: {
  kbId: string;
  openPage: PageRef | null;
  files: File[];
  setFiles: (files: File[]) => void;
  sending: boolean;
  onSend: (message: Outgoing) => Promise<unknown>;
}) {
  const { t } = useI18n();
  const selection = useEditorSelection();
  const [text, setText] = useState("");
  // A page pointed at with `@` holds while the same page stays open.
  const [picked, setPicked] = useState<{ page: PageRef; on: string | null } | null>(null);
  const [droppedPage, setDroppedPage] = useState<string | null>(null);
  const [droppedSelection, setDroppedSelection] = useState("");
  const [picking, setPicking] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const box = useRef<HTMLTextAreaElement>(null);

  const candidate = picked && picked.on === (openPage?.id ?? null) ? picked.page : openPage;
  const page = candidate && candidate.id !== droppedPage ? candidate : null;
  const quote = selection && selection !== droppedSelection ? selection : "";
  const canSend = !sending && (text.trim() !== "" || files.length > 0);

  const send = async () => {
    if (!canSend) return;
    try {
      await onSend({ text: text.trim(), files, pageId: page?.id ?? null, selection: quote || null });
      setText("");
      setFiles([]);
      if (quote) setDroppedSelection(quote);
    } catch {
      // The chat shows why; the text stays to send again.
    }
  };

  const pick = (chosen: PageRef) => {
    setPicked({ page: chosen, on: openPage?.id ?? null });
    setDroppedPage(null);
    setPicking(false);
    setText((current) => current.replace(/@$/, ""));
    box.current?.focus();
  };

  return (
    <div className="relative m-3 mt-0 flex flex-col gap-2 rounded-[12px] border border-line-2 py-2 pr-2 pl-2.5">
      {picking && <PagePicker kbId={kbId} onPick={pick} onClose={() => setPicking(false)} />}
      {(page || quote || files.length > 0) && (
        <div className="flex flex-wrap gap-1.5">
          {page && (
            <Chip label={t("chat.context.removePage")} remove={() => setDroppedPage(page.id)}>
              <Icon name="page" size={13} />
              <span className="truncate">{page.title}</span>
            </Chip>
          )}
          {quote && (
            <Chip label={t("chat.context.removeSelection")} remove={() => setDroppedSelection(quote)}>
              <span className="max-w-[200px] truncate">“{quote}”</span>
            </Chip>
          )}
          {files.map((file, i) => {
            const { name, ext } = splitExt(file.name);
            return (
              <Chip
                key={`${file.name}-${i}`}
                label={t("chat.context.removeFile", { name: file.name })}
                remove={() => setFiles(files.filter((_, j) => j !== i))}
              >
                <Icon name="file" size={13} />
                <FileName title={name} ext={ext} className="truncate" />
              </Chip>
            );
          })}
        </div>
      )}
      <label className="flex">
        <span className="sr-only">{t("chat.message")}</span>
        <textarea
          ref={box}
          rows={2}
          value={text}
          placeholder={t("chat.placeholder")}
          onChange={(event) => {
            const next = event.target.value;
            if (/(^|\s)@$/.test(next) && next.length > text.length) setPicking(true);
            setText(next);
          }}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
              event.preventDefault();
              void send();
            }
          }}
          className="flex-1 resize-none border-0 bg-transparent px-0.5 text-13 text-text outline-none placeholder:text-ghost"
        />
      </label>
      <div className="flex items-center justify-between">
        <span className="flex items-center gap-0.5">
          <IconButton aria-label={t("chat.attach")} onClick={() => input.current?.click()}>
            <Icon name="attach" size={15} />
          </IconButton>
          <input
            ref={input}
            type="file"
            multiple
            accept="application/pdf,.pdf"
            aria-label={t("chat.attachInput")}
            className="hidden"
            onChange={(event) => {
              setFiles([...files, ...Array.from(event.target.files ?? [])]);
              event.target.value = "";
            }}
          />
          <IconButton aria-label={t("chat.mention")} onClick={() => setPicking(!picking)} className="text-[14px] font-medium">
            @
          </IconButton>
          <span className="ml-1 text-12 text-text-3">{t("chat.shortcut")}</span>
        </span>
        <button
          type="button"
          aria-label={t("chat.send")}
          disabled={!canSend}
          onClick={() => void send()}
          className="inline-flex size-7 cursor-pointer items-center justify-center rounded-[7px] border-0 bg-ink text-on-ink disabled:cursor-default disabled:bg-muted disabled:text-text-3"
        >
          <Icon name="send" size={15} />
        </button>
      </div>
    </div>
  );
}
