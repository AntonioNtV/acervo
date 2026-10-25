import { useState, type DragEvent } from "react";
import { useI18n } from "../i18n";
import { cx } from "./cx";
import type { Tone } from "./Dot";
import { StatusValue } from "./StatusValue";

type Props =
  | { variant: "drop" }
  | {
      variant: "board" | "gallery";
      title: string;
      /** The line under the title on the board. */
      meta?: string;
      /** Hidden when empty. */
      value?: string;
      /** The status in the gallery. */
      status?: { label: string; tone: Tone };
      /** The preview area of the gallery. */
      preview?: boolean;
      onOpen: () => void;
      onDragStart?: (event: DragEvent) => void;
      onDragEnd?: (event: DragEvent) => void;
    };

/** A row of a database on the board or in the gallery; `drop` is the place a dragged card lands. */
export function RecordCard(props: Props) {
  const { t } = useI18n();
  const [dragging, setDragging] = useState(false);

  if (props.variant === "drop") {
    return (
      <div className="flex h-16 items-center justify-center rounded-[6px] border border-dashed border-ink bg-accent-soft text-12 text-text-2">
        {t("data.drop")}
      </div>
    );
  }

  const { variant, title, meta, value, status, preview, onOpen, onDragStart, onDragEnd } = props;
  return (
    <button
      type="button"
      draggable
      onClick={onOpen}
      onDragStart={(event) => {
        setDragging(true);
        onDragStart?.(event);
      }}
      onDragEnd={(event) => {
        setDragging(false);
        onDragEnd?.(event);
      }}
      className={cx(
        "flex w-full min-w-0 cursor-pointer flex-col overflow-hidden rounded-[6px] border p-0 text-left text-13 text-text",
        dragging ? "border-ink bg-accent-soft" : "border-line bg-bg hover:bg-subtle",
      )}
    >
      {variant === "gallery" && preview && (
        <span aria-hidden="true" className="flex h-24 flex-col justify-center gap-1.5 self-stretch bg-subtle px-[22%]">
          <span className="h-[5px] rounded-[3px] bg-line-2" />
          <span className="h-[5px] w-4/5 rounded-[3px] bg-line-2" />
          <span className="h-[5px] w-3/5 rounded-[3px] bg-line-2" />
        </span>
      )}
      <span className="flex flex-col gap-0.5 px-3 py-2.5">
        <span className="font-medium">{title}</span>
        <span className="flex flex-col gap-0.5">
          {variant === "board" ? (
            <>
              <span className="text-12 text-text-3">{meta}</span>
              {value && <span className="tabular-nums">{value}</span>}
            </>
          ) : (
            <>
              {status && <StatusValue label={status.label} tone={status.tone} />}
              {value && <span className="text-text-3 tabular-nums">{value}</span>}
            </>
          )}
        </span>
      </span>
    </button>
  );
}
