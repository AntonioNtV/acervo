import { useState, type ReactNode } from "react";
import { useErrorText } from "../../app/errors";
import { useRedo } from "../../data/chat";
import {
  REJECT_REASONS,
  useAcceptProposal,
  useEditProposal,
  useOtherPlace,
  useRejectProposal,
  useLatestProposal,
  useUndoProposal,
  type Payload,
  type Proposal,
  type ProposalSummary,
} from "../../data/proposals";
import { useI18n } from "../../i18n";
import { Button } from "../../ui/Button";
import { Dot } from "../../ui/Dot";
import { Input } from "../../ui/Input";
import { cx } from "../../ui/cx";
import { formatSize } from "../file/format";
import { useFollow } from "./follow";
import { FolderPicker, type Place } from "./FolderPicker";
import { isUnplaced, lastPart, payloadOf, probability, spaced, whereOf } from "./where";

type AnyProposal = Proposal | ProposalSummary;

const EDITABLE = ["append", "edit", "create_page", "save_pdf", "rename"];

const textareaClass =
  "w-full resize-y rounded-[7px] border border-line-2 bg-bg px-2.5 py-1.5 font-mono text-12 text-text focus:border-ink focus:shadow-[0_0_0_3px_var(--accent-soft)] focus:outline-none";

function Head({ children, where }: { children: ReactNode; where: string }) {
  return (
    <div className="flex flex-col gap-0.5 border-b border-line px-3 py-[9px]">
      <span className="font-medium">{children}</span>
      <span className="font-mono text-12 break-words text-text-3">{where}</span>
    </div>
  );
}

function Foot({ children }: { children: ReactNode }) {
  return <div className="flex flex-wrap items-center gap-1 px-2 py-[7px]">{children}</div>;
}

function Columns({ left, right }: { left: [string, ReactNode]; right: [string, ReactNode] }) {
  return (
    <div className="grid grid-cols-2 border-b border-line">
      {[left, right].map(([label, value], i) => (
        <div key={label} className={cx("flex min-w-0 flex-col gap-[3px] px-3 py-[9px] break-words", i === 1 && "border-l border-line")}>
          <span className="text-12 text-text-3">{label}</span>
          <span className="whitespace-pre-line">{value}</span>
        </div>
      ))}
    </div>
  );
}

type Line = { op: "add" | "del" | "same"; text: string };

function Diff({ lines }: { lines: Line[] }) {
  return (
    <div className="border-b border-line py-1.5 font-mono text-12">
      {lines.map((line, i) => (
        <span
          key={i}
          className={cx(
            "block px-3 whitespace-pre-wrap",
            line.op === "add" && "bg-add",
            line.op === "del" && "bg-del",
            line.op === "same" && "text-text-3",
          )}
        >
          {line.op === "add" ? "+ " : line.op === "del" ? "- " : ""}
          {line.text}
        </span>
      ))}
    </div>
  );
}

/** The change itself, rendered from the payload: never computed in the browser. */
function Body({ proposal, payload }: { proposal: AnyProposal; payload: Payload }) {
  const { t, lang } = useI18n();
  switch (payload.kind) {
    case "append":
    case "edit": {
      const lines: Line[] = payload.heading ? [{ op: "same", text: `## ${payload.heading}` }] : [];
      if (payload.line) lines.push({ op: payload.op === "replace" ? "del" : "same", text: payload.line });
      lines.push(...payload.lines.map((text) => ({ op: "add" as const, text })));
      return <Diff lines={lines} />;
    }
    case "create_page":
      return <Diff lines={payload.markdown.replace(/\n+$/, "").split("\n").map((text) => ({ op: "add", text }))} />;
    case "conflict":
      return (
        <Columns
          left={[t("chat.conflict.current"), payload.current || t("chat.conflict.noLine")]}
          right={[t("chat.conflict.new"), payload.new]}
        />
      );
    case "save_pdf":
      return proposal.staged ? (
        <div className="border-b border-line px-3 py-[9px] text-12 text-text-2">
          {t("chat.pdf.arriving", { name: proposal.staged.name, size: formatSize(proposal.staged.size, lang) })}
        </div>
      ) : null;
    case "replace_pdf":
      return (
        <Columns
          left={[t("chat.pdf.today"), <span className="font-mono text-12">{lastPart(payload.path)}</span>]}
          right={[t("chat.pdf.incoming"), <span className="font-mono text-12">{proposal.staged?.name ?? ""}</span>]}
        />
      );
    case "move":
      return (
        <Columns
          left={[t("chat.from"), <span className="font-mono text-12">{spaced(payload.from_path)}</span>]}
          right={[t("chat.to"), <span className="font-mono text-12">{spaced(payload.to_path) || t("chat.root")}</span>]}
        />
      );
    case "rename":
      return (
        <Columns
          left={[t("chat.from"), lastPart(payload.path)]}
          right={[t("chat.to"), payload.title]}
        />
      );
    case "undo":
      return <div className="border-b border-line px-3 py-[9px] text-12 text-text-2">{t("chat.undo.text")}</div>;
  }
}

/** The person's version of the payload, of the same kind. */
function EditForm({ payload, busy, onSave, onCancel }: { payload: Payload; busy: boolean; onSave: (next: Payload) => void; onCancel: () => void }) {
  const { t } = useI18n();
  const [draft, setDraft] = useState(payload);
  const field = (label: string, value: string, set: (value: string) => void) => (
    <Input aria-label={label} value={value} onChange={(event) => set(event.target.value)} />
  );
  return (
    <form
      className="flex flex-col gap-2 border-b border-line px-3 py-[9px]"
      onSubmit={(event) => {
        event.preventDefault();
        onSave(draft);
      }}
    >
      {(draft.kind === "append" || draft.kind === "edit") && (
        <textarea
          aria-label={t("chat.edit.lines")}
          rows={Math.max(2, draft.lines.length)}
          className={textareaClass}
          value={draft.lines.join("\n")}
          onChange={(event) => setDraft({ ...draft, lines: event.target.value.split("\n") })}
        />
      )}
      {draft.kind === "create_page" && (
        <>
          {field(t("chat.edit.title"), draft.title, (title) => setDraft({ ...draft, title }))}
          <textarea
            aria-label={t("chat.edit.text")}
            rows={6}
            className={textareaClass}
            value={draft.markdown}
            onChange={(event) => setDraft({ ...draft, markdown: event.target.value })}
          />
        </>
      )}
      {draft.kind === "save_pdf" && field(t("chat.edit.name"), draft.name, (name) => setDraft({ ...draft, name }))}
      {draft.kind === "rename" && field(t("chat.edit.title"), draft.title, (title) => setDraft({ ...draft, title }))}
      <span className="flex gap-1">
        <Button type="submit" variant="ink" size="sm" disabled={busy}>
          {t("chat.edit.save")}
        </Button>
        <Button size="sm" variant="quiet" onClick={onCancel}>
          {t("chat.cancel")}
        </Button>
      </span>
    </form>
  );
}

/** A proposal in the thread: what it does and where (in mono) before its buttons, then its state once decided. */
export function ProposalCard({ proposal: given, agentName }: { proposal: AnyProposal; agentName?: string }) {
  const { t, lang } = useI18n();
  const proposal = useLatestProposal(given);
  const errorText = useErrorText();
  const [mode, setMode] = useState<"idle" | "reject" | "edit" | "pick" | "left">("idle");
  const accept = useAcceptProposal();
  const reject = useRejectProposal();
  const edit = useEditProposal();
  const otherPlace = useOtherPlace();
  const undo = useUndoProposal();
  const redo = useRedo();
  const follow = useFollow();
  const actions = [accept, reject, edit, otherPlace, undo, redo];
  const busy = actions.some((action) => action.isPending);
  const failed = actions.find((action) => action.error)?.error;

  const payload = payloadOf(proposal);
  const open = proposal.status === "pending";
  const unplaced = open && isUnplaced(proposal);
  const id = proposal.id;

  const reset = () => actions.forEach((action) => action.reset());
  const place = ({ nodeId, path }: Place) => {
    setMode("idle");
    if (payload.kind === "create_page" || payload.kind === "save_pdf")
      edit.mutate({ id, input: { ...payload, parent_id: nodeId, parent_path: path } });
  };

  const kindLabel = t(`chat.kind.${proposal.kind}`);
  const head =
    payload.kind === "conflict" ? (
      <Dot tone="err">
        <span className="text-13 text-text">{kindLabel}</span>
      </Dot>
    ) : payload.kind === "replace_pdf" ? (
      <Dot tone="warn">
        <span className="text-13 text-text">{t("chat.pdf.newVersionOf", { name: lastPart(payload.path) })}</span>
      </Dot>
    ) : (
      kindLabel
    );

  let foot: ReactNode;
  if (!open) {
    foot = (
      <Foot>
        {proposal.status === "applied" && (
          <>
            <Dot tone="ok">{t(proposal.accepted_by === "auto" ? "chat.status.auto" : "chat.status.applied")}</Dot>
            {proposal.kind !== "undo" && !undo.data && (
              <Button size="sm" variant="quiet" className="ml-auto" disabled={busy} onClick={() => undo.mutate({ id, input: undefined })}>
                {t("chat.undo")}
              </Button>
            )}
          </>
        )}
        {proposal.status === "stale" && (
          <>
            <Dot tone="warn">{t("chat.status.stale")}</Dot>
            <Button
              size="sm"
              className="ml-auto"
              disabled={busy}
              onClick={() => redo.mutate(id, { onSuccess: (reply) => follow(reply.id) })}
            >
              {t("chat.redo")}
            </Button>
          </>
        )}
        {proposal.status === "rejected" && (
          <Dot>
            {proposal.reject_reason
              ? t("chat.status.rejectedWhy", { reason: t(`chat.reason.${proposal.reject_reason}`) })
              : t("chat.status.rejected")}
          </Dot>
        )}
      </Foot>
    );
  } else if (mode === "reject") {
    foot = (
      <Foot>
        <span className="px-1 text-12 text-text-3">{t("chat.reject.why")}</span>
        {REJECT_REASONS.map((reason) => (
          <Button key={reason} size="sm" disabled={busy} onClick={() => reject.mutate({ id, input: reason })}>
            {t(`chat.reason.${reason}`)}
          </Button>
        ))}
        <Button size="sm" variant="quiet" onClick={() => setMode("idle")}>
          {t("chat.cancel")}
        </Button>
      </Foot>
    );
  } else if (mode === "edit") {
    foot = null;
  } else if (mode === "left") {
    foot = (
      <Foot>
        <span className="px-1 text-12 text-text-3">{t("chat.unplaced.left")}</span>
        <Button size="sm" variant="quiet" className="ml-auto" onClick={() => setMode("idle")}>
          {t("chat.unplaced.chooseNow")}
        </Button>
      </Foot>
    );
  } else if (unplaced) {
    foot = (
      <Foot>
        <Button size="sm" disabled={busy} onClick={() => setMode("pick")}>
          {t("chat.unplaced.other")}
        </Button>
        <Button size="sm" variant="quiet" className="ml-auto" onClick={() => setMode("left")}>
          {t("chat.unplaced.leave")}
        </Button>
      </Foot>
    );
  } else if (payload.kind === "conflict") {
    const both = { ...payload, new: [payload.current, payload.new, `_${t("chat.conflict.note")}_`].filter(Boolean).join("\n") };
    foot = (
      <Foot>
        <Button size="sm" variant="ink" disabled={busy} onClick={() => accept.mutate({ id, input: undefined })}>
          {t("chat.conflict.useNew")}
        </Button>
        <Button size="sm" disabled={busy} onClick={() => reject.mutate({ id, input: "wrong_info" })}>
          {t("chat.conflict.keep")}
        </Button>
        <Button size="sm" variant="quiet" disabled={busy} onClick={() => edit.mutate({ id, input: both }, { onSuccess: () => accept.mutate({ id, input: undefined }) })}>
          {t("chat.conflict.both")}
        </Button>
      </Foot>
    );
  } else {
    const canMove = (payload.kind === "create_page" || payload.kind === "save_pdf") && Boolean(proposal.alternatives?.length);
    foot = (
      <Foot>
        <Button size="sm" variant="ink" disabled={busy} onClick={() => accept.mutate({ id, input: undefined })}>
          {t(proposal.kind === "undo" ? "chat.undo" : "chat.accept")}
        </Button>
        {EDITABLE.includes(payload.kind) && (
          <Button size="sm" disabled={busy} onClick={() => setMode("edit")}>
            {t("chat.edit")}
          </Button>
        )}
        <Button size="sm" variant="quiet" disabled={busy} onClick={() => setMode("reject")}>
          {t("chat.reject")}
        </Button>
        {canMove && (
          <Button size="sm" variant="quiet" className="ml-auto" disabled={busy} onClick={() => otherPlace.mutate({ id, input: undefined })}>
            {t("chat.otherPlace")}
          </Button>
        )}
      </Foot>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      <section
        aria-label={kindLabel}
        className="overflow-hidden rounded-[10px] border border-line-2"
      >
        {unplaced && mode !== "left" ? (
          <>
            <div className="border-b border-line px-3 py-[9px] text-12 text-text-2">{t("chat.unplaced.question")}</div>
            <div className="flex flex-col border-b border-line py-1.5">
              {proposal.alternatives?.map((option) => (
                <button
                  key={`${option.node_id}-${option.landing}`}
                  type="button"
                  disabled={busy}
                  onClick={() => place({ nodeId: option.node_id, path: option.path })}
                  className="grid cursor-pointer grid-cols-[minmax(0,1fr)_auto] items-center gap-2.5 border-0 bg-transparent px-3 py-1 text-left font-[inherit] text-13 text-text hover:bg-subtle"
                >
                  <span className="font-mono text-12 break-words">
                    {whereOf({ ...payload, parent_path: option.path } as Payload, t)}
                  </span>
                  <span className="font-mono text-12 text-text-3 tabular-nums">{probability(option.probability, lang)}</span>
                </button>
              ))}
            </div>
          </>
        ) : (
          <>
            <Head where={whereOf(payload, t)}>
              {head}
              {agentName && <span className="font-normal text-text-3"> · {agentName}</span>}
            </Head>
            {mode === "edit" ? (
              <EditForm
                payload={payload}
                busy={busy}
                onCancel={() => setMode("idle")}
                onSave={(next) => edit.mutate({ id, input: next }, { onSuccess: () => setMode("idle") })}
              />
            ) : (
              <Body proposal={proposal} payload={payload} />
            )}
          </>
        )}
        {foot}
        {failed && (
          <p role="alert" className="m-0 border-t border-line px-3 py-2 text-12 text-err">
            {errorText(failed, { conflict: t("chat.proposal.closed") })}
            <button type="button" onClick={reset} className="ml-2 cursor-pointer border-0 bg-transparent p-0 text-12 text-text-2 underline">
              {t("chat.dismiss")}
            </button>
          </p>
        )}
      </section>
      {mode === "pick" && <FolderPicker kbId={proposal.kb_id} onPick={place} onClose={() => setMode("idle")} />}
      {undo.data && <ProposalCard proposal={undo.data} />}
    </div>
  );
}

/** Several files of one reply, waiting together: one line each, accepted all at once or reviewed one by one. */
export function FileGroup({ proposals, onReview }: { proposals: AnyProposal[]; onReview: () => void }) {
  const { t } = useI18n();
  const errorText = useErrorText();
  const accept = useAcceptProposal();
  const [busy, setBusy] = useState(false);
  const acceptAll = async () => {
    setBusy(true);
    try {
      for (const proposal of proposals) await accept.mutateAsync({ id: proposal.id, input: undefined });
    } catch {
      // The error shows below; what was accepted stays accepted.
    } finally {
      setBusy(false);
    }
  };
  return (
    <section aria-label={t("chat.files.label")} className="overflow-hidden rounded-[10px] border border-line-2">
      {proposals.map((proposal) => {
        const payload = payloadOf(proposal);
        return (
          <div key={proposal.id} className="flex flex-col gap-0.5 border-b border-line px-3 py-2 text-12">
            <span>
              {payload.kind === "replace_pdf"
                ? t("chat.pdf.newVersionOf", { name: lastPart(payload.path) })
                : t("chat.files.save", { name: payload.kind === "save_pdf" ? payload.name : "" })}
            </span>
            <span className="font-mono text-text-3">{whereOf(payload, t)}</span>
          </div>
        );
      })}
      <Foot>
        <Button size="sm" variant="ink" disabled={busy} onClick={acceptAll}>
          {t("chat.files.acceptAll", { count: proposals.length })}
        </Button>
        <Button size="sm" disabled={busy} onClick={onReview}>
          {t("chat.files.review")}
        </Button>
      </Foot>
      {accept.error && (
        <p role="alert" className="m-0 border-t border-line px-3 py-2 text-12 text-err">
          {errorText(accept.error)}
        </p>
      )}
    </section>
  );
}
