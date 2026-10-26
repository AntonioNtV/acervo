import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import type { NodeDetail } from "../../api/client";
import { useErrorText } from "../../app/errors";
import { useMe } from "../../data/account";
import { useFavorite } from "../../data/favorites";
import { useFollowPage } from "../../data/pages";
import { useDuplicateNode, useExportNode, useTrashNode } from "../../data/tree";
import { useI18n } from "../../i18n";
import { Icon } from "../../ui/Icon";
import { IconButton } from "../../ui/IconButton";
import { Menu, MenuItem, MenuSeparator } from "../../ui/Menu";
import { useStartUpload } from "../base/Upload";
import { MovePicker } from "./MovePicker";

const NOTICE_MS = 2000;

/**
 * The page's ⋯: favorite, follow, duplicate, move, copy link, history, export, upload and trash; without `canEdit` (a Leitor)
 * only what changes nothing. `flush` sends the text still being typed, so a copy, a move or an export has it.
 */
export function PageMenu({
  node,
  canEdit = true,
  flush,
  onHistory,
}: {
  node: NodeDetail;
  canEdit?: boolean;
  flush: () => Promise<unknown>;
  onHistory: () => void;
}) {
  const { t } = useI18n();
  const navigate = useNavigate();
  const errorText = useErrorText();
  const kbId = node.kb_id;
  const favorite = useFavorite();
  const follow = useFollowPage(node.id);
  const digestOn = useMe().data?.preferences.notify_followed;
  const following = node.page?.following ?? false;
  const duplicate = useDuplicateNode();
  const exportNode = useExportNode();
  const trash = useTrashNode();
  const startUpload = useStartUpload(kbId);
  const fileInput = useRef<HTMLInputElement>(null);
  const [moving, setMoving] = useState(false);
  const [notice, setNotice] = useState<ReactNode>(null);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    // A notice with a link (Notificações) stays until the next action, so the keyboard can reach it.
    if (typeof notice !== "string") return;
    const timer = setTimeout(() => setNotice(null), NOTICE_MS);
    return () => clearTimeout(timer);
  }, [notice]);

  const run = (action: () => Promise<unknown>) => {
    setError(null);
    action().catch(setError);
  };

  const movePage = () =>
    run(async () => {
      await flush();
      setMoving(true);
    });

  const duplicatePage = () =>
    run(async () => {
      await flush();
      const copy = await duplicate.mutateAsync(node.id);
      navigate(`/kbs/${copy.kb_id}/n/${copy.id}`);
    });

  const copyLink = () =>
    run(async () => {
      await navigator.clipboard.writeText(`${window.location.origin}/kbs/${kbId}/n/${node.id}`);
      setNotice(t("page.link.copied"));
    });

  const toggleFollow = () =>
    run(async () => {
      await follow.mutateAsync(!following);
      if (following) return;
      setNotice(
        digestOn ? (
          t("page.followed")
        ) : (
          <>
            {t("page.followed.off")}{" "}
            <Link to="/conta/notificacoes" className="text-text-2 hover:text-text">
              {t("page.followed.offLink")}
            </Link>
            .
          </>
        ),
      );
    });

  const exportPage = () =>
    run(async () => {
      await flush();
      window.location.assign(await exportNode.mutateAsync(node.id));
    });

  const trashPage = () =>
    run(async () => {
      await trash.mutateAsync(node.id);
      navigate(node.parent_id ? `/kbs/${kbId}/n/${node.parent_id}` : `/kbs/${kbId}`);
    });

  return (
    <>
      {notice && (
        <span role="status" className="px-1 text-12 text-text-3">
          {notice}
        </span>
      )}
      {error !== null && (
        <span role="alert" className="px-1 text-12 text-err">
          {errorText(error)}
        </span>
      )}
      <input
        ref={fileInput}
        type="file"
        multiple
        hidden
        aria-label={t("page.upload")}
        onChange={(event) => {
          startUpload(Array.from(event.target.files ?? []), node.id);
          event.target.value = "";
        }}
      />
      <Menu
        trigger={
          <IconButton aria-label={t("page.more")}>
            <Icon name="more" />
          </IconButton>
        }
      >
        <MenuItem onSelect={() => run(() => favorite.mutateAsync({ nodeId: node.id, favorite: !node.favorite }))}>
          {t(node.favorite ? "shell.favorite.remove" : "shell.favorite.add")}
        </MenuItem>
        <MenuItem onSelect={toggleFollow}>{t(following ? "page.unfollow" : "page.follow")}</MenuItem>
        {canEdit && <MenuItem onSelect={duplicatePage}>{t("page.duplicate")}</MenuItem>}
        {canEdit && <MenuItem onSelect={movePage}>{t("page.move")}</MenuItem>}
        <MenuItem onSelect={copyLink}>{t("page.link.copy")}</MenuItem>
        <MenuSeparator />
        <MenuItem onSelect={onHistory}>{t("page.history")}</MenuItem>
        <MenuItem onSelect={exportPage}>{t("page.export")}</MenuItem>
        {canEdit && (
          <>
            <MenuItem onSelect={() => fileInput.current?.click()}>{t("page.upload")}</MenuItem>
            <MenuSeparator />
            <MenuItem onSelect={trashPage}>
              <span className="text-err">{t("page.trash")}</span>
            </MenuItem>
          </>
        )}
      </Menu>
      {moving && <MovePicker node={node} onClose={() => setMoving(false)} />}
    </>
  );
}
