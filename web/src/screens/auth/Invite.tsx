import { useCallback, useEffect } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useErrorText } from "../../app/errors";
import { useForgetAccount } from "../../app/lastPage";
import { useMe, useSignOut } from "../../data/account";
import { switchOrganization } from "../../data/organizations";
import { useAcceptInvite, useInvitePreview, type InvitePreview } from "../../data/orgSettings";
import { useI18n } from "../../i18n";
import { Button } from "../../ui/Button";
import { AuthCard, AuthError, authLink, GoogleFirst } from "./AuthCard";

/** Where the invite leads once accepted: the base it shares, else the organization's Bases. */
const landing = (invite: InvitePreview) => (invite.kb_id ? `/kbs/${invite.kb_id}` : "/bases");

/** Lands where the accepted invite leads; a base's organization is the shell's to follow from the base. */
function useLand() {
  const navigate = useNavigate();
  return useCallback(
    (invite: InvitePreview) => {
      if (!invite.kb_id) switchOrganization(invite.organization_id);
      navigate(landing(invite), { replace: true });
    },
    [navigate],
  );
}

/** The organization, or the base, and the role the invite gives. */
function Target({ invite }: { invite: InvitePreview }) {
  const { t } = useI18n();
  const role = t(`settings.role.${invite.kb_id ? "base" : "org"}.${invite.role}`);
  return (
    <div className="flex flex-col pb-3">
      <span className="text-15 font-medium text-text">{invite.base ?? invite.organization}</span>
      <span className="text-12 text-text-3">
        {invite.base
          ? t("auth.invite.inBase", { organization: invite.organization, role })
          : t("auth.invite.as", { role })}
      </span>
    </div>
  );
}

/**
 * `/convite/:token`, the link of the `org_invite` email. Signed in with the invited email, it joins; with another,
 * it offers to switch account; with none, it creates the account with the invited email, which joins once confirmed
 * and comes back here. A used link signed in as who joined with it lands where it leads.
 */
export function Invite() {
  const { t } = useI18n();
  const errorText = useErrorText();
  const navigate = useNavigate();
  const forget = useForgetAccount();
  const token = useParams().token!;
  const preview = useInvitePreview(token);
  const me = useMe();
  const accept = useAcceptInvite();
  const signOut = useSignOut();
  const land = useLand();
  const here = `/convite/${token}`;
  const used = preview.isError && Boolean(me.data);
  const { mutate } = accept;

  // The API answers a used invite again only for the account that joined with it, still in.
  useEffect(() => {
    if (used) mutate(token, { onSuccess: land });
  }, [used, token, mutate, land]);
  const home = (
    <Link to="/" className={authLink}>
      {t("auth.invite.home")}
    </Link>
  );

  if (preview.isError && (me.isPending || (me.data && !accept.isError))) return null;
  if (preview.isError) return <AuthCard title={t("auth.invite.invalid.title")} desc={t("auth.invite.invalid.desc")} foot={home} />;
  if (!preview.data || me.isPending) return null;
  const invite = preview.data;
  if (invite.expired)
    return (
      <AuthCard
        title={t("auth.invite.expired.title")}
        desc={t("auth.invite.expired.desc", { inviter: invite.inviter })}
        foot={home}
      />
    );

  const account = me.data;
  const title = t("auth.invite.title", { inviter: invite.inviter });

  if (!account)
    return (
      <AuthCard
        title={title}
        foot={
          <>
            {t("auth.invite.for", { email: invite.email })} {t("auth.signUp.hasAccount")}{" "}
            <Link to={`/entrar?next=${encodeURIComponent(here)}`} className={authLink}>
              {t("auth.signUp.signIn")}
            </Link>
          </>
        }
      >
        <Target invite={invite} />
        <GoogleFirst next={here} />
        <Button
          className="w-full"
          onClick={() =>
            // The email goes in the router's state, not the URL; confirming it joins what it was invited to.
            navigate(`/criar-conta?next=${encodeURIComponent(here)}`, { state: { email: invite.email } })
          }
        >
          {t("auth.invite.email")}
        </Button>
      </AuthCard>
    );

  if (account.email.toLowerCase() !== invite.email.toLowerCase())
    return (
      <AuthCard
        title={t("auth.invite.other", { email: invite.email })}
        desc={t("auth.invite.other.desc", { email: account.email })}
      >
        <Button
          variant="ink"
          className="w-full"
          disabled={signOut.isPending}
          onClick={() =>
            signOut.mutate(undefined, {
              onSuccess: () => {
                forget();
                navigate(`/entrar?next=${encodeURIComponent(here)}`, { replace: true });
              },
            })
          }
        >
          {t("auth.invite.switch")}
        </Button>
        {signOut.isError && <AuthError>{errorText(signOut.error)}</AuthError>}
      </AuthCard>
    );

  return (
    <AuthCard title={title} foot={t("auth.invite.for", { email: invite.email })}>
      <Target invite={invite} />
      <Button
        variant="ink"
        className="w-full"
        disabled={accept.isPending}
        onClick={() =>
          accept.mutate(token, { onSuccess: land })
        }
      >
        {t("auth.invite.accept")}
      </Button>
      {accept.isError && <AuthError>{errorText(accept.error)}</AuthError>}
    </AuthCard>
  );
}
