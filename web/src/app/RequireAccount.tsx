import { useQueryClient } from "@tanstack/react-query";
import { useLayoutEffect } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import { useMe } from "../data/account";
import { setUnauthorizedHandler } from "../data/request";
import { forgetPages } from "./lastPage";

/**
 * Every screen of an account. It loads the account alongside the screen instead of before it, and a 401 from any
 * request forgets what this browser held for the session and opens Entrar, which comes back here.
 */
export function RequireAccount() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const { pathname, search } = useLocation();
  useMe();

  // A layout effect, so the handler is in place before the screen's queries are answered.
  useLayoutEffect(() => {
    setUnauthorizedHandler(() => {
      navigate(`/entrar?next=${encodeURIComponent(pathname + search)}`, { replace: true });
      forgetPages();
      queryClient.clear();
    });
    return () => setUnauthorizedHandler(null);
  }, [navigate, queryClient, pathname, search]);

  return <Outlet />;
}
