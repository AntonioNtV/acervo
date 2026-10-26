import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { KbSummary } from "../../api/client";
import { forgetBase } from "../../app/lastPage";
import { useAccess } from "../../data/access";
import { useKbIcon, useTrashKb } from "../../data/kbs";
import { useI18n } from "../../i18n";
import { EmojiPicker } from "../../ui/EmojiPicker";
import { Icon } from "../../ui/Icon";
import { IconButton } from "../../ui/IconButton";
import { Menu, MenuItem, MenuSeparator } from "../../ui/Menu";
import { NodeIcon } from "../../ui/NodeIcon";
import type { BaseEdit } from "../bases/BaseDialog";
import { UploadList } from "../base/Upload";
import { ShareDialog } from "./ShareDialog";
import { useCurrent } from "./shell";
import { TreeRows, type Draft } from "./TreeRows";

const OPEN_KEY = "acervo.openBases";

function readOpen(): string[] {
  try {
    return JSON.parse(localStorage.getItem(OPEN_KEY) ?? "[]") as string[];
  } catch {
    return [];
  }
}

function storeOpen(kbId: string, open: boolean) {
  try {
    const others = readOpen().filter((id) => id !== kbId);
    localStorage.setItem(OPEN_KEY, JSON.stringify(open ? [...others, kbId] : others));
  } catch {
    // The section still opens and closes for this session.
  }
}

/** One base in the sidebar: its name with a menu and "+", then its tree while open. */
export function BaseSection({ kb, onEdit }: { kb: KbSummary; onEdit: (edit: BaseEdit) => void }) {
  const { t } = useI18n();
  const navigate = useNavigate();
  const current = useCurrent();
  const here = current.kbId === kb.id;
  const [open, setOpenState] = useState(() => here || readOpen().includes(kb.id));
  const [draft, setDraft] = useState<Draft | null>(null);
  const trash = useTrashKb();
  const icon = useKbIcon(kb);
  const { canEdit, canManage } = useAccess(kb.id);
  const [sharing, setSharing] = useState(false);

  const setOpen = (next: boolean) => {
    setOpenState(next);
    storeOpen(kb.id, next);
  };

  // Landing in a base from a link or from `/` opens its section.
  useEffect(() => {
    if (here) setOpenState(true);
  }, [here, current.nodeId]);

  const startDraft = (next: Draft) => {
    setOpen(true);
    setDraft(next);
  };

  return (
    <section aria-label={kb.name} className="mt-3.5 flex flex-col gap-px first-of-type:mt-3">
      <div className="group flex h-[26px] items-center justify-between gap-1 rounded-[6px] px-2 text-12 font-medium text-text-3">
        <button
          type="button"
          aria-expanded={open}
          onClick={() => setOpen(!open)}
          className="flex min-w-0 flex-1 cursor-pointer items-center gap-1.5 border-0 bg-transparent p-0 text-left font-medium text-text-3 hover:text-text"
        >
          <NodeIcon icon={kb.icon} size={14} />
          <span className="truncate">{kb.name}</span>
        </button>
        {icon.picking && <EmojiPicker onPick={icon.pick} onRemove={icon.remove} onClose={icon.close} />}
        {sharing && <ShareDialog kb={kb} onClose={() => setSharing(false)} />}
        {canEdit && (
          <span className="flex opacity-0 group-focus-within:opacity-100 group-hover:opacity-100 has-[[data-state=open]]:opacity-100">
            <Menu
              trigger={
                <IconButton size="sm" aria-label={t("shell.base.actions", { name: kb.name })}>
                  <Icon name="more" size={14} />
                </IconButton>
              }
            >
              {kb.my_role === "admin" && <MenuItem onSelect={() => setSharing(true)}>{t("sharing.share")}</MenuItem>}
              {canManage && (
                <>
                  <MenuItem onSelect={() => onEdit({ mode: "rename", kb })}>{t("bases.rename")}</MenuItem>
                  <MenuItem onSelect={() => onEdit({ mode: "describe", kb })}>{t("bases.describe")}</MenuItem>
                  <MenuItem onSelect={icon.open}>{t("bases.icon")}</MenuItem>
                </>
              )}
              <MenuItem onSelect={() => startDraft({ parentId: null, kind: "folder" })}>
                {t("base.new.folder")}
              </MenuItem>
              {canManage && (
                <>
                  <MenuSeparator />
                  <MenuItem
                    onSelect={() =>
                      trash.mutate(kb.id, {
                        onSuccess: () => {
                          forgetBase(kb.id);
                          if (here) navigate("/");
                        },
                      })
                    }
                  >
                    {t("bases.trash")}
                  </MenuItem>
                </>
              )}
            </Menu>
            <IconButton
              size="sm"
              aria-label={t("shell.base.newPage", { name: kb.name })}
              onClick={() => startDraft({ parentId: null, kind: "page" })}
            >
              <Icon name="plus" size={14} />
            </IconButton>
          </span>
        )}
      </div>
      {open && (
        <>
          <TreeRows kbId={kb.id} selectedId={here ? current.nodeId : undefined} draft={draft} onDraft={setDraft} />
          <UploadList kbId={kb.id} />
        </>
      )}
    </section>
  );
}
