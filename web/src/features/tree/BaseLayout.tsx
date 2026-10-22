import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useKbs } from "../../api/queries";
import { useI18n } from "../../i18n";
import { Input } from "../../ui/Input";
import { Menu, MenuItem, MenuSeparator } from "../../ui/Menu";
import { Bin } from "./Bin";
import { SearchResults } from "./Search";
import { Tree } from "./Tree";
import { UploadList } from "./Upload";

function Switcher({ kbId }: { kbId: string }) {
  const { t } = useI18n();
  const navigate = useNavigate();
  const kbs = useKbs().data ?? [];
  const current = kbs.find((kb) => kb.id === kbId);
  return (
    <Menu
      trigger={
        <button
          type="button"
          aria-label={t("tree.switcher")}
          className="mb-2.5 flex h-8 cursor-pointer items-center justify-between border-0 bg-transparent px-2.5 text-13 font-medium text-text"
        >
          <span className="truncate">{current?.name}</span>
          <svg viewBox="0 0 24 24" width={15} height={15} aria-hidden="true" className="shrink-0 fill-none stroke-text-3 stroke-[1.5]">
            <path d="m7 15 5 5 5-5M7 9l5-5 5 5" />
          </svg>
        </button>
      }
    >
      {kbs
        .filter((kb) => kb.id !== kbId)
        .map((kb) => (
          <MenuItem key={kb.id} onSelect={() => navigate(`/kbs/${kb.id}`)}>
            {kb.name}
          </MenuItem>
        ))}
      {kbs.length > 1 && <MenuSeparator />}
      <MenuItem onSelect={() => navigate("/")}>{t("tree.switcher.all")}</MenuItem>
    </Menu>
  );
}

export function BaseLayout() {
  const { t } = useI18n();
  const { kbId = "", nodeId } = useParams();
  const [q, setQ] = useState("");
  return (
    <>
      <Switcher kbId={kbId} />
      <div className="mb-2 px-1">
        <Input type="search" aria-label={t("tree.search")} placeholder={t("tree.search")} value={q} onChange={(e) => setQ(e.target.value)} />
      </div>
      {q.trim() && <SearchResults kbId={kbId} q={q.trim()} onOpen={() => setQ("")} />}
      {/* Hidden, not unmounted, so the folders the person opened stay open after a search. */}
      <div hidden={q.trim() !== ""} className="flex flex-col">
        <Tree key={kbId} kbId={kbId} selectedId={nodeId} />
      </div>
      <UploadList kbId={kbId} />
      <div className="mt-3">
        <Bin kbId={kbId} />
      </div>
    </>
  );
}
