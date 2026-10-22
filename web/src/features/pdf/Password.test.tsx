import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import type { NodeDetail } from "../../api/queries";
import { I18nProvider } from "../../i18n";
import { FileView } from "./FileView";
import { openPdf, type OnPassword } from "./pdfjs";

// openapi-fetch keeps the `fetch` it finds when the client module loads.
const fetchMock = vi.hoisted(() => {
  const fn = vi.fn<typeof fetch>();
  globalThis.fetch = fn;
  return fn;
});
vi.mock("./pdfjs", () => ({ openPdf: vi.fn() }));

const NODE_ID = "22222222-2222-2222-2222-222222222222";
const PASSWORD = "s3gredo-da-apolice";

const node: NodeDetail = {
  id: NODE_ID,
  kb_id: "kb-1",
  parent_id: null,
  kind: "file",
  title: "Contrato.pdf",
  deleted_at: null,
  path: "Contrato.pdf",
  page: null,
  file: { size: 1000, mime: "application/pdf", pages: null, protected: true, sha256: "abc" },
  versions: 1,
};

async function requestText(input: RequestInfo | URL, init?: RequestInit): Promise<string> {
  const request = new Request(input, init);
  return [request.url, [...request.headers].join(), await request.text()].join(" ");
}

describe("a protected PDF", () => {
  it("asks its password in a dialog and hands it to pdf.js only", async () => {
    fetchMock.mockImplementation(async () => Response.json(node));
    const xhrOpen = vi.spyOn(XMLHttpRequest.prototype, "open");
    const xhrSend = vi.spyOn(XMLHttpRequest.prototype, "send");
    const submit = vi.fn();
    vi.mocked(openPdf).mockImplementation((_url, onPassword: OnPassword) => {
      onPassword(submit, false);
      return { promise: new Promise(() => {}), destroy: () => {} };
    });

    render(
      <QueryClientProvider client={new QueryClient()}>
        <I18nProvider>
          <MemoryRouter initialEntries={[`/kbs/kb-1/n/${NODE_ID}`]}>
            <Routes>
              <Route path="/kbs/:kbId/n/:nodeId" element={<FileView />} />
            </Routes>
          </MemoryRouter>
        </I18nProvider>
      </QueryClientProvider>,
    );

    const dialog = await screen.findByRole("dialog", { name: "Este PDF tem senha" });
    await userEvent.type(screen.getByLabelText("Senha"), PASSWORD);
    await userEvent.click(screen.getByRole("button", { name: "Abrir" }));

    expect(submit).toHaveBeenCalledWith(PASSWORD);
    expect(dialog).not.toBeInTheDocument();
    for (const [input, init] of fetchMock.mock.calls) expect(await requestText(input, init)).not.toContain(PASSWORD);
    expect(JSON.stringify(xhrOpen.mock.calls)).not.toContain(PASSWORD);
    expect(xhrSend).not.toHaveBeenCalled();
    expect(JSON.stringify({ ...localStorage })).not.toContain(PASSWORD);
  });
});
