import { useId, useState, type FormEvent } from "react";
import { useParams } from "react-router-dom";
import { AiMark } from "../../app/AiMark";
import {
  mcpUrl,
  useAgents,
  useConnectAgent,
  useRevokeAgent,
  useSetAgentMode,
  type Agent,
  type AgentMode,
} from "../../data/agents";
import { useI18n } from "../../i18n";
import { Button } from "../../ui/Button";
import { cx } from "../../ui/cx";
import { Dialog, DialogClose } from "../../ui/Dialog";
import { Input } from "../../ui/Input";
import { fullDate, relativeTime } from "../bases/when";
import { TopBar } from "../shell/TopBar";

const MODES: AgentMode[] = ["ask", "auto"];

function ModeSwitch({ agent, kbId }: { agent: Agent; kbId: string }) {
  const { t } = useI18n();
  const setMode = useSetAgentMode(kbId);
  return (
    <span className="flex items-center gap-2">
      {setMode.isError && (
        <span role="alert" className="text-12 text-err">
          {t("agents.mode.error")}
        </span>
      )}
      <span
        role="group"
        aria-label={t("agents.mode", { name: agent.name })}
        className="inline-flex gap-0.5 rounded-[7px] border border-line-2 p-0.5"
      >
        {MODES.map((mode) => (
          <button
            key={mode}
            type="button"
            aria-pressed={agent.mode === mode}
            disabled={setMode.isPending}
            onClick={() => agent.mode !== mode && setMode.mutate({ agentId: agent.id, mode })}
            className={cx(
              "h-6 cursor-pointer rounded-[5px] border-0 bg-transparent px-2.5 text-12 text-text-3",
              "aria-pressed:bg-muted aria-pressed:font-medium aria-pressed:text-text disabled:cursor-default",
            )}
          >
            {t(`agents.mode.${mode}`)}
          </button>
        ))}
      </span>
    </span>
  );
}

function AgentRow({ agent, kbId, onRevoke }: { agent: Agent; kbId: string; onRevoke: (agent: Agent) => void }) {
  const { t, lang } = useI18n();
  const when = (key: string, iso: string) => (
    <time dateTime={iso} title={fullDate(iso, lang)}>
      {t(key, { when: relativeTime(iso, lang) })}
    </time>
  );
  return (
    <li className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4 gap-y-1 border-b border-line py-3.5">
      <span className="flex items-center gap-2 font-medium">
        {agent.built_in && <AiMark />}
        {agent.name}
      </span>
      {!agent.revoked_at && (
        <span className="flex items-center gap-1">
          {!agent.built_in && (
            <Button size="sm" variant="quiet" onClick={() => onRevoke(agent)}>
              {t("agents.revoke")}
            </Button>
          )}
          <ModeSwitch agent={agent} kbId={kbId} />
        </span>
      )}
      <span className="col-span-2 text-12 text-text-3">
        {agent.built_in ? t("agents.builtIn") : t("agents.mcp")}
        {agent.token_hint && (
          <>
            {" · "}
            {t("agents.token")} <span className="font-mono">acv_…{agent.token_hint}</span>
          </>
        )}
        {" · "}
        {agent.revoked_at
          ? when("agents.revoked", agent.revoked_at)
          : agent.last_used_at
            ? when("agents.used", agent.last_used_at)
            : t("agents.used.never")}
      </span>
    </li>
  );
}

/** The agent's name, then its connection with the token, shown this once. */
function ConnectDialog({ kbId, onClose }: { kbId: string; onClose: () => void }) {
  const { t } = useI18n();
  const formId = useId();
  const [name, setName] = useState("");
  const [copied, setCopied] = useState(false);
  const connect = useConnectAgent(kbId);
  const token = connect.data?.token;
  const connection = token
    ? JSON.stringify({ url: mcpUrl(), headers: { Authorization: `Bearer ${token}` } }, null, 1)
    : "";

  function submit(event: FormEvent) {
    event.preventDefault();
    connect.mutate(name.trim());
  }

  async function copy() {
    await navigator.clipboard.writeText(connection);
    setCopied(true);
  }

  return (
    <Dialog
      open
      onOpenChange={(open) => !open && onClose()}
      title={t("agents.connect")}
      footer={
        token ? (
          <Button variant="ink" onClick={onClose}>
            {t("agents.connect.done")}
          </Button>
        ) : (
          <>
            <DialogClose asChild>
              <Button variant="quiet">{t("agents.cancel")}</Button>
            </DialogClose>
            <Button type="submit" form={formId} variant="ink" disabled={connect.isPending || name.trim() === ""}>
              {t("agents.connect.submit")}
            </Button>
          </>
        )
      }
    >
      {token ? (
        <div className="flex flex-col gap-2">
          <p className="m-0 text-12 text-text-2">{t("agents.connect.once")}</p>
          <pre
            aria-label={t("agents.connect.connection")}
            className="m-0 overflow-x-auto rounded-[7px] border border-line-2 bg-subtle px-2.5 py-2 font-mono text-12 whitespace-pre-wrap break-all text-text"
          >
            {connection}
          </pre>
          <span className="flex items-center gap-2">
            <Button size="sm" onClick={copy}>
              {t("agents.connect.copy")}
            </Button>
            {copied && (
              <span role="status" className="text-12 text-text-3">
                {t("agents.connect.copied")}
              </span>
            )}
          </span>
        </div>
      ) : (
        <form id={formId} onSubmit={submit} className="flex flex-col gap-3">
          <label className="flex flex-col gap-1.5 text-12 text-text-2">
            {t("agents.connect.name")}
            <Input
              autoFocus
              value={name}
              placeholder={t("agents.connect.placeholder")}
              onChange={(event) => setName(event.target.value)}
              onKeyDown={(event) => {
                // The submit button sits in the dialog's footer, so the browser's own Enter does not reach it.
                if (event.key !== "Enter" || event.nativeEvent.isComposing) return;
                event.preventDefault();
                if (name.trim() && !connect.isPending) submit(event);
              }}
            />
          </label>
          {connect.isError && (
            <p role="alert" className="m-0 text-12 text-err">
              {t("agents.connect.error")}
            </p>
          )}
        </form>
      )}
    </Dialog>
  );
}

function RevokeDialog({ agent, kbId, onClose }: { agent: Agent; kbId: string; onClose: () => void }) {
  const { t } = useI18n();
  const revoke = useRevokeAgent(kbId);
  return (
    <Dialog
      open
      onOpenChange={(open) => !open && onClose()}
      title={t("agents.revoke.title", { name: agent.name })}
      description={t("agents.revoke.text")}
      footer={
        <>
          <DialogClose asChild>
            <Button variant="quiet">{t("agents.cancel")}</Button>
          </DialogClose>
          <Button variant="ink" disabled={revoke.isPending} onClick={() => revoke.mutate(agent.id, { onSuccess: onClose })}>
            {t("agents.revoke")}
          </Button>
        </>
      }
    >
      {revoke.isError && (
        <p role="alert" className="m-0 text-12 text-err">
          {t("agents.revoke.error")}
        </p>
      )}
    </Dialog>
  );
}

/** The base's agents: the built-in chat and those connected over MCP, each with its mode. */
export function AgentsScreen() {
  const { t } = useI18n();
  const { kbId = "" } = useParams();
  const agents = useAgents(kbId);
  const [connecting, setConnecting] = useState(false);
  const [revoking, setRevoking] = useState<Agent | null>(null);
  return (
    <>
      <TopBar kbId={kbId} />
      <div className="mx-auto w-full max-w-[720px] px-8 pt-14 pb-16">
        <div className="flex items-center justify-between gap-4">
          <h1 className="m-0 text-32 font-medium tracking-[-0.035em]">{t("agents.title")}</h1>
          <Button variant="ink" onClick={() => setConnecting(true)}>
            {t("agents.connect")}
          </Button>
        </div>
        <p className="m-0 mt-2 text-text-3">{t("agents.intro")}</p>
        <section className="mt-10">
          {agents.isPending ? (
            <p className="m-0 text-text-3">{t("agents.loading")}</p>
          ) : agents.isError ? (
            <div className="flex items-center gap-3">
              <p role="alert" className="m-0 text-err">
                {t("agents.error.load")}
              </p>
              <Button size="sm" onClick={() => agents.refetch()}>
                {t("agents.retry")}
              </Button>
            </div>
          ) : (
            <ul className="m-0 list-none border-t border-line p-0">
              {agents.data.map((agent) => (
                <AgentRow key={agent.id} agent={agent} kbId={kbId} onRevoke={setRevoking} />
              ))}
            </ul>
          )}
        </section>
      </div>
      {connecting && <ConnectDialog kbId={kbId} onClose={() => setConnecting(false)} />}
      {revoking && <RevokeDialog agent={revoking} kbId={kbId} onClose={() => setRevoking(null)} />}
    </>
  );
}
