import { useState } from "react";
import { Navigate } from "react-router-dom";
import { useKbs } from "../data/kbs";
import { useChildren } from "../data/tree";
import { useI18n } from "../i18n";
import { BaseDialog } from "../screens/bases/BaseDialog";
import { TopBar } from "../screens/shell/TopBar";
import { Button } from "../ui/Button";
import { useErrorText } from "./errors";
import { readLastPage } from "./lastPage";

function FirstNode({ kbId }: { kbId: string }) {
  const children = useChildren(kbId);
  if (children.isPending) return null;
  const first = children.data?.[0];
  return <Navigate replace to={first ? `/kbs/${kbId}/n/${first.id}` : `/kbs/${kbId}`} />;
}

/** `/`: the last page seen in this browser, else the first base's first node, else the offer of a first base. */
export function Home() {
  const { t } = useI18n();
  const kbs = useKbs();
  const errorText = useErrorText();
  const [creating, setCreating] = useState(false);
  const last = readLastPage();
  if (last) return <Navigate replace to={last} />;
  if (kbs.isError) return <p className="m-0 p-10 text-err">{errorText(kbs.error)}</p>;
  if (!kbs.data) return null;
  const first = kbs.data[0];
  if (first) return <FirstNode kbId={first.id} />;
  return (
    <>
      <TopBar />
      <div className="flex flex-1 flex-col items-center justify-center gap-4 p-10 text-center">
        <p className="m-0 text-text-3">{t("bases.empty")}</p>
        <Button variant="ink" onClick={() => setCreating(true)}>
          {t("bases.new")}
        </Button>
      </div>
      {creating && <BaseDialog edit={{ mode: "create" }} onClose={() => setCreating(false)} />}
    </>
  );
}
