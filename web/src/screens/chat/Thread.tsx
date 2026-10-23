import { useEffect, useRef, useState } from "react";
import { AiMark } from "../../app/AiMark";
import { useErrorText } from "../../app/errors";
import { ROUTES, useReroute, type Message, type Route, type StepEvent } from "../../data/chat";
import type { Proposal, ProposalSummary } from "../../data/proposals";
import { useI18n } from "../../i18n";
import { Button } from "../../ui/Button";
import { FileName } from "../../ui/FileName";
import { Icon } from "../../ui/Icon";
import { Menu, MenuItem } from "../../ui/Menu";
import { splitExt } from "../../ui/names";
import { cx } from "../../ui/cx";
import { formatSize } from "../file/format";
import { FileGroup, ProposalCard } from "./ProposalCard";
import { Steps } from "./Steps";
import { isUnplaced } from "./where";

type AnyProposal = Proposal | ProposalSummary;

const FILE_KINDS = ["save_pdf", "replace_pdf"];

function PersonMessage({ message }: { message: Message }) {
  const { lang } = useI18n();
  const selection = message.context?.selection;
  return (
    <div className="flex max-w-[86%] flex-col gap-1.5 self-end rounded-[12px_12px_4px_12px] bg-subtle px-3 py-2 break-words">
      {selection && <span className="border-l-2 border-line-2 pl-2.5 text-text-2">{selection}</span>}
      {message.attachments?.map((file) => {
        const { name, ext } = splitExt(file.name);
        return (
          <span key={file.sha256} className="flex items-center gap-2 text-12">
            <Icon name="file" size={15} />
            <FileName title={name} ext={ext} className="min-w-0 truncate" />
            <span className="shrink-0 text-text-3">{formatSize(file.size, lang)}</span>
          </span>
        );
      })}
      {message.text && <span className="whitespace-pre-line">{message.text}</span>}
    </div>
  );
}

/** "Entendi como algo para guardar · mudar": the other readings, each redoing the message that way. */
function Understood({ reply }: { reply: Message }) {
  const { t } = useI18n();
  const reroute = useReroute();
  const route = reply.understood_as;
  if (!route) return null;
  return (
    <span className="flex flex-wrap items-center gap-1.5 text-12 text-text-3">
      {t(`chat.understood.${route}`)}
      <span aria-hidden="true">·</span>
      <Menu
        label={t("chat.change")}
        trigger={
          <button
            type="button"
            disabled={reroute.isPending}
            className="cursor-pointer border-0 bg-transparent p-0 text-12 text-text-2 underline decoration-line-2 underline-offset-[3px]"
          >
            {t("chat.change")}
          </button>
        }
      >
        {ROUTES.filter((other) => other !== route).map((other) => (
          <MenuItem key={other} onSelect={() => reroute.mutate({ replyId: reply.id, route: other })}>
            {t(`chat.reroute.${other}`)}
          </MenuItem>
        ))}
      </Menu>
    </span>
  );
}

function Reply({
  reply,
  replaced,
  steps,
  proposals,
}: {
  reply: Message;
  replaced: boolean;
  steps: StepEvent[];
  proposals: AnyProposal[];
}) {
  const { t } = useI18n();
  const errorText = useErrorText();
  const reroute = useReroute();
  const [review, setReview] = useState(false);
  const choose = (route: Route) => reroute.mutate({ replyId: reply.id, route });

  const grouped = review
    ? []
    : proposals.filter((p) => FILE_KINDS.includes(p.kind) && p.status === "pending" && !isUnplaced(p));
  const cards = grouped.length > 1 ? proposals.filter((p) => !grouped.includes(p)) : proposals;

  return (
    <article aria-label={t("chat.reply")} className={cx("flex flex-col gap-2", replaced && "opacity-45")}>
      <span className="flex items-center gap-1.5 text-12 text-ai-text">
        <AiMark size={13} />
        {t("chat.acervo")}
      </span>
      {reply.status === "working" && (
        <>
          <span className="text-text-2">{t("chat.working")}</span>
          {steps.length > 0 && <Steps steps={steps} />}
          <span className="text-12 text-text-3">{t("chat.keepGoing")}</span>
        </>
      )}
      {reply.status === "failed" && (
        <>
          <span role="alert" className="text-err">
            {t("chat.failed")}
          </span>
          {!replaced && (
            <span>
              <Button
                size="sm"
                disabled={reroute.isPending}
                onClick={() => choose(reply.understood_as ?? reply.ask?.[0] ?? "guardar")}
              >
                {t("chat.retry")}
              </Button>
            </span>
          )}
        </>
      )}
      {reply.status === "done" && (
        <>
          {reply.text && <span className="whitespace-pre-line">{reply.text}</span>}
          {reply.ask && reply.ask.length > 0 && !replaced && (
            <span className="flex gap-1">
              {reply.ask.map((route) => (
                <Button key={route} size="sm" disabled={reroute.isPending} onClick={() => choose(route)}>
                  {t(`chat.ask.${route}`)}
                </Button>
              ))}
            </span>
          )}
          {grouped.length > 1 && <FileGroup proposals={grouped} onReview={() => setReview(true)} />}
          {cards.map((proposal) => (
            <ProposalCard key={proposal.id} proposal={proposal} />
          ))}
          {!replaced && !reply.ask?.length && <Understood reply={reply} />}
        </>
      )}
      {reroute.error && (
        <span role="alert" className="text-12 text-err">
          {errorText(reroute.error)}
        </span>
      )}
    </article>
  );
}

/** The conversation, oldest first, kept scrolled to its end as replies arrive. */
export function Thread({
  messages,
  steps,
  proposalsOf,
}: {
  messages: Message[];
  steps: Record<string, StepEvent[]>;
  proposalsOf: (replyId: string) => AnyProposal[];
}) {
  const { t } = useI18n();
  const end = useRef<HTMLDivElement>(null);
  const replacedIds = new Set(messages.map((m) => m.replaces_id).filter(Boolean));
  const last = messages.at(-1);

  useEffect(() => {
    end.current?.scrollIntoView?.({ block: "end" });
  }, [messages.length, last?.status]);

  if (messages.length === 0)
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
        message.role === "person" ? (
          <PersonMessage key={message.id} message={message} />
        ) : (
          <Reply
            key={message.id}
            reply={message}
            replaced={replacedIds.has(message.id)}
            steps={steps[message.id] ?? []}
            proposals={proposalsOf(message.id)}
          />
        ),
      )}
      <div ref={end} />
    </div>
  );
}
