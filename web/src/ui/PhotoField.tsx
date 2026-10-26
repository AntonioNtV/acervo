import { useRef, type ReactNode } from "react";
import { useI18n } from "../i18n";
import { Button } from "./Button";
import { Icon } from "./Icon";

/** The 64 px avatar, Enviar foto (Trocar foto) and Remover, and the file's rule or the error in its place. */
export function PhotoField({
  avatar,
  hasPhoto,
  sending,
  error,
  onPick,
  onRemove,
}: {
  avatar: ReactNode;
  hasPhoto: boolean;
  sending: boolean;
  error?: string;
  onPick: (file: File) => void;
  onRemove: () => void;
}) {
  const { t } = useI18n();
  const input = useRef<HTMLInputElement>(null);
  return (
    <div className="flex items-center gap-4">
      {avatar}
      <div className="flex max-w-[300px] flex-col gap-1.5 text-12 text-text-3">
        <span className="flex gap-1">
          <Button size="sm" disabled={sending} onClick={() => input.current?.click()}>
            {sending ? (
              t("settings.photo.sending")
            ) : (
              <>
                <Icon name="upload" size={14} />
                {t(hasPhoto ? "settings.photo.change" : "settings.photo.send")}
              </>
            )}
          </Button>
          {hasPhoto && !sending && (
            <Button variant="quiet" size="sm" onClick={onRemove}>
              {t("settings.photo.remove")}
            </Button>
          )}
          <input
            ref={input}
            type="file"
            accept="image/png,image/jpeg,image/webp"
            aria-label={t("settings.photo")}
            className="hidden"
            onChange={(event) => {
              const file = event.target.files?.[0];
              // So picking the same file again still sends it.
              event.target.value = "";
              if (file) onPick(file);
            }}
          />
        </span>
        {error ? (
          <span role="alert" className="text-err">
            {error}
          </span>
        ) : (
          <span>{t("settings.photo.hint")}</span>
        )}
      </div>
    </div>
  );
}
