import { useState } from "react";
import { useErrorText } from "../../app/errors";
import { useUndoProposal, type ProposalSummary } from "../../data/proposals";
import { useI18n } from "../../i18n";
import { Button } from "../../ui/Button";
import { Dot } from "../../ui/Dot";
import { ProposalCard } from "./ProposalCard";
import { payloadOf, whereOf } from "./where";

function Heading({ children }: { children: string }) {
  return <h3 className="m-0 border-b border-line px-4 pt-4 pb-2 text-12 font-medium text-text-3">{children}</h3>;
}

/** A change an agent in auto mode applied: its kind, where, which agent, and "Desfazer". */
function Applied({ proposal }: { proposal: ProposalSummary }) {
  const { t } = useI18n();
  const errorText = useErrorText();
  const undo = useUndoProposal();
  return (
    <li className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-2 border-b border-line py-3 pr-3 pl-4">
      <span className="flex min-w-0 flex-col gap-0.5">
        <span className="font-medium">{t(`chat.kind.${proposal.kind}`)}</span>
        <span className="font-mono text-12 break-words text-text-3">{whereOf(payloadOf(proposal), t)}</span>
        <span className="text-12 text-text-3">{proposal.agent_name}</span>
      </span>
      {undo.data ? (
        <Dot tone={undo.data.status === "applied" ? "ok" : "warn"}>
          {t(undo.data.status === "applied" ? "chat.undone" : "chat.undo.waiting")}
        </Dot>
      ) : (
        <Button size="sm" variant="quiet" disabled={undo.isPending} onClick={() => undo.mutate({ id: proposal.id, input: undefined })}>
          {t("chat.undo")}
        </Button>
      )}
      {undo.error && (
        <span role="alert" className="col-span-2 text-12 text-err">
          {errorText(undo.error)}
        </span>
      )}
    </li>
  );
}

/**
 * Every proposal waiting in the base, from any conversation or agent, each with the agent that made it, then what
 * agents in auto mode applied lately. Opening a waiting one goes to the conversation it came from; one an agent made
 * outside a conversation, or whose conversation was deleted (it has no title then), opens right here.
 */
export function PendingList({
  proposals,
  applied,
  onOpenConversation,
}: {
  proposals: ProposalSummary[];
  applied: ProposalSummary[];
  onOpenConversation: (conversationId: string) => void;
}) {
  const { t } = useI18n();
  const [expanded, setExpanded] = useState<string | null>(null);

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-y-auto">
      {proposals.length === 0 ? (
        <p className="m-0 px-4 py-6 text-text-3">{t("chat.pending.none")}</p>
      ) : (
        <ul aria-label={t("chat.pending.title")} className="m-0 flex list-none flex-col p-0">
          {proposals.map((proposal) => {
            const kind = t(`chat.kind.${proposal.kind}`);
            const conversationId = proposal.conversation_title === null ? null : proposal.conversation_id;
            const from = [proposal.agent_name, proposal.conversation_title].filter(Boolean).join(" · ");
            return (
              <li key={proposal.id} className="border-b border-line">
                <button
                  type="button"
                  onClick={() =>
                    conversationId ? onOpenConversation(conversationId) : setExpanded(expanded === proposal.id ? null : proposal.id)
                  }
                  className="flex w-full cursor-pointer flex-col gap-0.5 border-0 bg-transparent px-4 py-3 text-left font-[inherit] text-13 text-text hover:bg-side"
                >
                  <span className="font-medium">
                    {proposal.kind === "conflict" ? <Dot tone="err"><span className="text-13 text-text">{kind}</span></Dot> : kind}
                  </span>
                  <span className="font-mono text-12 break-words text-text-3">{whereOf(payloadOf(proposal), t)}</span>
                  <span className="text-12 text-text-3">{from}</span>
                </button>
                {expanded === proposal.id && (
                  <div className="px-4 pb-3">
                    <ProposalCard proposal={proposal} agentName={proposal.agent_name} />
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
      {applied.length > 0 && (
        <section aria-label={t("chat.applied.title")}>
          <Heading>{t("chat.applied.title")}</Heading>
          <ul className="m-0 flex list-none flex-col p-0">
            {applied.map((proposal) => (
              <Applied key={proposal.id} proposal={proposal} />
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
