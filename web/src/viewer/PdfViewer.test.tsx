import "@testing-library/jest-dom/vitest";
import { screen, waitFor } from "@testing-library/react";
import type { NodeDetail } from "../api/client";
import { NodeView } from "../app/NodeView";
import { nodeFields, renderInBase, resetApi, respond } from "../api/testing";
import { openPdf, type PDFDocumentProxy } from "./pdfjs";

vi.mock("../api/client", () => import("../api/testing").then((m) => m.mockClient()));
vi.mock("./pdfjs", () => ({ openPdf: vi.fn() }));

const NODE_ID = "33333333-3333-3333-3333-333333333333";

const node: NodeDetail = {
  ...nodeFields,
  id: NODE_ID,
  kb_id: "kb-1",
  parent_id: null,
  kind: "file",
  title: "Condições Gerais 2026.pdf",
  deleted_at: null,
  path: "Condições Gerais 2026.pdf",
  page: null,
  file: { size: 1000, mime: "application/pdf", pages: 200, protected: false, sha256: "abc" },
  versions: 1,
};

/** A letter-size page whose viewport flips y as pdf.js does: user space starts at the bottom left. */
const letter = {
  view: [0, 0, 612, 792],
  getViewport: ({ scale }: { scale: number }) => ({
    width: 612 * scale,
    height: 792 * scale,
    convertToViewportPoint: (x: number, y: number) => [x * scale, (792 - y) * scale],
  }),
  render: () => ({ promise: Promise.resolve(), cancel: () => {} }),
};

describe("PdfViewer", () => {
  it("a citation's page and highlight open that page with the block's box drawn", async () => {
    resetApi();
    respond("GET", `/v1/nodes/${NODE_ID}`, { body: node });
    const getPage = vi.fn(() => Promise.resolve(letter));
    vi.mocked(openPdf).mockReturnValue({
      promise: Promise.resolve({ numPages: 200, getPage } as unknown as PDFDocumentProxy),
      destroy: () => {},
    });

    const { container } = renderInBase(<NodeView />, `/kbs/kb-1/n/${NODE_ID}?p=137&hl=72,100,300,140`);

    expect(await screen.findByRole("img", { name: "Página 137 do PDF" })).toBeInTheDocument();
    expect(getPage).toHaveBeenCalledWith(137);
    await waitFor(() => expect(container.querySelector("mark")).toBeInTheDocument());
    // At 100%, a point is 96/72 CSS pixels; the box is read from the page's top left.
    const { style } = container.querySelector("mark")!;
    expect(parseFloat(style.left)).toBeCloseTo(96);
    expect(parseFloat(style.top)).toBeCloseTo(133.33);
    expect(parseFloat(style.width)).toBeCloseTo(304);
    expect(parseFloat(style.height)).toBeCloseTo(53.33);
  });
});
