import { createMemoryRouter, RouterProvider, type InitialEntry } from "react-router-dom";
import { renderWithApi } from "../../api/testing";
import { routes } from "../../app/routes";
import { ThemeProvider } from "../../app/theme";

/** The screens before signing in at `entry`; any other path shows "Dentro", where signing in lands. */
export function renderAuth(entry: InitialEntry) {
  const router = createMemoryRouter([...routes.filter((route) => route.path), { path: "*", element: <p>Dentro</p> }], {
    initialEntries: [entry],
  });
  renderWithApi(
    <ThemeProvider>
      <RouterProvider router={router} />
    </ThemeProvider>,
  );
  return router;
}
