import { useI18n } from "../i18n";
import { Icon } from "./Icon";

const providers = {
  YouTube: ["youtube.com", "16 / 9"],
  Figma: ["figma.com", "4 / 3"],
  "Google Maps": ["google.com/maps", "16 / 9"],
  Loom: ["loom.com", "16 / 10"],
  GitHub: ["gist.github.com", "3 / 1"],
} as const;

export type EmbedProvider = keyof typeof providers;

/** Another service's content in its own ratio, with "Abrir no site"; when the service blocks it, the notice and the link. */
export function EmbedFrame({
  provider,
  src,
  url,
  blocked = false,
}: {
  provider: EmbedProvider;
  /** The service's embed address, shown in the frame. */
  src: string;
  /** The content's page on the service. */
  url: string;
  blocked?: boolean;
}) {
  const { t } = useI18n();
  const [domain, ratio] = providers[provider];
  return (
    <div>
      <div
        style={{ aspectRatio: ratio }}
        className="flex max-h-[300px] w-full items-center justify-center overflow-hidden rounded-[7px] border border-line bg-subtle"
      >
        {blocked ? (
          <div className="flex flex-col items-center gap-2 p-4 text-center text-13 text-text-2">
            <Icon name="link" />
            {t("media.embed.blocked", { provider })}
            <a href={url} target="_blank" rel="noopener noreferrer" className="text-text">
              {t("media.embed.open")}
            </a>
          </div>
        ) : (
          <iframe
            src={src}
            title={provider}
            sandbox="allow-scripts allow-same-origin allow-popups allow-presentation"
            allowFullScreen
            className="size-full border-0"
          />
        )}
      </div>
      <div className="mt-1.5 flex items-center justify-between text-12 text-text-3">
        <span className="font-mono">{domain}</span>
        <a href={url} target="_blank" rel="noopener noreferrer" className="text-text-2">
          {t("media.embed.open")}
        </a>
      </div>
    </div>
  );
}
