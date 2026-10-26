import type { RouteObject } from "react-router-dom";
import { Invite } from "../screens/auth/Invite";
import { LinkGoogle } from "../screens/auth/LinkGoogle";
import { NewPassword, ResetRequest } from "../screens/auth/Reset";
import { SignIn } from "../screens/auth/SignIn";
import { SignUp } from "../screens/auth/SignUp";
import { TwoFactor } from "../screens/auth/TwoFactor";
import { VerifyEmail } from "../screens/auth/VerifyEmail";
import { BasesPage } from "../screens/bases/BasesPage";
import { BaseRootScreen } from "../screens/folder/FolderScreen";
import Activity from "../screens/settings/Activity";
import { OrgAccess } from "../screens/settings/OrgAccess";
import OrgAudit from "../screens/settings/OrgAudit";
import { OrgBases } from "../screens/settings/OrgBases";
import { OrgGeneral } from "../screens/settings/OrgGeneral";
import { OrgMembers } from "../screens/settings/OrgMembers";
import { Preferences } from "../screens/settings/Preferences";
import { Profile } from "../screens/settings/Profile";
import { Security } from "../screens/settings/Security";
import Sessions from "../screens/settings/Sessions";
import { OrgSettings, SettingsFrame } from "../screens/settings/SettingsFrame";
import { AccountPreferences } from "../screens/settings/usePreferences";
import { Lixeira } from "../screens/shell/Lixeira";
import { Home } from "./Home";
import { NodeView } from "./NodeView";
import { RequireAccount } from "./RequireAccount";
import { ShellFrame } from "./ShellFrame";

export const routes: RouteObject[] = [
  { path: "/entrar", element: <SignIn /> },
  { path: "/entrar/vincular", element: <LinkGoogle /> },
  { path: "/entrar/codigo", element: <TwoFactor /> },
  { path: "/criar-conta", element: <SignUp /> },
  { path: "/confirmar-email", element: <VerifyEmail /> },
  { path: "/redefinir-senha", element: <ResetRequest /> },
  { path: "/redefinir-senha/:token", element: <NewPassword /> },
  { path: "/convite/:token", element: <Invite /> },
  {
    element: <RequireAccount />,
    children: [
      {
        element: <AccountPreferences />,
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
          {
            element: <SettingsFrame />,
            children: [
              { path: "/conta/perfil", element: <Profile /> },
              { path: "/conta/preferencias", element: <Preferences /> },
              { path: "/conta/seguranca", element: <Security /> },
              { path: "/conta/sessoes", element: <Sessions /> },
              { path: "/conta/atividade", element: <Activity /> },
              {
                element: <OrgSettings />,
                children: [
                  { path: "/organizacao/geral", element: <OrgGeneral /> },
                  { path: "/organizacao/membros", element: <OrgMembers /> },
                  { path: "/organizacao/acesso", element: <OrgAccess /> },
                  { path: "/organizacao/bases", element: <OrgBases /> },
                  { path: "/organizacao/auditoria", element: <OrgAudit /> },
                ],
              },
            ],
          },
        ],
      },
    ],
  },
];
