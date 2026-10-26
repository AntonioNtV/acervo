import type { ReactNode } from "react";

export type Tone = "neutral" | "ok" | "err" | "warn" | "run";

export const tones: Record<Tone, string> = {
  neutral: "bg-text-3",
  ok: "bg-ok",
  err: "bg-err",
  warn: "bg-warn",
  run: "bg-run",
};

export function Dot({ tone = "neutral", children }: { tone?: Tone; children?: ReactNode }) {
  return (
    <span className="inline-flex items-center gap-[7px] text-12 whitespace-nowrap text-text-2">
      <span aria-hidden="true" className={`size-1.5 shrink-0 rounded-full ${tones[tone]}`} />
      {children}
    </span>
  );
}
