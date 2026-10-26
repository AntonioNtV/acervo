import "@testing-library/jest-dom/vitest";
import { Editor } from "@tiptap/core";
import { MarkdownManager } from "@tiptap/markdown";
import { EditorContent, useEditor } from "@tiptap/react";
import { fireEvent, screen } from "@testing-library/react";
import { renderWithApi, resetApi, respond } from "../../api/testing";
import { embedOf } from "../../ui/EmbedFrame";
import { blockExtensions } from "../extensions";
import { LinkBlock, LinkBlockWithView } from "./linkBlock";

vi.mock("../../api/client", () => import("../../api/testing").then((m) => m.mockClient()));

// jsdom has no layout, and ProseMirror measures text ranges to scroll the selection into view.
Range.prototype.getClientRects ??= () => [] as unknown as DOMRectList;
Range.prototype.getBoundingClientRect ??= () => new DOMRect();

// Tried before `RawInline`/`RawBlock`, which come later in `blockExtensions`.
const extensions = [LinkBlock, ...blockExtensions];
const md = new MarkdownManager({ extensions });

const SUSEP = "https://www.susep.gov.br/circular-621";

let shown: Editor | null = null;

function Page({ markdown }: { markdown: string }) {
  shown = useEditor({
    extensions: extensions.map((extension) => (extension.name === "linkBlock" ? LinkBlockWithView : extension)),
    content: md.parse(markdown),
  });
  return <EditorContent editor={shown} />;
}

beforeEach(resetApi);

describe("link block", () => {
  it("reads a URL alone in a paragraph and writes it back as written", () => {
    const markdown = `Antes.\n\n${SUSEP}\n\n<https://youtu.be/dQw4w9WgXcQ>\n\nDepois.`;
    const doc = md.parse(markdown);

    expect(doc.content!.map((block) => block.type)).toEqual(["paragraph", "linkBlock", "linkBlock", "paragraph"]);
    expect(doc.content![1]!.attrs).toEqual({ url: SUSEP, angle: false });
    expect(md.serialize(doc)).toBe(markdown);

    const created = { type: "linkBlock", attrs: { url: "https://x.y/a?b=1" } };
    expect(md.serialize({ type: "doc", content: [created] })).toBe("https://x.y/a?b=1");
  });

  it.each([
    ["Veja https://x.y aqui", "paragraph"],
    [`${SUSEP}\nna linha seguinte`, "paragraph"],
    [`[Circular](${SUSEP})`, "paragraph"],
    ["    https://x.y", "codeBlock"],
    ["- https://x.y", "bulletList"],
  ])("leaves %j as it was", (markdown, type) => {
    expect(md.parse(markdown).content!.map((block) => block.type)).toEqual([type]);
  });

  it.each([
    [
      "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=10",
      "YouTube",
      "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ",
    ],
    ["https://youtube.com/shorts/dQw4w9WgXcQ", "YouTube", "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ"],
    ["https://youtu.be/dQw4w9WgXcQ", "YouTube", "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ"],
    ["https://www.youtube.com/@susep", "YouTube", null],
    [
      "https://www.figma.com/design/AbC123/Tela",
      "Figma",
      "https://www.figma.com/embed?embed_host=acervo&url=https%3A%2F%2Fwww.figma.com%2Fdesign%2FAbC123%2FTela",
    ],
    ["https://www.figma.com/file/AbC123", "Figma", expect.stringContaining("figma.com/embed?")],
    [
      "https://www.google.com/maps/place/SUSEP/@-22.9,-43.17,17z",
      "Google Maps",
      "https://maps.google.com/maps?q=-22.9%2C-43.17&output=embed",
    ],
    [
      "https://www.google.com/maps?q=Rua+Buenos+Aires",
      "Google Maps",
      "https://maps.google.com/maps?q=Rua%20Buenos%20Aires&output=embed",
    ],
    ["https://www.loom.com/share/abc123", "Loom", "https://www.loom.com/embed/abc123"],
    ["https://gist.github.com/ana/abc123", "GitHub", "https://gist.github.com/ana/abc123.pibb"],
    ["https://github.com/ana/repo", null, null],
    [SUSEP, null, null],
  ])("embeds %s with %s", (url, provider, src) => {
    expect(embedOf(url)).toEqual(provider ? { provider, src } : null);
  });

  it("shows the site's preview, opening it in a new tab", async () => {
    respond("GET", "/v1/link-preview", {
      body: {
        url: SUSEP,
        domain: "susep.gov.br",
        title: "Circular SUSEP nº 621/2021",
        description: "Seguros de danos.",
      },
    });
    renderWithApi(<Page markdown={`${SUSEP}\n`} />);

    const card = await screen.findByRole("link", { name: /Circular SUSEP nº 621\/2021/ });
    expect(card).toHaveAttribute("href", SUSEP);
    expect(card).toHaveAttribute("target", "_blank");
    expect(card).toHaveAttribute("rel", "noopener noreferrer");
    expect(card).toHaveTextContent("Seguros de danos.");
  });

  it.each([
    ["did not answer", { body: { url: SUSEP, domain: "susep.gov.br" } }],
    ["was refused", { status: 422, body: { error: "invalid_url", message: "private address" } }],
  ])("shows only the domain and the URL when the site %s", async (_case, reply) => {
    respond("GET", "/v1/link-preview", reply);
    renderWithApi(<Page markdown={`${SUSEP}\n`} />);

    expect(await screen.findByText("Não deu para ler este site. O link continua funcionando.")).toBeInTheDocument();
    const card = screen.getByRole("link");
    expect(card).toHaveTextContent(SUSEP);
    expect(card).toHaveTextContent("susep.gov.br");
    expect(card).not.toHaveAttribute("aria-busy");
  });

  it("plays a YouTube URL, and a page of the service with no player shows the blocked state", async () => {
    renderWithApi(<Page markdown={"https://youtu.be/dQw4w9WgXcQ\n\nhttps://www.youtube.com/@susep\n"} />);

    const player = await screen.findByTitle("YouTube");
    expect(player).toHaveAttribute("src", "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ");
    expect(player).toHaveAttribute("referrerpolicy", "no-referrer");
    expect(player.getAttribute("sandbox")).not.toContain("allow-top-navigation");
    expect(screen.getByText("YouTube não deixa mostrar este conteúdo aqui.")).toBeInTheDocument();
  });

  it("asks for the address when inserted, and turns back into a link", async () => {
    renderWithApi(<Page markdown={"Antes.\n"} />);
    shown!.commands.setTextSelection(1);
    shown!.commands.insertLinkBlock();

    const ask = await screen.findByRole("textbox", { name: "editor.link.url" });
    fireEvent.change(ask, { target: { value: " sem endereço " } });
    fireEvent.keyDown(ask, { key: "Enter" });
    expect(shown!.getJSON().content?.find((block) => block.type === "linkBlock")?.attrs?.url).toBe("");

    fireEvent.change(ask, { target: { value: " https://www.loom.com/share/abc123 " } });
    fireEvent.keyDown(ask, { key: "Enter" });
    expect(await screen.findByTitle("Loom")).toHaveAttribute("src", "https://www.loom.com/embed/abc123");

    let pos = -1;
    shown!.state.doc.forEach((child, offset) => {
      if (child.type.name === "linkBlock") pos = offset;
    });
    shown!.commands.linkBlockToLink(pos);

    expect(shown!.getJSON().content!.map((block) => block.type)).toEqual(["paragraph", "paragraph"]);
    expect(md.serialize({ type: "doc", content: [shown!.getJSON().content![0]!] })).toBe(
      "[https://www.loom.com/share/abc123](https://www.loom.com/share/abc123)",
    );
  });
});
