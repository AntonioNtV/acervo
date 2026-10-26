import "@testing-library/jest-dom/vitest";
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { calls, renderWithApi, resetApi, respond } from "../../api/testing";
import type { Member, Organization } from "../../data/orgSettings";
import { OrgGeneral } from "./OrgGeneral";
import { OrgSettings } from "./SettingsFrame";
import { signedIn } from "./testing";

vi.mock("../../api/client", () => import("../../api/testing").then((m) => m.mockClient()));

beforeEach(() => {
  localStorage.clear();
  resetApi();
});

/** Antonio in Seguros SA with `role`, at `path`; the rail's choice is already Seguros SA unless `chosen` is null. */
function renderOrg(role: Organization["my_role"], path: string, chosen: string | null = "org-1") {
  signedIn();
  const organizations: Organization[] = [
    { id: "pessoal", name: "Pessoal", logo_url: null, my_role: "owner", new_base_access: "editor", require_two_factor: false, personal: true },
    { id: "org-1", name: "Seguros SA", logo_url: null, my_role: role, new_base_access: "editor", require_two_factor: false, personal: false },
  ];
  if (chosen) localStorage.setItem("acervo.org", chosen);
  respond("GET", "/v1/organizations", { body: organizations });
  renderWithApi(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route element={<OrgSettings />}>
          <Route path="/organizacao/geral" element={<OrgGeneral />} />
          <Route path="/organizacao/membros" element={<p>Lista de membros</p>} />
        </Route>
        <Route path="/bases" element={<p>Bases</p>} />
        <Route path="/conta/perfil" element={<p>Perfil</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

const owner = (account_id: string, name: string): Member => ({
  account_id,
  name,
  email: `${account_id}@segura.com.br`,
  photo_url: null,
  role: "owner",
});

describe("OrgGeneral", () => {
  it("the invite_accepted link opens the organization it names, whatever the rail had", async () => {
    renderOrg("admin", "/organizacao/membros?org=org-1", null);

    expect(await screen.findByText("Lista de membros")).toBeInTheDocument();
    expect(localStorage.getItem("acervo.org")).toBe("org-1");
  });

  it("a Membro sees Geral read-only and leaves to the Pessoal", async () => {
    renderOrg("member", "/organizacao/membros");
    respond("POST", "/v1/organizations/org-1/leave", { status: 204, body: undefined });

    expect(await screen.findByLabelText("Nome")).toHaveAttribute("readonly");
    expect(screen.queryByRole("button", { name: /Enviar logo/ })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Sair" }));
    await userEvent.click(within(await screen.findByRole("dialog", { name: "Sair de Seguros SA?" })).getByRole("button", { name: "Sair" }));

    expect(await screen.findByText("Bases")).toBeInTheDocument();
    expect(calls.some((call) => call.method === "POST" && call.path === "/v1/organizations/org-1/leave")).toBe(true);
    expect(localStorage.getItem("acervo.org")).toBeNull();
  });

  it("its last Owner cannot leave and reads why", async () => {
    renderOrg("owner", "/organizacao/geral");
    respond("GET", "/v1/organizations/org-1/members", { body: [owner("acc-1", "Antonio Bertino")] });

    expect(await screen.findByText(/Você é o único Owner/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sair" })).toBeDisabled();
  });

  it("an Admin does not see Excluir organização", async () => {
    renderOrg("admin", "/organizacao/geral");

    expect(await screen.findByLabelText("Nome")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Excluir organização" })).not.toBeInTheDocument();
  });
});
