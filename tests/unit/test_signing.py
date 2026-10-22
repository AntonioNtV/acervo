import uuid

from acervo.core.signing import sign, verify

SECRET = "test-api-key"
NODE = uuid.uuid4()
VERSION = uuid.uuid4()
EXPIRES = 1_800_000_060
NOW = 1_800_000_000


def test_a_valid_signature_verifies() -> None:
    for version in (None, VERSION):
        assert verify(SECRET, NODE, version, EXPIRES, sign(SECRET, NODE, version, EXPIRES), NOW)


def test_an_expired_signature_does_not() -> None:
    assert not verify(SECRET, NODE, None, EXPIRES, sign(SECRET, NODE, None, EXPIRES), EXPIRES)


def test_a_signature_for_another_node_or_version_does_not() -> None:
    signature = sign(SECRET, NODE, VERSION, EXPIRES)

    assert not verify(SECRET, uuid.uuid4(), VERSION, EXPIRES, signature, NOW)
    assert not verify(SECRET, NODE, uuid.uuid4(), EXPIRES, signature, NOW)
    assert not verify(SECRET, NODE, None, EXPIRES, signature, NOW)


def test_a_tampered_signature_or_expiry_does_not() -> None:
    signature = sign(SECRET, NODE, None, EXPIRES)

    assert not verify(SECRET, NODE, None, EXPIRES, signature[:-1] + ("0" if signature[-1] != "0" else "1"), NOW)
    assert not verify(SECRET, NODE, None, EXPIRES + 3600, signature, NOW)
    assert not verify("another-key", NODE, None, EXPIRES, signature, NOW)
    assert not verify(SECRET, NODE, None, EXPIRES, "é", NOW)
