import random

from acervo.domain.sort_keys import key_between


def test_between_two_keys() -> None:
    for before, after in [("a", "c"), ("a", "b"), ("a0001", "a0002"), ("az", "b"), ("1", "11")]:
        key = key_between(before, after)
        assert before < key < after


def test_before_first() -> None:
    for first in ["a", "1", "01", "a0000"]:
        assert key_between(None, first) < first


def test_after_last() -> None:
    for last in ["a", "z", "zzz", "a0004"]:
        assert key_between(last, None) > last


def test_many_inserts_stay_ordered() -> None:
    rng = random.Random(7)
    keys: list[str] = []
    for _ in range(2000):
        index = rng.randint(0, len(keys))
        before = keys[index - 1] if index else None
        after = keys[index] if index < len(keys) else None
        keys.insert(index, key_between(before, after))

    assert keys == sorted(keys)
    assert len(set(keys)) == len(keys)
