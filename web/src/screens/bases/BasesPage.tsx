import { useState } from "react";
import { Link } from "react-router-dom";
import type { KbSummary } from "../../api/client";
import { useKbIcon, useKbs, useTrashKb } from "../../data/kbs";
import { useI18n } from "../../i18n";
import { Button } from "../../ui/Button";
import { cx } from "../../ui/cx";
import { EmojiPicker } from "../../ui/EmojiPicker";
import { Icon } from "../../ui/Icon";
import { Menu, MenuItem, MenuSeparator } from "../../ui/Menu";
import { NodeIcon } from "../../ui/NodeIcon";
import { TopBar } from "../shell/TopBar";
import { BaseDialog, type BaseEdit } from "./BaseDialog";
import { fullDate, relativeTime } from "./when";

const card = "flex min-h-[176px] flex-col gap-3.5 rounded-[10px] border border-line-2 p-5";

function fold(text: string): string {
  return text.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase();
}

function BaseCard({ kb, onEdit }: { kb: KbSummary; onEdit: (edit: BaseEdit) => void }) {
  const { t, lang } = useI18n();
  const trash = useTrashKb();
  const icon = useKbIcon(kb);
  const count = (key: string, n: number) => t(`bases.${key}.${n === 1 ? "one" : "other"}`, { n });

  return (
    <article className={cx(card, "relative hover:border-text-3")}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <Link
            to={`/kbs/${kb.id}`}
            className={cx(
              "inline-flex items-center gap-2 text-15 font-medium tracking-[-0.01em] text-text no-underline",
              "after:absolute after:inset-0 after:rounded-[10px]",
            )}
          >
            <NodeIcon icon={kb.icon} size={18} />
            {kb.name}
          </Link>
          {icon.picking && <EmojiPicker onPick={icon.pick} onRemove={icon.remove} onClose={icon.close} />}
        </div>
        <Menu
          trigger={
            <Button
              variant="quiet"
              size="sm"
              icon
              aria-label={t("bases.actions", { name: kb.name })}
              className="relative -mt-1 -mr-2"
            >
              <Icon name="more" />
            </Button>
          }
        >
          <MenuItem onSelect={() => onEdit({ mode: "rename", kb })}>{t("bases.rename")}</MenuItem>
          <MenuItem onSelect={() => onEdit({ mode: "describe", kb })}>{t("bases.describe")}</MenuItem>
          <MenuItem onSelect={icon.open}>{t("bases.icon")}</MenuItem>
          <MenuSeparator />
          <MenuItem onSelect={() => trash.mutate(kb.id)}>{t("bases.trash")}</MenuItem>
        </Menu>
      </div>
      {kb.description && <p className="m-0 text-text-3">{kb.description}</p>}
      <div className="mt-auto flex items-center justify-between gap-3 text-12 text-text-3 tabular-nums">
        <span>
          {count("pages", kb.pages)} · {count("files", kb.files)}
        </span>
        <time dateTime={kb.last_edit} title={fullDate(kb.last_edit, lang)}>
          {relativeTime(kb.last_edit, lang)}
        </time>
      </div>
    </article>
  );
}

export function BasesPage() {
  const { t } = useI18n();
  const kbs = useKbs();
  const [filter, setFilter] = useState("");
  const [edit, setEdit] = useState<BaseEdit | null>(null);
  const shown = (kbs.data ?? []).filter((kb) => fold(kb.name).includes(fold(filter.trim())));
  const create = () => setEdit({ mode: "create" });

  return (
    <>
      <TopBar label={t("bases.title")} />
      <div className="mx-auto w-full max-w-[1040px] px-8 pt-14 pb-16">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <h1 className="m-0 text-32 leading-[38px] font-medium tracking-[-0.035em]">
            {t("bases.title")} {kbs.data && <span className="text-ghost">{kbs.data.length}</span>}
          </h1>
          <Button variant="ink" onClick={create}>
            {t("bases.new")}
          </Button>
        </div>

        <div className="mt-10 mb-4 flex justify-end">
          <label className="flex h-[30px] w-60 items-center gap-2 text-text-3">
            <svg
              viewBox="0 0 24 24"
              aria-hidden="true"
              className="size-[15px] shrink-0 fill-none stroke-current stroke-[1.5]"
            >
              <circle cx="11" cy="11" r="7" />
              <path d="m20 20-3.5-3.5" />
            </svg>
            <input
              type="search"
              aria-label={t("bases.filter")}
              placeholder={t("bases.filter.placeholder")}
              value={filter}
              onChange={(event) => setFilter(event.target.value)}
              className="min-w-0 flex-1 border-0 bg-transparent text-13 text-text outline-none placeholder:text-ghost"
            />
          </label>
        </div>

        {kbs.isPending ? (
          <p className="m-0 text-text-3">{t("bases.loading")}</p>
        ) : kbs.isError ? (
          <div className="flex items-center gap-3">
            <p role="alert" className="m-0 text-err">
              {t("bases.error.load")}
            </p>
            <Button size="sm" onClick={() => kbs.refetch()}>
              {t("bases.retry")}
            </Button>
          </div>
        ) : (
          <>
            {shown.length === 0 && (
              <p className="m-0 mb-4 text-text-3">{t(filter.trim() ? "bases.empty.filter" : "bases.empty")}</p>
            )}
            <div className="grid grid-cols-[repeat(auto-fill,minmax(280px,1fr))] gap-4">
              {shown.map((kb) => (
                <BaseCard key={kb.id} kb={kb} onEdit={setEdit} />
              ))}
              <button
                type="button"
                onClick={create}
                className={cx(
                  card,
                  "cursor-pointer items-center justify-center border-dashed bg-transparent hover:border-text-3",
                  "text-15 font-medium tracking-[-0.01em] text-text-2",
                )}
              >
                {t("bases.new")}
              </button>
            </div>
          </>
        )}

        {edit && <BaseDialog key={edit.mode} edit={edit} onClose={() => setEdit(null)} />}
      </div>
    </>
  );
}
