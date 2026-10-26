import { useQueryClient } from "@tanstack/react-query";
import { useLayoutEffect, useState } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import { useMe } from "../data/account";
import { setUnauthorizedHandler } from "../data/request";
import { readAccountId, rememberAccountId, useForgetAccount } from "./lastPage";

/**
 * Every screen of an account. It loads the account alongside the screen instead of before it, and a 401 from any
 * request forgets what this browser held for the session and opens Entrar, which comes back here. An account other
 * than the one this browser last showed (signed in through Google, a full page load) forgets the previous one first.
 */
export function RequireAccount() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const { pathname, search } = useLocation();
  const forget = useForgetAccount();
  const me = useMe().data;
  const [known, setKnown] = useState(readAccountId);
  const switched = me !== undefined && known !== null && known !== me.id;

  // A layout effect, so the handler is in place before the screen's queries are answered.
  useLayoutEffect(() => {
    setUnauthorizedHandler(() => {
      navigate(`/entrar?next=${encodeURIComponent(pathname + search)}`, { replace: true });
      forget();
    });
    return () => setUnauthorizedHandler(null);
  }, [navigate, forget, pathname, search]);

  useLayoutEffect(() => {
    if (!me || known === me.id) return;
    if (switched) {
      forget();
      queryClient.setQueryData(["me"], me);
    }
    rememberAccountId(me.id);
    setKnown(me.id);
  }, [me, known, switched, forget, queryClient]);

  return switched ? null : <Outlet />;
}
