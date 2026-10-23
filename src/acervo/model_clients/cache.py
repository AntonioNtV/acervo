"""Answers already given, keyed by the hash of state + questions: a cached state is never re-sent."""

import hashlib
import json
from collections import OrderedDict
from collections.abc import Sequence

from acervo.domain.decisions import Answers, Question


class DecisionCache:
    """In memory, dropping the least recently used entry past `max_entries`."""

    def __init__(self, max_entries: int = 1024) -> None:
        self._entries: OrderedDict[str, Answers] = OrderedDict()
        self._max_entries = max_entries

    @staticmethod
    def key(state: str, questions: Sequence[Question]) -> str:
        payload = json.dumps([state, [question.model_dump() for question in questions]], ensure_ascii=False)
        return hashlib.sha256(payload.encode()).hexdigest()

    def get(self, key: str) -> Answers | None:
        answers = self._entries.get(key)
        if answers is not None:
            self._entries.move_to_end(key)
        return answers

    def put(self, key: str, answers: Answers) -> None:
        self._entries[key] = answers
        self._entries.move_to_end(key)
        if len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)
