import { useEffect } from "react";
import { useParams } from "react-router-dom";
import { ApiError } from "../data/request";
import { useNode } from "../data/tree";
import { FileView } from "../screens/file/FileView";
import { PageView } from "../screens/page/PageView";
import { FolderView } from "../screens/base/FolderView";
import { TopBar } from "../screens/shell/TopBar";
import { useErrorText } from "./errors";
import { rememberPage } from "./lastPage";

export function NodeView() {
  const { nodeId = "" } = useParams();
  const node = useNode(nodeId);
  const errorText = useErrorText();
  const kbId = node.data?.kb_id;
  useEffect(() => {
    if (kbId) rememberPage(kbId, nodeId);
  }, [kbId, nodeId]);
  // A failed background refetch keeps what is open; only a node that is gone replaces it.
  const gone = node.error instanceof ApiError && node.error.code === "not_found";
  if (node.error && (gone || !node.data)) return <p className="m-0 p-10 text-err">{errorText(node.error)}</p>;
  if (!node.data) return null;
  let screen;
  if (node.data.kind === "page") screen = <PageView key={node.data.id} node={node.data} />;
  else if (node.data.kind === "file") screen = <FileView key={node.data.id} node={node.data} />;
  else screen = <FolderView node={node.data} />;
  // Until the folder, file and page screens bring their own TopBar (cards 05 and 06), the shell puts a plain one here.
  return (
    <>
      <TopBar kbId={node.data.kb_id} nodeId={node.data.id} />
      {screen}
    </>
  );
}
