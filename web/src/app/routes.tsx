import type { RouteObject } from "react-router-dom";
import { BasesPage } from "../features/bases/BasesPage";
import { TrashPage } from "../features/bases/TrashPage";
import { BaseFrame } from "./BaseFrame";
import { IndexFrame } from "./IndexFrame";
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
    children: [{ path: "n/:nodeId", element: <NodeView /> }],
  },
];
