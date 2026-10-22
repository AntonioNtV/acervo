import { useParams } from "react-router-dom";
import { useNode } from "../api/queries";
import { FileView } from "../features/pdf/FileView";
import { PageView } from "../features/page/PageView";
import { FolderView } from "../features/tree/FolderView";

export function NodeView() {
  const { nodeId = "" } = useParams();
  const node = useNode(nodeId);
  if (node.error) return <p className="m-0 p-10 text-err">{node.error.message}</p>;
  if (!node.data) return null;
  if (node.data.kind === "page") return <PageView />;
  if (node.data.kind === "file") return <FileView />;
  return <FolderView node={node.data} />;
}
