import { useState } from "react";
import type { ProposalSummary } from "../../data/proposals";
import { useI18n } from "../../i18n";
import { Dot } from "../../ui/Dot";
import { ProposalCard } from "./ProposalCard";
import { payloadOf, whereOf } from "./where";

/**
 * Every proposal waiting in the base, from any conversation or agent, each with the agent that made it. Opening one
 * goes to the conversation it came from; one an agent made outside a conversation opens right here.
 */
export function PendingList({
  proposals,
  onOpenConversation,
}: {
  proposals: ProposalSummary[];
  onOpenConversation: (conversationId: string) => void;
}) {
  const { t } = useI18n();
  const [expanded, setExpanded] = useState<string | null>(null);

  if (proposals.length === 0) return <p className="m-0 px-4 py-6 text-text-3">{t("chat.pending.none")}</p>;

  return (
    <ul aria-label={t("chat.pending.title")} className="m-0 flex min-h-0 flex-1 list-none flex-col overflow-y-auto p-0">
      {proposals.map((proposal) => {
        const kind = t(`chat.kind.${proposal.kind}`);
        const conversationId = proposal.conversation_id;
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
  );
}
