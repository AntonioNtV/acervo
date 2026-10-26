import type { ReactNode } from "react";
import { Avatar } from "./Avatar";

/**
 * A person with access to an organization or a base: avatar, name and email, and at the right `actions` (Reenviar)
 * and the role. A pending invite has no name: its email, and `note` (when it expires) under it.
 */
export function MemberRow({
  name,
  email,
  photo = null,
  you,
  note,
  actions,
  role,
}: {
  name: string;
  email: string;
  photo?: string | null;
  you?: string;
  note?: string;
  actions?: ReactNode;
  role: ReactNode;
}) {
  return (
    <div className="flex min-h-14 items-center gap-3 border-b border-line px-2 py-2.5 text-13 hover:bg-subtle">
      <Avatar name={name} email={email} photo={photo} size={28} />
      <span className="flex min-w-0 flex-1 flex-col">
        <span className="truncate text-text">
          {name || email}
          {you && <span className="text-text-3"> {you}</span>}
        </span>
        <span className="truncate text-12 leading-[18px] text-text-3">{note ?? email}</span>
      </span>
      {actions}
      {role}
    </div>
  );
}
