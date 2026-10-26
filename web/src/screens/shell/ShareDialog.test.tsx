import "@testing-library/jest-dom/vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { components } from "../../api/schema.gen";
import { calls, renderWithApi, resetApi, respond } from "../../api/testing";
import { summary } from "../bases/testing";
import { ShareDialog } from "./ShareDialog";

vi.mock("../../api/client", () => import("../../api/testing").then((m) => m.mockClient()));

type Member = components["schemas"]["MemberRead"];
type Invite = components["schemas"]["InviteRead"];

const kb = summary({ id: "kb-1", name: "Seguros · Operação", organization_id: "org-1", my_role: "admin" });
const ana: Member = { account_id: "acc-ana", name: "Ana Souza", email: "ana@segura.com.br", photo_url: null, role: "admin" };

let members: Member[];
let invites: Invite[];
let general: "none" | "reader" | "editor";

beforeEach(() => {
  resetApi();
  members = [ana];
  invites = [];
  general = "editor";
  respond("GET", "/v1/organizations", {
    body: [
      { id: "org-1", name: "Seguros SA", personal: false, my_role: "admin", logo_url: null, new_base_access: "editor" },
    ],
  });
  respond("GET", "/v1/kbs/kb-1/access", () => ({ body: { general_access: general, members } }));
  respond("GET", "/v1/kbs/kb-1/invites", () => ({ body: invites }));
});

function renderDialog() {
  return renderWithApi(<ShareDialog kb={kb} onClose={() => {}} />);
}

async function addEmail(email: string) {
  await userEvent.type(await screen.findByRole("textbox", { name: "Adicionar pessoas por email" }), email);
  await userEvent.click(screen.getByRole("button", { name: "Adicionar" }));
}

describe("ShareDialog", () => {
  it("changes the general access to only the people added", async () => {
    respond("PUT", "/v1/kbs/kb-1/access", (_url, body) => {
      general = (body as { general_access: typeof general }).general_access;
      return { body: { general_access: general, members } };
    });
    renderDialog();

    expect(await screen.findByText("Todos de Seguros SA")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Acesso geral" }));
    await userEvent.click(await screen.findByRole("menuitemradio", { name: /^Só as pessoas adicionadas/ }));

    await waitFor(() =>
      expect(calls.find((call) => call.method === "PUT")).toMatchObject({
        path: "/v1/kbs/kb-1/access",
        body: { general_access: "none" },
      }),
    );
    expect(await screen.findByText("Só as pessoas adicionadas")).toBeInTheDocument();
  });

  it("adds a member of the organization by email with the role chosen", async () => {
    respond("POST", "/v1/kbs/kb-1/invites", () => {
      members = [...members, { account_id: "acc-bruno", name: "Bruno Lima", email: "bruno@segura.com.br", photo_url: null, role: "editor" }];
      return { status: 201, body: [] };
    });
    renderDialog();

    await addEmail("bruno@segura.com.br");

    expect(await screen.findByText("Bruno Lima")).toBeInTheDocument();
    expect(calls.find((call) => call.method === "POST")?.body).toEqual({ emails: ["bruno@segura.com.br"], role: "editor" });
    expect(screen.getByRole("textbox", { name: "Adicionar pessoas por email" })).toHaveValue("");
  });

  it("an email outside the organization becomes a pending invite", async () => {
    respond("POST", "/v1/kbs/kb-1/invites", () => {
      const invite: Invite = {
        id: "inv-1",
        email: "julia@outra.com",
        role: "editor",
        kb_id: "kb-1",
        created_at: new Date().toISOString(),
        expires_at: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString(),
      };
      invites = [invite];
      return { status: 201, body: [invite] };
    });
    renderDialog();

    await addEmail("julia@outra.com");

    expect(await screen.findByText("julia@outra.com")).toBeInTheDocument();
    expect(screen.getByText("Convite pendente · vence em 7 dias")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reenviar" })).toBeInTheDocument();
  });
});
