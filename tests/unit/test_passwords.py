from acervo.core.passwords import hash_password, needs_rehash, verify_password


def test_a_hash_verifies_its_password_only() -> None:
    hashed = hash_password("correct horse battery")

    assert verify_password("correct horse battery", hashed)
    assert not verify_password("correct horse batterY", hashed)
    assert not verify_password("correct horse battery", "not a hash")
    assert not needs_rehash(hashed)


def test_the_same_password_hashes_differently() -> None:
    assert hash_password("correct horse battery") != hash_password("correct horse battery")
