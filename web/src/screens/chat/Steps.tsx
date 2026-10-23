import type { StepEvent } from "../../data/chat";
import { useI18n } from "../../i18n";
import { Dot } from "../../ui/Dot";

/** The steps of a reply being worked on, as they arrive: the last one is running, the ones before it are done. */
export function Steps({ steps }: { steps: StepEvent[] }) {
  const { t } = useI18n();
  return (
    <ol aria-label={t("chat.steps")} className="m-0 flex list-none flex-col p-0">
      {steps.map((step, i) => {
        const running = i === steps.length - 1;
        return (
          <li key={i} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-2 text-12 leading-[22px] text-text-3">
            <Dot tone={running ? "run" : "ok"}>
              <span className={running ? "text-text" : "text-text-3"}>{t(`chat.step.${step.step}`)}</span>
            </Dot>
            {step.detail && <span className="truncate font-mono text-text-2">{step.detail}</span>}
          </li>
        );
      })}
    </ol>
  );
}
