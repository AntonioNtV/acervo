import * as RadixMenu from "@radix-ui/react-dropdown-menu";
import { useCallback, useRef, useState, type ReactNode } from "react";
import type { NodeDetail } from "../../api/client";
import { useErrorText } from "../../app/errors";
import { coverBackground, GALLERY, galleryCover, isImageCover, useCoverLink, useUploadCover } from "../../data/covers";
import { ApiError } from "../../data/request";
import { useDecorateNode } from "../../data/tree";
import { useI18n } from "../../i18n";
import { Button } from "../../ui/Button";
import { cx } from "../../ui/cx";
import { EmojiPicker } from "../../ui/EmojiPicker";
import { Menu, MenuItem, MenuSeparator } from "../../ui/Menu";

const IMAGE_TYPES = "image/png,image/jpeg,image/webp";

const quietClass =
  "flex h-7 cursor-pointer items-center gap-1.5 rounded-[6px] border-0 bg-transparent px-1.5 font-[inherit] text-13 text-text-3 hover:bg-subtle hover:text-text";

/** A hidden file input for the cover and what its upload failed with; a wrong type or size is told by its code. */
function useCoverUpload(nodeId: string) {
  const { t } = useI18n();
  const errorText = useErrorText();
  const upload = useUploadCover(nodeId);
  const input = useRef<HTMLInputElement>(null);
  const error = upload.error;
  const tooBig = error instanceof ApiError && error.code === "validation" && "max_bytes" in error.details;
  return {
    choose: () => input.current?.click(),
    error: error && (tooBig ? t("page.cover.error.size") : errorText(error, { validation: t("page.cover.error.type") })),
    input: (
      <input
        ref={input}
        type="file"
        accept={IMAGE_TYPES}
        hidden
        aria-label={t("page.cover.upload")}
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) upload.mutate(file);
          event.target.value = "";
        }}
      />
    ),
  };
}

/**
 * The gallery's covers and "Enviar imagem", below "Adicionar capa" or "Trocar": `align` keeps it on the side of its
 * button that has room, so it never opens over the sidebar.
 */
function CoverMenu({
  trigger,
  align,
  onPick,
  onUpload,
}: {
  trigger: ReactNode;
  align: "start" | "end";
  onPick: (cover: string) => void;
  onUpload: () => void;
}) {
  const { t } = useI18n();
  return (
    <Menu trigger={trigger} align={align} width={248} label={t("page.cover.gallery")}>
      <RadixMenu.Label className="px-1.5 pt-1 pb-1.5 text-12 text-text-3">{t("page.cover.gallery")}</RadixMenu.Label>
      <div className="grid grid-cols-4 gap-1.5 px-1.5 pb-1.5">
        {GALLERY.map((slug) => (
          <RadixMenu.Item
            key={slug}
            aria-label={t(`page.cover.${slug}`)}
            onSelect={() => onPick(galleryCover(slug))}
            style={{ background: coverBackground(galleryCover(slug)) }}
            className="h-10 cursor-pointer rounded-[6px] border border-line-2 outline-none data-[highlighted]:border-ink data-[highlighted]:shadow-[0_0_0_3px_var(--accent-soft)]"
          />
        ))}
      </div>
      <MenuSeparator />
      <MenuItem onSelect={onUpload}>{t("page.cover.upload")}</MenuItem>
    </Menu>
  );
}

/** An uploaded cover through its signed link; a link that expired before the image was read is asked again. */
function CoverImage({ nodeId, cover }: { nodeId: string; cover: string }) {
  const { t } = useI18n();
  const link = useCoverLink(nodeId, cover);
  const data = link.data;
  if (!data) return null;
  return (
    <img
      src={data.src}
      alt={t("page.cover.alt")}
      onError={() => Date.now() >= data.usableUntil && void link.refetch()}
      className="absolute inset-0 size-full object-cover"
    />
  );
}

/** A page's or folder's cover, full width above its column, with "Trocar" and "Remover" on hover. */
export function Cover({ node }: { node: NodeDetail }) {
  const { t } = useI18n();
  const errorText = useErrorText();
  const decorate = useDecorateNode();
  const upload = useCoverUpload(node.id);
  const setCover = (cover: string | null) => decorate.mutate({ nodeId: node.id, cover });
  if (!node.cover) return null;
  return (
    <div className="group/cover relative h-[200px] shrink-0" style={{ background: coverBackground(node.cover) }}>
      {isImageCover(node.cover) && <CoverImage nodeId={node.id} cover={node.cover} />}
      {upload.input}
      {(upload.error || decorate.error) && (
        <p role="alert" className="absolute bottom-3 left-4 m-0 rounded-[6px] bg-bg px-2 text-12 text-err">
          {upload.error || errorText(decorate.error)}
        </p>
      )}
      <div className="absolute right-4 bottom-3 flex gap-1.5 opacity-0 group-hover/cover:opacity-100 focus-within:opacity-100 has-[[data-state=open]]:opacity-100">
        <CoverMenu
          align="end"
          onPick={setCover}
          onUpload={upload.choose}
          trigger={<Button size="sm">{t("page.cover.change")}</Button>}
        />
        <Button size="sm" onClick={() => setCover(null)}>
          {t("page.cover.remove")}
        </Button>
      </div>
    </div>
  );
}

/**
 * Above the title: the node's emoji, which opens the picker, and on hover over the header "Adicionar ícone" and
 * "Adicionar capa" for what it lacks. Rendered inside a `group/header` box.
 */
export function HeaderDecor({ node }: { node: NodeDetail }) {
  const { t } = useI18n();
  const errorText = useErrorText();
  const decorate = useDecorateNode();
  const upload = useCoverUpload(node.id);
  const [picking, setPicking] = useState(false);
  const close = useCallback(() => setPicking(false), []);

  const setIcon = (icon: string | null) => {
    setPicking(false);
    decorate.mutate({ nodeId: node.id, icon });
  };
  const picker = picking && (
    <EmojiPicker onPick={setIcon} onRemove={node.icon ? () => setIcon(null) : undefined} onClose={close} />
  );

  return (
    <>
      {node.icon && (
        // Over the cover's lower edge, as in Notion: the column's top padding plus half the icon.
        <div className={cx("w-fit", node.cover && "-mt-[78px]")}>
          <button
            type="button"
            aria-label={t("page.icon.change")}
            onClick={() => setPicking(!picking)}
            className="flex size-[76px] cursor-pointer items-center justify-center rounded-[10px] border-0 bg-transparent p-0 text-[56px] leading-none hover:bg-subtle"
          >
            {node.icon}
          </button>
          {picker}
        </div>
      )}
      {(!node.icon || !node.cover) && (
        <div
          className={cx(
            "-ml-1.5 flex gap-1 opacity-0 group-hover/header:opacity-100 focus-within:opacity-100 has-[[data-state=open]]:opacity-100",
            picking && "opacity-100",
          )}
        >
          {!node.icon && (
            <>
              <button type="button" onClick={() => setPicking(!picking)} className={quietClass}>
                {t("page.icon.add")}
              </button>
              {picker}
            </>
          )}
          {!node.cover && (
            <CoverMenu
              align="start"
              onPick={(cover) => decorate.mutate({ nodeId: node.id, cover })}
              onUpload={upload.choose}
              trigger={
                <button type="button" className={quietClass}>
                  {t("page.cover.add")}
                </button>
              }
            />
          )}
        </div>
      )}
      {upload.input}
      {(upload.error || decorate.error) && (
        <p role="alert" className="m-0 mt-1 text-12 text-err">
          {upload.error || errorText(decorate.error)}
        </p>
      )}
    </>
  );
}
