import "@testing-library/jest-dom/vitest";
import type { Editor } from "@tiptap/core";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { I18nProvider } from "../i18n";
import { BlockEditor } from "./BlockEditor";

// jsdom has no layout, and ProseMirror measures text ranges to scroll the selection into view.
Range.prototype.getClientRects ??= () => [] as unknown as DOMRectList;
Range.prototype.getBoundingClientRect ??= () => new DOMRect();
document.elementFromPoint ??= () => null;

function renderEditor(markdown: string) {
  const onChange = vi.fn();
  render(
    <MemoryRouter>
      <I18nProvider>
        <BlockEditor
          markdown={markdown}
          onChange={onChange}
          resolveLink={(title) => (title === "Renovação" ? { href: "/kbs/kb-1/n/page-2" } : "missing")}
          onCreateSubPage={async () => "Sem título"}
        />
      </I18nProvider>
    </MemoryRouter>,
  );
  const dom = screen.getByRole("textbox", { name: "Texto da página" }) as HTMLElement & { editor: Editor };
  return { onChange, editor: dom.editor };
}

/**
 * Types as the keyboard does, through input rules and the menus' triggers. jsdom cannot drive the input itself, and
 * a focused view would read back jsdom's DOM selection, which does not follow; so the editor is not focused here.
 */
function type(editor: Editor, text: string) {
  act(() => {
    for (const char of text) {
      const { view } = editor;
      const { from, to } = view.state.selection;
      const handled = view.someProp("handleTextInput", (f) => f(view, from, to, char, () => view.state.tr));
      if (!handled) view.dispatch(view.state.tr.insertText(char, from, to));
    }
  });
}

describe("BlockEditor", () => {
  it('"/" inserts a callout', async () => {
    const { editor, onChange } = renderEditor("");

    type(editor, "/dest");
    const menu = await screen.findByRole("listbox", { name: "Inserir bloco" });
    fireEvent.click(screen.getByRole("option", { name: /Destaque/ }));

    expect(menu).not.toBeInTheDocument();
    type(editor, "Prazo de 3 dias");
    expect(onChange).toHaveBeenLastCalledWith("> [!NOTE]\n> Prazo de 3 dias\n");
  });

  it('"/" lists the planned blocks', async () => {
    const { editor } = renderEditor("");

    type(editor, "/");
    await screen.findByRole("listbox", { name: "Inserir bloco" });

    for (const name of [
      "Título 4",
      "Título 5",
      "Título 6",
      "Título recolhível",
      "Colunas",
      "Sumário",
      "Trilha de navegação",
      "Nota de rodapé",
      "Equação na linha",
      "Bloco sincronizado",
    ]) {
      expect(screen.getByRole("option", { name: new RegExp(name) })).toBeInTheDocument();
    }
  });

  it("#### makes a heading 4", () => {
    const { editor, onChange } = renderEditor("");

    type(editor, "#### Emissão");

    expect(screen.getByRole("heading", { level: 4, name: "Emissão" })).toBeInTheDocument();
    expect(onChange).toHaveBeenLastCalledWith("#### Emissão\n");
  });

  it("- [ ] makes a to-do", () => {
    const { editor, onChange } = renderEditor("");

    type(editor, "- [ ] Boleto no portal");

    expect(screen.getByRole("checkbox")).not.toBeChecked();
    expect(onChange).toHaveBeenLastCalledWith("- [ ] Boleto no portal\n");
  });

  it("[] makes a to-do", () => {
    const { editor, onChange } = renderEditor("");

    type(editor, "[] Boleto no portal");

    expect(screen.getByRole("checkbox")).not.toBeChecked();
    expect(onChange).toHaveBeenLastCalledWith("- [ ] Boleto no portal\n");
  });

  it("the handle acts on its block after an edit above it", () => {
    const { editor, onChange } = renderEditor("Primeiro\n\nSegundo\n");

    fireEvent.mouseMove(screen.getByText("Segundo"));
    act(() => {
      editor.commands.insertContentAt(0, { type: "paragraph", content: [{ type: "text", text: "Novo" }] });
    });
    fireEvent.click(screen.getByRole("button", { name: "Arrastar para mover ou clicar para abrir o menu" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Excluir" }));

    expect(onChange).toHaveBeenLastCalledWith("Novo\n\nPrimeiro\n");
  });

  it("pasting Markdown builds blocks", async () => {
    const { editor, onChange } = renderEditor("");
    const markdown = "## Documentos\n\n- Boleto\n- Apólice\n\nVer [[Renovação]].\n";

    act(() => {
      const paste = new Event("paste", { bubbles: true, cancelable: true });
      Object.assign(paste, {
        clipboardData: { types: ["text/plain"], getData: (kind: string) => (kind === "text/plain" ? markdown : "") },
      });
      editor.view.dom.dispatchEvent(paste);
    });

    expect(screen.getByRole("heading", { level: 2, name: "Documentos" })).toBeInTheDocument();
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
    expect(await screen.findByRole("link", { name: "Renovação" })).toHaveAttribute("href", "/kbs/kb-1/n/page-2");
    expect(onChange).toHaveBeenLastCalledWith(markdown);
  });

  it("loading emits nothing", async () => {
    const markdown =
      "## Documentos\n\n- Boleto <!-- nota · 22/10/2026 · 8f3a -->\n\n> [!NOTE]\n> Aviso\n\nVer [[Sinistros]].\n";
    const { editor, onChange } = renderEditor(markdown);

    act(() => {
      editor.commands.setTextSelection(3);
    });

    expect(await screen.findByText("Sinistros")).toHaveAttribute("title", "Nenhuma página com esse nome");
    expect(onChange).not.toHaveBeenCalled();
  });
});
