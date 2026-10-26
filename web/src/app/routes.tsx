import type { RouteObject } from "react-router-dom";
import { LinkGoogle } from "../screens/auth/LinkGoogle";
import { NewPassword, ResetRequest } from "../screens/auth/Reset";
import { SignIn } from "../screens/auth/SignIn";
import { SignUp } from "../screens/auth/SignUp";
import { VerifyEmail } from "../screens/auth/VerifyEmail";
import { BasesPage } from "../screens/bases/BasesPage";
import { BaseRootScreen } from "../screens/folder/FolderScreen";
import { Lixeira } from "../screens/shell/Lixeira";
import { Home } from "./Home";
import { NodeView } from "./NodeView";
import { RequireAccount } from "./RequireAccount";
import { ShellFrame } from "./ShellFrame";

export const routes: RouteObject[] = [
  { path: "/entrar", element: <SignIn /> },
  { path: "/entrar/vincular", element: <LinkGoogle /> },
  { path: "/criar-conta", element: <SignUp /> },
  { path: "/confirmar-email", element: <VerifyEmail /> },
  { path: "/redefinir-senha", element: <ResetRequest /> },
  { path: "/redefinir-senha/:token", element: <NewPassword /> },
  {
    element: <RequireAccount />,
    children: [
      {
        element: <ShellFrame />,
        children: [
          { path: "/", element: <Home /> },
          { path: "/bases", element: <BasesPage /> },
          { path: "/lixeira", element: <Lixeira /> },
          { path: "/kbs/:kbId", element: <BaseRootScreen /> },
          { path: "/kbs/:kbId/n/:nodeId", element: <NodeView /> },
        ],
      },
    ],
  },
];
