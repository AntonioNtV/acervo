/** A node's name as the person reads it: pages end in `.md`, files in their own extension. */
export function FileName({ title, ext, className }: { title: string; ext?: string; className?: string }) {
  return (
    <span className={className}>
      {title}
      {ext && <span className="text-text-3">.{ext}</span>}
    </span>
  );
}
