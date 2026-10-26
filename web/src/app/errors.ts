import { ApiError } from "../data/request";
import { useI18n } from "../i18n";

// The codes any screen shows the same way; the others are told apart where they happen.
const BY_CODE: Record<string, string> = {
  not_found: "errors.notFound",
  unauthorized: "errors.unauthorized",
  invalid_credentials: "errors.invalidCredentials",
  too_many_attempts: "errors.tooManyAttempts",
  email_taken: "errors.emailTaken",
  code_invalid: "errors.codeInvalid",
  validation: "errors.invalid",
};

function genericKey(status: number): string {
  if (status === 0) return "errors.network";
  if (status === 400 || status === 422) return "errors.invalid";
  if (status === 404) return "errors.notFound";
  if (status === 409) return "errors.conflict";
  if (status >= 500) return "errors.server";
  return "errors.other";
}

/**
 * What the person reads for a failed call: the text its call site gave for that error code, the shared one for the
 * code, or a generic one by status. The API's own `message` is never shown.
 */
export function useErrorText() {
  const { t } = useI18n();
  return (error: unknown, known: Partial<Record<string, string>> = {}) => {
    if (!(error instanceof ApiError)) return t(genericKey(0));
    const shared = BY_CODE[error.code];
    return known[error.code] ?? (shared ? t(shared) : t(genericKey(error.status)));
  };
}

