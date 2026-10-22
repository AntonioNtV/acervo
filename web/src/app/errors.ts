import { ApiError } from "../api/queries";
import { useI18n } from "../i18n";

function genericKey(status: number): string {
  if (status === 0) return "errors.network";
  if (status === 400 || status === 422) return "errors.invalid";
  if (status === 404) return "errors.notFound";
  if (status === 409) return "errors.conflict";
  if (status >= 500) return "errors.server";
  return "errors.other";
}

/**
 * What the person reads for a failed call: the text its call site gave for that status, or a generic one by status.
 * The API's own `message` is never shown.
 */
export function useErrorText() {
  const { t } = useI18n();
  return (error: unknown, known: Partial<Record<number, string>> = {}) => {
    const status = error instanceof ApiError ? error.status : 0;
    return known[status] ?? t(genericKey(status));
  };
}
