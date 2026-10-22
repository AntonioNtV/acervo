import type { RouteObject } from "react-router-dom";
import { useParams } from "react-router-dom";
import { BaseRootView } from "../screens/base/FolderView";
import { Lixeira } from "../screens/shell/Lixeira";
import { TopBar } from "../screens/shell/TopBar";
import { Home } from "./Home";
import { NodeView } from "./NodeView";
import { ShellFrame } from "./ShellFrame";

function BaseRoot() {
  const { kbId = "" } = useParams();
  return (
    <>
      <TopBar kbId={kbId} />
      <BaseRootView />
    </>
  );
}

export const routes: RouteObject[] = [
  {
    element: <ShellFrame />,
    children: [
      { path: "/", element: <Home /> },
      { path: "/lixeira", element: <Lixeira /> },
      { path: "/kbs/:kbId", element: <BaseRoot /> },
      { path: "/kbs/:kbId/n/:nodeId", element: <NodeView /> },
    ],
  },
];
