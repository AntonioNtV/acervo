import { useState } from "react";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import { Providers } from "./Providers";
import { routes } from "./routes";

export function App() {
  const [router] = useState(() => createBrowserRouter(routes));
  return (
    <Providers>
      <RouterProvider router={router} />
    </Providers>
  );
}
