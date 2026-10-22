import { useParams } from "react-router-dom";
import { ApiError } from "../data/request";
import { useNode } from "../data/tree";
import { FileView } from "../screens/file/FileView";
import { PageView } from "../screens/page/PageView";
import { FolderView } from "../screens/base/FolderView";
import { useErrorText } from "./errors";

export function NodeView() {
  const { nodeId = "" } = useParams();
  const node = useNode(nodeId);
  const errorText = useErrorText();
  // A failed background refetch keeps what is open; only a node that is gone replaces it.
  const gone = node.error instanceof ApiError && node.error.code === "not_found";
  if (node.error && (gone || !node.data)) return <p className="m-0 p-10 text-err">{errorText(node.error)}</p>;
  if (!node.data) return null;
  if (node.data.kind === "page") return <PageView key={node.data.id} node={node.data} />;
  if (node.data.kind === "file") return <FileView key={node.data.id} node={node.data} />;
  return <FolderView node={node.data} />;
}
