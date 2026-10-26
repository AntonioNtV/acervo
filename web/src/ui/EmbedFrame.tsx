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

const YOUTUBE_ID = /^[\w-]{11}$/;

/** What a URL of a provider's site shows in the frame: its embed address, or blocked when that page has none. */
export function embedOf(url: string): { provider: EmbedProvider; src: string | null } | null {
  let link: URL;
  try {
    link = new URL(url);
  } catch {
    return null;
  }
  const host = link.hostname.replace(/^(?:www|m)\./, "");
  const path = link.pathname.split("/").filter(Boolean);
  if (host === "youtu.be" || host === "youtube.com") {
    const id =
      host === "youtu.be"
        ? path[0]
        : path[0] === "shorts"
          ? path[1]
          : path[0] === "watch"
            ? link.searchParams.get("v")
            : null;
    return {
      provider: "YouTube",
      src: id && YOUTUBE_ID.test(id) ? `https://www.youtube-nocookie.com/embed/${id}` : null,
    };
  }
  if (host === "figma.com") {
    const shown = (path[0] === "file" || path[0] === "design") && path[1];
    return {
      provider: "Figma",
      src: shown ? `https://www.figma.com/embed?embed_host=acervo&url=${encodeURIComponent(url)}` : null,
    };
  }
  if (host === "google.com" && path[0] === "maps") {
    if (path[1] === "embed") return { provider: "Google Maps", src: url };
    const at = /^@(-?[\d.]+,-?[\d.]+)/.exec(path.find((part) => part.startsWith("@")) ?? "")?.[1];
    const q = link.searchParams.get("q") ?? at;
    // A place's name stays as the URL encoded it.
    const query = q ? encodeURIComponent(q) : path[1] === "place" || path[1] === "search" ? path[2] : undefined;
    return { provider: "Google Maps", src: query ? `https://maps.google.com/maps?q=${query}&output=embed` : null };
  }
  if (host === "loom.com")
    return { provider: "Loom", src: path[0] === "share" && path[1] ? `https://www.loom.com/embed/${path[1]}` : null };
  if (host === "gist.github.com")
    return { provider: "GitHub", src: path.length === 2 ? `https://gist.github.com/${path[0]}/${path[1]}.pibb` : null };
  return null;
}

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
            referrerPolicy="no-referrer"
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
