import { useRef, useState, type SyntheticEvent } from "react";
import { useI18n } from "../i18n";
import { Button } from "./Button";
import { Dot } from "./Dot";
import { FileName } from "./FileName";
import { Icon } from "./Icon";
import { IconButton } from "./IconButton";

type Props =
  | {
      kind: "file";
      name: string;
      ext?: string;
      size?: string;
      /** 0–100; given while the file uploads. */
      progress?: number;
      failed?: boolean;
      /** Without it, a row at rest shows no Baixar. */
      onDownload?: () => void;
      onRetry: () => void;
    }
  | {
      kind: "video" | "audio";
      name: string;
      ext?: string;
      src: string;
      /** A link that stopped working after it had played; the player picks up where it was on the new `src`. */
      onExpired?: () => void;
    };

/** A file to download, a video in a 16:9 box or an audio in a one-line player; both play the original file. */
export function MediaRow(props: Props) {
  if (props.kind === "file") return <FileRow {...props} />;
  return <Player {...props} />;
}

function FileRow({ name, ext, size, progress, failed, onDownload, onRetry }: Extract<Props, { kind: "file" }>) {
  const { t } = useI18n();
  return (
    <div className="flex min-h-11 items-center gap-2.5 rounded-[7px] border border-line py-0 pr-1 pl-3 text-[14px] leading-5">
      <Icon name="file" className="text-text-3" />
      <FileName title={name} ext={ext} className="min-w-0 flex-1 truncate" />
      {size && <span className="text-12 whitespace-nowrap text-text-3 tabular-nums">{size}</span>}
      {progress !== undefined ? (
        <span className="tabular-nums">
          <Dot tone="run">{t("media.sending", { pct: Math.round(progress) })}</Dot>
        </span>
      ) : failed ? (
        <span className="inline-flex items-center gap-2 text-12 text-err">
          {t("media.failed")}
          <Button size="sm" onClick={onRetry}>
            {t("media.retry")}
          </Button>
        </span>
      ) : (
        onDownload && (
          <Button variant="quiet" size="sm" onClick={onDownload}>
            <Icon name="download" size={14} />
            {t("media.download")}
          </Button>
        )
      )}
    </div>
  );
}

function clock(seconds: number): string {
  const s = Math.floor(seconds);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

function Player({ kind, name, ext, src, onExpired }: Extract<Props, { kind: "video" | "audio" }>) {
  const { t } = useI18n();
  const media = useRef<HTMLVideoElement & HTMLAudioElement>(null);
  const [playing, setPlaying] = useState(false);
  const [broken, setBroken] = useState(false);
  const [time, setTime] = useState({ at: 0, total: 0 });
  // A file that never loaded its metadata is broken, not expired, so it is not asked for again.
  const loaded = useRef(false);
  const resume = useRef<{ at: number; play: boolean } | null>(null);
  const pct = time.total ? (time.at / time.total) * 100 : 0;
  const label = t(playing ? "media.pause" : "media.play");

  function toggle() {
    const el = media.current;
    if (!el) return;
    if (playing) el.pause();
    // A failed start fires `pause` or `error`, which the element's listeners already turn into state.
    else void el.play()?.catch(() => {});
  }

  const events = {
    src,
    preload: "metadata",
    onPlay: () => setPlaying(true),
    onPause: () => setPlaying(false),
    onEnded: () => setPlaying(false),
    onError: (event: SyntheticEvent<HTMLMediaElement>) => {
      if (!onExpired || !loaded.current) return setBroken(true);
      loaded.current = false;
      resume.current = { at: event.currentTarget.currentTime, play: playing };
      onExpired();
    },
    onLoadedMetadata: (event: SyntheticEvent<HTMLMediaElement>) => {
      const el = event.currentTarget;
      const total = el.duration;
      const at = resume.current?.at ?? 0;
      loaded.current = true;
      if (resume.current) {
        el.currentTime = at;
        if (resume.current.play) void el.play()?.catch(() => {});
        resume.current = null;
      }
      setTime({ at, total: Number.isFinite(total) ? total : 0 });
    },
    onTimeUpdate: (event: SyntheticEvent<HTMLMediaElement>) => {
      const at = event.currentTarget.currentTime;
      setTime((prev) => ({ ...prev, at }));
    },
  };
  const file = <FileName title={name} ext={ext} />;

  if (kind === "audio")
    return (
      <div className="flex min-h-11 items-center gap-2.5 rounded-[7px] border border-line py-0 pr-3 pl-1 text-13">
        <audio ref={media} {...events} />
        <IconButton aria-label={label} onClick={toggle} disabled={broken}>
          <Icon name={playing ? "pause" : "play"} />
        </IconButton>
        <span className="min-w-0 truncate">{file}</span>
        {broken ? (
          <span role="alert" className="text-12 text-err">
            {t("media.cannotPlay")}
          </span>
        ) : (
          <>
            <span className="relative h-px min-w-[60px] flex-1 bg-line-2">
              <span style={{ width: `${pct}%` }} className="absolute -top-px left-0 h-[3px] rounded-[2px] bg-ink" />
            </span>
            <span className="font-mono text-12 whitespace-nowrap text-text-3">
              {clock(time.at)} / {clock(time.total)}
            </span>
          </>
        )}
      </div>
    );

  return (
    <figure className="m-0 flex flex-col gap-2">
      {broken ? (
        <div
          role="alert"
          className="flex aspect-video items-center justify-center rounded-[6px] bg-subtle p-4 text-center text-13 text-err"
        >
          {t("media.cannotPlay")}
        </div>
      ) : (
        <div
          role="button"
          tabIndex={0}
          aria-label={label}
          onClick={toggle}
          onKeyDown={(event) => {
            if (event.key !== " " && event.key !== "Enter") return;
            event.preventDefault();
            toggle();
          }}
          className="relative flex aspect-video cursor-pointer items-center justify-center overflow-hidden rounded-[6px] bg-subtle"
        >
          <video ref={media} {...events} className="absolute inset-0 size-full" />
          {playing ? (
            <span style={{ width: `${pct}%` }} className="absolute bottom-0 left-0 h-[3px] bg-ink" />
          ) : (
            <span className="relative inline-flex size-11 items-center justify-center rounded-full border border-line-2 bg-bg text-text">
              <Icon name="play" size={20} />
            </span>
          )}
        </div>
      )}
      <figcaption className="text-13 text-text-3">
        {file}
        {time.total > 0 && ` · ${clock(time.total)}`}
      </figcaption>
    </figure>
  );
}
