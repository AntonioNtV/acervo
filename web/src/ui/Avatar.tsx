/** Up to two letters: the first and last words of the name, or the email's first letter when there is no name. */
function initials(name: string, email: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean);
  const letters = words.length > 1 ? words[0]![0]! + words.at(-1)![0]! : (words[0]?.[0] ?? email[0] ?? "");
  return letters.toUpperCase();
}

/** A person's photo in a circle or, without one, their initials on `muted`; no color per person. */
export function Avatar({
  name,
  email = "",
  photo,
  size = 20,
}: {
  name: string;
  email?: string;
  photo: string | null;
  size?: 20 | 28 | 64;
}) {
  return (
    <span
      aria-hidden="true"
      style={{ width: size, height: size, fontSize: size === 20 ? 10 : size === 28 ? 11 : 20 }}
      className="inline-flex shrink-0 items-center justify-center overflow-hidden rounded-full bg-muted leading-none font-medium text-text-2"
    >
      {photo ? <img src={photo} alt="" className="size-full object-cover" /> : initials(name, email)}
    </span>
  );
}
