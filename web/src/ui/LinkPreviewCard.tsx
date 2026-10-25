import { useI18n } from "../i18n";
import { Icon } from "./Icon";

/** A link shown as its site's title, description, domain and image; a skeleton while read, the URL when it could not be. */
export function LinkPreviewCard({
  url,
  state,
  title,
  description,
  domain,
  image,
}: {
  url: string;
  state: "done" | "loading" | "failed";
  title?: string;
  description?: string;
  domain: string;
  image?: string;
}) {
  const { t } = useI18n();
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      aria-busy={state === "loading" || undefined}
      className="flex min-h-24 overflow-hidden rounded-[7px] border border-line text-text no-underline"
    >
      <span className="flex min-w-0 flex-1 flex-col gap-1 px-3.5 py-3">
        {state === "loading" ? (
          <>
            <span className="my-1 block h-3 w-3/5 rounded-[3px] bg-muted" />
            <span className="my-1 block h-3 w-[90%] rounded-[3px] bg-muted" />
          </>
        ) : (
          <>
            <span className="text-[14px] leading-5 font-medium [overflow-wrap:anywhere]">
              {state === "failed" ? url : title}
            </span>
            <span className={state === "failed" ? "text-13 text-text-3" : "line-clamp-2 text-13 text-text-2"}>
              {state === "failed" ? t("media.link.failed") : description}
            </span>
          </>
        )}
        <span className="font-mono text-12 text-text-3">{domain}</span>
      </span>
      {state !== "failed" && (
        <span className="flex w-[120px] flex-none items-center justify-center overflow-hidden bg-subtle text-ghost">
          {state === "done" &&
            (image ? <img src={image} alt="" className="size-full object-cover" /> : <Icon name="image" size={20} />)}
        </span>
      )}
    </a>
  );
}
