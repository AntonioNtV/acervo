/**
 * A block tokenizer's `start`: where `pattern` (one line) first matches before the next blank line, else that blank
 * line. marked asks it before each paragraph to stop the paragraph there, and no paragraph runs past a blank line;
 * searching the whole rest of the page each time made opening a long page quadratic. Answering the blank line, not
 * -1, keeps the paragraph marked as cut, which is how a line the tokenizers then reject is joined back to it.
 */
export const startBefore = (pattern: RegExp) => (src: string) => {
  const blank = src.indexOf("\n\n");
  if (blank < 0) return src.search(pattern);
  const found = src.slice(0, blank).search(pattern);
  return found < 0 ? blank + 1 : found;
};
