import { Dot, type Tone } from "./Dot";

export function StatusValue({ label, tone }: { label: string; tone: Tone }) {
  return <Dot tone={tone}>{label}</Dot>;
}
