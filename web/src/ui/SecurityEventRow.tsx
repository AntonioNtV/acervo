import { tones, type Tone } from "./Dot";

/**
 * A line of Conta › Atividade or Organização › Auditoria: what happened, from which browser or in which area, and
 * when. The dot says whether it asks for attention: `warn` when something was turned off, `err` for failures.
 */
export function SecurityEventRow({
  tone,
  text,
  where,
  when,
}: {
  tone: Tone;
  text: string;
  where?: string;
  when: string;
}) {
  return (
    <div className="flex min-h-11 items-center gap-3 border-b border-line px-2 py-2 text-13">
      <span aria-hidden="true" className={`mx-[5px] size-1.5 shrink-0 rounded-full ${tones[tone]}`} />
      <span className="flex min-w-0 flex-1 flex-col">
        <span className="text-text">{text}</span>
        {where && <span className="truncate text-12 leading-[18px] text-text-3">{where}</span>}
      </span>
      <span className="shrink-0 text-12 text-text-3 tabular-nums">{when}</span>
    </div>
  );
}
