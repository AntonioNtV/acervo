import type { RouteObject } from "react-router-dom";
import { BasesPage } from "../features/bases/BasesPage";
import { TrashPage } from "../features/bases/TrashPage";
import { BaseFrame } from "./BaseFrame";
import { IndexFrame } from "./IndexFrame";
import { BaseRootView } from "../features/tree/FolderView";
import { NodeView } from "./NodeView";

export const routes: RouteObject[] = [
  {
    element: <IndexFrame />,
    children: [
      { path: "/", element: <BasesPage /> },
      { path: "/lixeira", element: <TrashPage /> },
    ],
  },
  {
    path: "/kbs/:kbId",
    element: <BaseFrame />,
    children: [
      { index: true, element: <BaseRootView /> },
      { path: "n/:nodeId", element: <NodeView /> },
    ],
  },
];
