import "@testing-library/jest-dom/vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { calls, renderWithApi, resetApi, respond } from "../../api/testing";
import type { Organization } from "../../data/orgSettings";
import type { AuditEvent } from "../../data/sessions";
import { OrgAccess } from "./OrgAccess";
import OrgAudit from "./OrgAudit";
import { OrgSettings } from "./SettingsFrame";
import { signedIn } from "./testing";

vi.mock("../../api/client", () => import("../../api/testing").then((m) => m.mockClient()));

const ORG = "/v1/organizations/org-1";
const SEGUROS: Organization = {
  id: "org-1",
  name: "Seguros SA",
  logo_url: null,
  my_role: "owner",
  new_base_access: "editor",
  require_two_factor: false,
  personal: false,
};

beforeEach(() => {
  localStorage.clear();
  resetApi();
  vi.unstubAllGlobals();
});

function event(id: string, kind: AuditEvent["kind"], data: Record<string, unknown>): AuditEvent {
  const by = { actor_id: "acc-1", actor_name: "Antonio Bertino", actor_email: "antonio@segura.com.br" };
  return { id, kind, data, created_at: new Date().toISOString(), ...by };
}

/** Antonio, Owner of Seguros SA (the current organization), at `path`. */
function renderOrg(path: string) {
  signedIn();
  localStorage.setItem("acervo.org", "org-1");
  respond("GET", "/v1/organizations", { body: [SEGUROS] });
  renderWithApi(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route element={<OrgSettings />}>
          <Route path="/organizacao/auditoria" element={<OrgAudit />} />
          <Route path="/organizacao/acesso" element={<OrgAccess />} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

describe("OrgAudit", () => {
  it("lists who did what, by day", async () => {
    respond("GET", `${ORG}/audit`, {
      body: [
        event("e-1", "role_changed", { member: "rafael@segura.com.br", role: "admin", old_role: "member" }),
        event("e-2", "base_trashed", { base: "Jurídico antigo" }),
      ],
    });
    renderOrg("/organizacao/auditoria");

    expect(await screen.findByText("Hoje")).toBeInTheDocument();
    expect(screen.getByText("Antonio Bertino mudou rafael@segura.com.br de Membro para Admin")).toBeInTheDocument();
    const trashed = screen.getByText("Antonio Bertino mandou a base Jurídico antigo para a Lixeira");
    expect(within(trashed.closest<HTMLElement>(".border-b")!).getByText("Bases")).toBeInTheDocument();
  });

  it("exports the audit as CSV", async () => {
    respond("GET", `${ORG}/audit`, { body: [] });
    const assign = vi.fn();
    vi.stubGlobal("location", { ...window.location, assign });
    renderOrg("/organizacao/auditoria");

    await userEvent.click(await screen.findByRole("button", { name: "Exportar CSV" }));

    expect(assign).toHaveBeenCalledWith(`${ORG}/audit.csv`);
  });
});

describe("OrgAccess", () => {
  it("the requirement shows how many members sign in with a password only", async () => {
    respond("GET", ORG, { body: { ...SEGUROS, password_only: 3 } });
    respond("PATCH", ORG, { body: { ...SEGUROS, require_two_factor: true, password_only: 3 } });
    renderOrg("/organizacao/acesso");

    expect(await screen.findByText("3 membros ainda entram só com senha.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Exigir verificação em duas etapas" }));
    await userEvent.click(await screen.findByRole("menuitemradio", { name: "Exigida" }));

    await waitFor(() =>
      expect(calls.find((call) => call.method === "PATCH")).toMatchObject({ body: { require_two_factor: true } }),
    );
  });
});
