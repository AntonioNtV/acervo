import * as RadixMenu from "@radix-ui/react-dropdown-menu";
import { useI18n } from "../i18n";
import { Button } from "./Button";
import { Icon } from "./Icon";

const ROLES = { org: ["owner", "admin", "member"], base: ["reader", "editor", "admin"] } as const;

/**
 * A person's role in an organization or a base: the role as text with a caret, opening what each role can do and,
 * with `onRemove`, Remover acesso. `roles` narrows the choice (an Admin cannot make Owners); `disabled` leaves only the
 * text, for who cannot change it or the last Owner. Changes at once.
 */
export function RoleSelect<S extends keyof typeof ROLES>({
  scope,
  value,
  roles = ROLES[scope],
  disabled = false,
  onChange,
  onRemove,
}: {
  scope: S;
  value: (typeof ROLES)[S][number];
  roles?: readonly (typeof ROLES)[S][number][];
  disabled?: boolean;
  onChange: (role: (typeof ROLES)[S][number]) => void;
  onRemove?: () => void;
}) {
  const { t } = useI18n();
  const name = t(`settings.role.${scope}.${value}`);
  if (disabled) return <span className="px-2 text-12 text-text-2">{name}</span>;
  return (
    <RadixMenu.Root>
      <RadixMenu.Trigger asChild>
        <Button variant="quiet" size="sm" className="gap-0.5 font-normal" aria-label={`${t("settings.role.label")}: ${name}`}>
          {name}
          <Icon name="caretDown" size={14} />
        </Button>
      </RadixMenu.Trigger>
      <RadixMenu.Portal>
        <RadixMenu.Content
          align="end"
          sideOffset={4}
          aria-label={t("settings.role.label")}
          className="flex w-[260px] flex-col rounded-[8px] border border-line-2 bg-bg p-1"
        >
          <RadixMenu.RadioGroup value={value} onValueChange={(next) => onChange(next as (typeof ROLES)[S][number])}>
            {roles.map((role) => (
              <RadixMenu.RadioItem
                key={role}
                value={role}
                className="flex cursor-pointer items-start justify-between gap-2 rounded-[6px] px-2.5 py-1.5 text-13 text-text outline-none data-[highlighted]:bg-subtle"
              >
                <span className="flex flex-col">
                  {t(`settings.role.${scope}.${role}`)}
                  <span className="text-12 leading-[18px] text-text-3">{t(`settings.role.${scope}.${role}.desc`)}</span>
                </span>
                <RadixMenu.ItemIndicator className="mt-[3px] inline-flex text-text-2">
                  <Icon name="check" size={14} />
                </RadixMenu.ItemIndicator>
              </RadixMenu.RadioItem>
            ))}
          </RadixMenu.RadioGroup>
          {onRemove && (
            <>
              <RadixMenu.Separator className="my-1 h-px bg-line" />
              <RadixMenu.Item
                onSelect={onRemove}
                className="flex h-[30px] cursor-pointer items-center rounded-[6px] px-2.5 text-13 text-text outline-none data-[highlighted]:bg-subtle"
              >
                {t("settings.role.remove")}
              </RadixMenu.Item>
            </>
          )}
        </RadixMenu.Content>
      </RadixMenu.Portal>
    </RadixMenu.Root>
  );
}
