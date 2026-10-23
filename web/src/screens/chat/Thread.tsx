import { isToolUIPart, type ChatStatus } from "ai";
import { memo, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { AiMark } from "../../app/AiMark";
import { useErrorText } from "../../app/errors";
import { useRetry, type ChatMessage, type Citation } from "../../data/chat";
import { newest, useProposalStates, type Proposal, type ProposalSummary } from "../../data/proposals";
import { useI18n } from "../../i18n";
import { Button } from "../../ui/Button";
import { FileName } from "../../ui/FileName";
import { Icon } from "../../ui/Icon";
import { splitExt } from "../../ui/names";
import { formatSize } from "../file/format";
import { useFollow } from "./follow";
import { FileGroup, ProposalCard } from "./ProposalCard";
import { ReplyText } from "./ReplyText";
import { Steps } from "./Steps";
import { isUnplaced, lastPart } from "./where";

type AnyProposal = Proposal | ProposalSummary;

const FILE_KINDS = ["save_pdf", "replace_pdf"];

// Memoized, as Reply: a streamed chunk changes only the last message, so the others keep their parsed Markdown.
const PersonMessage = memo(function PersonMessage({ message }: { message: ChatMessage }) {
  const { lang } = useI18n();
  const { selection, attachments } = message.metadata ?? {};
  return (
    <div className="flex max-w-[86%] flex-col gap-1.5 self-end rounded-[12px_12px_4px_12px] bg-subtle px-3 py-2 break-words">
      {selection && <span className="border-l-2 border-line-2 pl-2.5 text-text-2">{selection}</span>}
      {attachments?.map((file, i) => {
        const { name, ext } = splitExt(file.name);
        return (
          <span key={`${file.name}-${i}`} className="flex items-center gap-2 text-12">
            <Icon name="file" size={15} />
            <FileName title={name} ext={ext} className="min-w-0 truncate" />
            <span className="shrink-0 text-text-3">{formatSize(file.size, lang)}</span>
          </span>
        );
      })}
      {message.parts.map((part, i) =>
        part.type === "text" && part.text ? (
          <span key={i} className="whitespace-pre-line">
            {part.text}
          </span>
        ) : null,
      )}
    </div>
  );
});

/** Where a citation opens: the page (at its section), or the PDF at its page. */
function citationHref(kbId: string, citation: Citation): string {
  const at = citation.kind === "file" ? (citation.page ? `?p=${citation.page}` : "") : citation.anchor ? `#${citation.anchor}` : "";
  return `/kbs/${kbId}/n/${citation.node_id}${at}`;
}

function Sources({ kbId, citations }: { kbId: string; citations: Citation[] }) {
  const { t } = useI18n();
  return (
    <ol aria-label={t("chat.sources")} className="m-0 flex list-none flex-col p-0">
      {citations.map((citation) => {
        const { name, ext } = citation.kind === "page" ? { name: lastPart(citation.path), ext: "md" } : splitExt(lastPart(citation.path));
        return (
          <li key={citation.marker}>
            <Link
              to={citationHref(kbId, citation)}
              title={citation.path.split("/").join(" / ")}
              className="grid grid-cols-[20px_minmax(0,1fr)_auto] items-center gap-1.5 text-12 leading-[22px] text-text-2 no-underline hover:text-text"
            >
              <span className="font-medium text-ink">{citation.marker}</span>
              <FileName title={name} ext={ext} className="truncate" />
              {citation.page ? <span className="text-text-3">{t("chat.source.page", { page: citation.page })}</span> : <span />}
            </Link>
          </li>
        );
      })}
    </ol>
  );
}

const Reply = memo(function Reply({
  message,
  kbId,
  working,
  failed,
  busy,
}: {
  message: ChatMessage;
  kbId: string;
  working: boolean;
  failed: boolean;
  busy: boolean;
}) {
  const { t } = useI18n();
  const errorText = useErrorText();
  const retry = useRetry();
  const follow = useFollow();
  const [review, setReview] = useState(false);
  const [showSteps, setShowSteps] = useState(false);

  const states = useProposalStates().data;
  const proposals: AnyProposal[] = message.parts.flatMap((part) =>
    part.type === "data-proposal" ? [newest(states?.[part.data.id], part.data)] : [],
  );
  const citations = message.parts.flatMap((part) => {
    const citation = part.type === "source-document" ? (part.providerMetadata?.acervo as Citation | undefined) : undefined;
    return citation?.node_id ? [citation] : [];
  });
  const hrefOf = (marker: number) => {
    const citation = citations.find((c) => c.marker === marker);
    return citation && citationHref(kbId, citation);
  };
  const texts = message.parts.flatMap((part) => (part.type === "text" && part.text ? [part.text] : []));
  const steps = message.parts.filter(isToolUIPart);

  const grouped = review
    ? []
    : proposals.filter((p) => FILE_KINDS.includes(p.kind) && p.status === "pending" && !isUnplaced(p));
  const cards = grouped.length > 1 ? proposals.filter((p) => !grouped.includes(p)) : proposals;
  const general = !working && !failed && message.metadata?.grounded === false && texts.length > 0;

  return (
    <article aria-label={t("chat.reply")} className="flex flex-col gap-2">
      <span className="flex items-center gap-1.5 text-12 text-ai-text">
        <AiMark size={13} />
        {t("chat.acervo")}
      </span>
      {working ? (
        <Steps parts={steps} />
      ) : (
        steps.length > 0 && (
          <span>
            <button
              type="button"
              aria-expanded={showSteps}
              onClick={() => setShowSteps(!showSteps)}
              className="cursor-pointer border-0 bg-transparent p-0 font-[inherit] text-12 text-text-3 underline decoration-line-2 underline-offset-[3px] hover:text-text-2"
            >
              {t("chat.steps.show", { count: steps.length })}
            </button>
            {showSteps && <Steps parts={steps} />}
          </span>
        )
      )}
      {texts.map((text, i) => (
        <ReplyText key={i} text={text} hrefOf={hrefOf} />
      ))}
      {working && texts.length === 0 && (
        <>
          <span className="text-text-2">{t("chat.working")}</span>
          <span className="text-12 text-text-3">{t("chat.keepGoing")}</span>
        </>
      )}
      {grouped.length > 1 && <FileGroup proposals={grouped} onReview={() => setReview(true)} />}
      {cards.map((proposal) => (
        <ProposalCard key={proposal.id} proposal={proposal} />
      ))}
      {citations.length > 0 && <Sources kbId={kbId} citations={citations} />}
      {general && <span className="text-12 text-text-3">{t("chat.general")}</span>}
      {failed && (
        <>
          <span role="alert" className="text-err">
            {t("chat.failed")}
          </span>
          <span>
            <Button
              size="sm"
              disabled={busy || retry.isPending}
              onClick={() => retry.mutate(message.id, { onSuccess: (reply) => follow(reply.id, message.id) })}
            >
              {t("chat.retry")}
            </Button>
          </span>
        </>
      )}
      {retry.error && (
        <span role="alert" className="text-12 text-err">
          {errorText(retry.error)}
        </span>
      )}
    </article>
  );
});

/** The conversation, oldest first, kept scrolled to its end as replies arrive. */
export function Thread({
  kbId,
  messages,
  status,
  streamFailed,
}: {
  kbId: string;
  messages: ChatMessage[];
  status: ChatStatus;
  streamFailed: boolean;
}) {
  const { t } = useI18n();
  const end = useRef<HTMLDivElement>(null);
  const last = messages.at(-1);
  const busy = status === "submitted" || status === "streaming";

  useEffect(() => {
    end.current?.scrollIntoView?.({ block: "end" });
  }, [messages.length, last?.parts.length, status]);

  if (messages.length === 0 && !busy)
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-2 px-8 py-6 text-center">
        <AiMark size={28} />
        <span className="text-15 font-medium">{t("chat.empty.title")}</span>
        <span className="text-text-3">{t("chat.empty.text")}</span>
      </div>
    );

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-5 overflow-y-auto px-4 py-[18px]">
      {messages.map((message) =>
        message.role === "user" ? (
          <PersonMessage key={message.id} message={message} />
        ) : (
          <Reply
            key={message.id}
            message={message}
            kbId={kbId}
            busy={busy}
            working={busy && message === last}
            failed={message.metadata?.status === "failed" || (streamFailed && message === last)}
          />
        ),
      )}
      {busy && last?.role !== "assistant" && (
        <article aria-label={t("chat.reply")} className="flex flex-col gap-2">
          <span className="flex items-center gap-1.5 text-12 text-ai-text">
            <AiMark size={13} />
            {t("chat.acervo")}
          </span>
          <span className="text-text-2">{t("chat.working")}</span>
        </article>
      )}
      <div ref={end} />
    </div>
  );
}
