import { cx } from "./cx";
import { Icon, type IconName } from "./Icon";

/**
 * The person's emoji for a page, folder or base when there is one, else the icon of its kind (none for a base). The
 * emoji takes the icon's box, so rows keep their alignment.
 */
export function NodeIcon({
  icon,
  kind,
  size = 16,
  className,
}: {
  icon: string | null | undefined;
  kind?: IconName;
  size?: number;
  className?: string;
}) {
  if (icon) {
    return (
      <span
        aria-hidden="true"
        style={{ width: size, height: size, fontSize: Math.round(size * 0.9) }}
        className={cx("inline-flex shrink-0 items-center justify-center leading-none", className)}
      >
        {icon}
      </span>
    );
  }
  return kind ? <Icon name={kind} size={size} className={className} /> : null;
}
