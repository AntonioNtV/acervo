import "@testing-library/jest-dom/vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { calls, renderWithApi, resetApi, respond } from "../../api/testing";
import type { Member, Organization } from "../../data/orgSettings";
import { OrgMembers } from "./OrgMembers";
import { OrgSettings } from "./SettingsFrame";
import { signedIn } from "./testing";

vi.mock("../../api/client", () => import("../../api/testing").then((m) => m.mockClient()));

const ORG = "/v1/organizations/org-1";

beforeEach(() => {
  localStorage.clear();
  resetApi();
});

function member(account_id: string, name: string, role: Member["role"]): Member {
  return { account_id, name, email: `${name.split(" ")[0]!.toLowerCase()}@segura.com.br`, photo_url: null, role };
}

/** Antonio, Owner of Seguros SA (the current organization), with `members` and one pending invite. */
function renderMembers(members: Member[]) {
  signedIn();
  const organizations: Organization[] = [
    { id: "pessoal", name: "Pessoal", logo_url: null, my_role: "owner", new_base_access: "editor", require_two_factor: false, personal: true },
    { id: "org-1", name: "Seguros SA", logo_url: null, my_role: "owner", new_base_access: "editor", require_two_factor: false, personal: false },
  ];
  localStorage.setItem("acervo.org", "org-1");
  respond("GET", "/v1/organizations", { body: organizations });
  respond("GET", `${ORG}/members`, { body: members });
  respond("GET", `${ORG}/invites`, {
    body: [
      {
        id: "inv-1",
        email: "julia@corretora.com",
        role: "member",
        kb_id: null,
        created_at: new Date().toISOString(),
        expires_at: new Date(Date.now() + 5 * 24 * 60 * 60 * 1000 - 60_000).toISOString(),
      },
    ],
  });
  renderWithApi(
    <MemoryRouter initialEntries={["/organizacao/membros"]}>
      <Routes>
        <Route element={<OrgSettings />}>
          <Route path="/organizacao/membros" element={<OrgMembers />} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

const row = async (text: string) => (await screen.findByText(text)).closest<HTMLElement>(".border-b")!;

describe("OrgMembers", () => {
  it("changes a member's role at once", async () => {
    renderMembers([member("acc-1", "Antonio Bertino", "owner"), member("acc-2", "Rafael Nunes", "member")]);
    respond("PATCH", `${ORG}/members/acc-2`, { body: member("acc-2", "Rafael Nunes", "admin") });

    await userEvent.click(within(await row("Rafael Nunes")).getByRole("button", { name: "Papel: Membro" }));
    await userEvent.click(await screen.findByRole("menuitemradio", { name: /^Admin/ }));

    await waitFor(() =>
      expect(calls.find((call) => call.method === "PATCH")).toMatchObject({
        path: `${ORG}/members/acc-2`,
        body: { role: "admin" },
      }),
    );
  });

  it("the last Owner's role cannot be changed", async () => {
    renderMembers([member("acc-1", "Antonio Bertino", "owner"), member("acc-2", "Rafael Nunes", "member")]);

    const you = await row("Antonio Bertino");

    expect(within(you).getByText("(você)")).toBeInTheDocument();
    expect(within(you).getByText("Owner")).toBeInTheDocument();
    expect(within(you).queryByRole("button", { name: /^Papel/ })).not.toBeInTheDocument();
  });

  it("invites emails typed as chips, all with one role", async () => {
    renderMembers([member("acc-1", "Antonio Bertino", "owner")]);
    respond("POST", `${ORG}/invites`, { status: 201, body: [] });

    await userEvent.click(await screen.findByRole("button", { name: "Convidar" }));
    const dialog = await screen.findByRole("dialog", { name: "Convidar para Seguros SA" });
    await userEvent.type(within(dialog).getByLabelText("Emails"), "marina@segura.com.br, rafael@segura.com.br{Enter}");
    await userEvent.click(within(dialog).getByRole("button", { name: "Papel: Membro" }));
    await userEvent.click(await screen.findByRole("menuitemradio", { name: /^Admin/ }));
    await userEvent.click(within(dialog).getByRole("button", { name: "Convidar 2 pessoas" }));

    await waitFor(() =>
      expect(calls.find((call) => call.method === "POST")).toMatchObject({
        path: `${ORG}/invites`,
        body: { emails: ["marina@segura.com.br", "rafael@segura.com.br"], role: "admin" },
      }),
    );
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("a pending invite is resent or revoked", async () => {
    renderMembers([member("acc-1", "Antonio Bertino", "owner")]);
    respond("POST", "/v1/invites/inv-1/resend", { body: {} });
    respond("DELETE", "/v1/invites/inv-1", { status: 204, body: undefined });

    const invite = await row("julia@corretora.com");
    expect(within(invite).getByText("Convite pendente · vence em 5 dias")).toBeInTheDocument();
    expect(screen.getByText("1 convite pendente.")).toBeInTheDocument();

    await userEvent.click(within(invite).getByRole("button", { name: "Reenviar" }));
    await waitFor(() => expect(calls.some((call) => call.path === "/v1/invites/inv-1/resend")).toBe(true));

    await userEvent.click(within(invite).getByRole("button", { name: "Papel: Membro" }));
    await userEvent.click(await screen.findByRole("menuitem", { name: "Remover acesso" }));
    await waitFor(() =>
      expect(calls.some((call) => call.method === "DELETE" && call.path === "/v1/invites/inv-1")).toBe(true),
    );
  });
});
