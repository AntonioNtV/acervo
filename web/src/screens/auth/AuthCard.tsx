import { useId, type InputHTMLAttributes, type ReactNode } from "react";
import { useSearchParams } from "react-router-dom";
import { Brand } from "../../app/Brand";
import { useI18n } from "../../i18n";
import { Input } from "../../ui/Input";
import { GoogleLogo, ProviderButton } from "../../ui/ProviderButton";

/** A link inside the texts of these screens: the foot's, an error's. */
export const authLink = "text-text underline decoration-line-2 underline-offset-[3px]";

/**
 * The column of every screen before signing in: the brand, a title, a line of explanation, the form and a foot. No box
 * around it: it sits on the page.
 */
export function AuthCard({
  title,
  desc,
  onSubmit,
  children,
  foot,
}: {
  title: string;
  desc?: string;
  onSubmit?: () => void;
  children?: ReactNode;
  foot?: ReactNode;
}) {
  return (
    <main className="flex min-h-full justify-center bg-bg px-4 pt-28">
      <div className="flex w-80 max-w-full flex-col gap-6">
        <Brand />
        <div>
          <h1 className="m-0 text-20 font-medium tracking-[-0.01em] text-text">{title}</h1>
          {desc && <p className="mt-1 mb-0 text-13 text-text-3">{desc}</p>}
        </div>
        {children &&
          (onSubmit ? (
            <form
              className="m-0 flex flex-col gap-3"
              onSubmit={(event) => {
                event.preventDefault();
                onSubmit();
              }}
            >
              {children}
            </form>
          ) : (
            <div className="flex flex-col gap-3">{children}</div>
          ))}
        {foot && <p className="m-0 text-13 text-text-3">{foot}</p>}
      </div>
    </main>
  );
}

/**
 * Continuar com Google, the other providers in `children`, and the "ou" line above the email form; Google comes back
 * to `next` once signed in.
 */
export function GoogleFirst({ next, children }: { next: string; children?: ReactNode }) {
  const { t } = useI18n();
  return (
    <>
      <ProviderButton href={`/v1/auth/google/start?next=${encodeURIComponent(next)}`} logo={<GoogleLogo />}>
        {t("auth.google")}
      </ProviderButton>
      {children}
      <div className="flex items-center gap-3 text-12 text-ghost">
        <span className="h-px flex-1 bg-line" />
        {t("auth.or")}
        <span className="h-px flex-1 bg-line" />
      </div>
    </>
  );
}

/** A labeled input; its error sits outside the label, so a link in the error is not part of the field's name. */
export function AuthField({ label, error, ...rest }: InputHTMLAttributes<HTMLInputElement> & { label: string; error?: ReactNode }) {
  const id = useId();
  return (
    <div className="flex flex-col gap-1.5 text-12 text-text-2">
      <label htmlFor={id}>{label}</label>
      <Input id={id} aria-invalid={error ? true : undefined} aria-describedby={error ? `${id}-error` : undefined} {...rest} />
      {error && (
        <span id={`${id}-error`} role="alert" className="-mt-0.5 text-err">
          {error}
        </span>
      )}
    </div>
  );
}

export function AuthError({ children }: { children: ReactNode }) {
  return (
    <p role="alert" className="m-0 text-12 text-err">
      {children}
    </p>
  );
}

/** Where to go once signed in: a path of this app only, so `?next=` cannot send the person to another site. */
export function useNext(): string {
  const [params] = useSearchParams();
  const next = params.get("next");
  return next && /^\/(?![/\\])/.test(next) ? next : "/bases";
}
