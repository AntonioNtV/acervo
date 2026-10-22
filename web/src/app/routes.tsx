import type { RouteObject } from "react-router-dom";
import { BasesPage } from "../screens/bases/BasesPage";
import { TrashPage } from "../screens/bases/TrashPage";
import { BaseFrame } from "./BaseFrame";
import { IndexFrame } from "./IndexFrame";
import { BaseRootView } from "../screens/base/FolderView";
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
