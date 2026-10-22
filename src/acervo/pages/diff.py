from difflib import SequenceMatcher
from typing import Literal, TypedDict


class DiffLine(TypedDict):
    op: Literal["same", "add", "del"]
    text: str


def line_diff(old: str, new: str) -> list[DiffLine]:
    """Every line of both texts in reading order, so the web app renders it without computing."""
    a, b = old.splitlines(), new.splitlines()
    lines: list[DiffLine] = []
    for tag, i1, i2, j1, j2 in SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag == "equal":
            lines += [{"op": "same", "text": text} for text in a[i1:i2]]
            continue
        lines += [{"op": "del", "text": text} for text in a[i1:i2]]
        lines += [{"op": "add", "text": text} for text in b[j1:j2]]
    return lines
