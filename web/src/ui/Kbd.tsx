/** A keyboard shortcut shown next to what it does, as "⌘K". */
export function Kbd({ children }: { children: string }) {
  return <kbd className="ml-auto font-sans text-11 text-ghost">{children}</kbd>;
}
