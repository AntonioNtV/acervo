import "@testing-library/jest-dom/vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithApi } from "../../api/testing";
import { DeleteDialog } from "./DeleteDialog";

describe("DeleteDialog", () => {
  it("enables the button only once the name is typed as it is", async () => {
    const onDelete = vi.fn();
    renderWithApi(
      <DeleteDialog
        title="Excluir Seguros SA"
        items={["Não dá para desfazer."]}
        match="Seguros SA"
        action="Excluir organização"
        pending={false}
        onDelete={onDelete}
        onClose={() => {}}
      />,
    );
    const field = screen.getByLabelText("Digite Seguros SA para confirmar");
    const button = screen.getByRole("button", { name: "Excluir organização" });

    await userEvent.type(field, "seguros sa");
    expect(button).toBeDisabled();
    await userEvent.clear(field);
    await userEvent.type(field, "Seguros SA ");
    await userEvent.click(button);

    expect(onDelete).toHaveBeenCalledOnce();
  });
});
