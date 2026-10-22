import type { RouteObject } from "react-router-dom";
import { BaseRootScreen } from "../screens/folder/FolderScreen";
import { Lixeira } from "../screens/shell/Lixeira";
import { Home } from "./Home";
import { NodeView } from "./NodeView";
import { ShellFrame } from "./ShellFrame";

export const routes: RouteObject[] = [
  {
    element: <ShellFrame />,
    children: [
      { path: "/", element: <Home /> },
      { path: "/lixeira", element: <Lixeira /> },
      { path: "/kbs/:kbId", element: <BaseRootScreen /> },
      { path: "/kbs/:kbId/n/:nodeId", element: <NodeView /> },
    ],
  },
];
