import { useRef } from "react";
import { useI18n } from "../i18n";
import { Button } from "./Button";
import { Icon } from "./Icon";

/**
 * Where an image or a file is not yet: empty (Enviar, or drop files on it), uploading while `progress` is given, or
 * failed while `error` is given.
 */
export function UploadArea({
  kind,
  progress,
  name,
  error,
  onFiles,
  onRetry,
}: {
  kind: "image" | "file";
  /** 0–100; given while uploading. */
  progress?: number;
  /** The file being sent, shown while a file uploads. */
  name?: string;
  /** What went wrong and what to do; given when the upload failed. */
  error?: string;
  onFiles: (files: File[]) => void;
  onRetry: () => void;
}) {
  const { t } = useI18n();
  const input = useRef<HTMLInputElement>(null);
  const icon = kind === "image" ? "image" : "file";

  if (progress !== undefined) {
    const pct = Math.round(Math.max(0, Math.min(100, progress)));
    const label = (
      <span className="inline-flex items-center gap-[7px] text-12 whitespace-nowrap text-text-2 tabular-nums">
        <span aria-hidden="true" className="size-1.5 shrink-0 rounded-full bg-run" />
        {t("media.sending", { pct })}
      </span>
    );
    const bar = (
      <span
        role="progressbar"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={name}
        style={{ width: `${pct}%` }}
        className="absolute bottom-0 left-0 h-[3px] bg-run"
      />
    );
    return kind === "image" ? (
      <div className="relative flex aspect-video items-center justify-center overflow-hidden rounded-[6px] bg-subtle text-ghost">
        <Icon name="image" size={28} />
        <span className="absolute bottom-3 left-3">{label}</span>
        {bar}
      </div>
    ) : (
      <div className="relative flex h-14 items-center gap-2.5 overflow-hidden rounded-[6px] bg-subtle px-3 text-13 text-text-3">
        <Icon name="file" />
        <span className="min-w-0 truncate text-text">{name}</span>
        <span className="ml-auto">{label}</span>
        {bar}
      </div>
    );
  }

  return (
    <div
      onDragOver={(event) => event.preventDefault()}
      onDrop={(event) => {
        event.preventDefault();
        if (!error && event.dataTransfer.files.length) onFiles(Array.from(event.dataTransfer.files));
      }}
      className="flex h-14 items-center gap-2.5 rounded-[6px] bg-subtle px-3 text-13 text-text-3"
    >
      <Icon name={icon} />
      {error ? (
        <>
          <span role="alert" className="min-w-0 text-err">
            {error}
          </span>
          <Button size="sm" className="ml-auto" onClick={onRetry}>
            {t("media.retry")}
          </Button>
        </>
      ) : (
        <>
          <span className="min-w-0">{t(`media.upload.${kind}`)}</span>
          <input
            ref={input}
            type="file"
            hidden
            multiple={kind === "file"}
            accept={kind === "image" ? "image/*" : undefined}
            aria-label={t(`media.upload.${kind}`)}
            onChange={(event) => {
              if (event.target.files?.length) onFiles(Array.from(event.target.files));
              event.target.value = "";
            }}
          />
          <Button size="sm" className="ml-auto" onClick={() => input.current?.click()}>
            {t("media.send")}
          </Button>
        </>
      )}
    </div>
  );
}
