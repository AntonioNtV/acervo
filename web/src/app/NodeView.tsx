import { FileView } from "../features/pdf/FileView";
import { PageView } from "../features/page/PageView";

// TODO(card 06+): pick PageView or FileView from the node's kind once api/queries.ts exists.
export function NodeView() {
  return (
    <>
      <PageView />
      <FileView />
    </>
  );
}
