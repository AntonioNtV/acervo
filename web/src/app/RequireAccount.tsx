import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useLayoutEffect, useState } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import { useMe } from "../data/account";
import { switchOrganization, useOrganizations } from "../data/organizations";
import { ApiError, setUnauthorizedHandler } from "../data/request";
import { RequiredTwoFactor } from "../screens/auth/RequiredTwoFactor";
import { readAccountId, rememberAccountId, useForgetAccount } from "./lastPage";

/**
 * Every screen of an account. It loads the account alongside the screen instead of before it, and a 401 from any
 * request forgets what this browser held for the session and opens Entrar, which comes back here. An account other
 * than the one this browser last showed (signed in through Google, a full page load) forgets the previous one first.
 * A read refused with `two_factor_required` shows "2FA exigido" for that organization in place of the screen.
 */
export function RequireAccount() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const { pathname, search } = useLocation();
  const forget = useForgetAccount();
  const me = useMe().data;
  const [known, setKnown] = useState(readAccountId);
  const [required, setRequired] = useState<string | null>(null);
  const organizations = useOrganizations().data;
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

  useEffect(
    () =>
      queryClient.getQueryCache().subscribe((event) => {
        const error = event.query.state.error;
        if (event.type === "updated" && error instanceof ApiError && error.code === "two_factor_required")
          setRequired(String(error.details.organization_id));
      }),
    [queryClient],
  );

  if (switched) return null;
  if (required)
    return (
      <RequiredTwoFactor
        organization={organizations?.find((organization) => organization.id === required)?.name ?? ""}
        onDone={() => {
          setRequired(null);
          void queryClient.invalidateQueries();
        }}
        onLeave={() => {
          setRequired(null);
          switchOrganization(null);
          navigate("/bases");
        }}
      />
    );
  return <Outlet />;
}
