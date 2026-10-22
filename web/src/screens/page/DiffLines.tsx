import type { DiffLine } from "../../api/client";
import { cx } from "../../ui/cx";

const marks = { same: "  ", add: "+ ", del: "- " };

/** A difference as the server computed it, line by line. */
export function DiffLines({ lines }: { lines: DiffLine[] }) {
  return (
    <div className="overflow-x-auto py-2 font-mono text-12">
      {lines.map((line, i) => (
        <span
          key={i}
          data-op={line.op}
          className={cx(
            "block px-3 whitespace-pre-wrap",
            line.op === "add" && "bg-add",
            line.op === "del" && "bg-del",
            line.op === "same" && "text-text-3",
          )}
        >
          {marks[line.op]}
          {line.text}
        </span>
      ))}
    </div>
  );
}
