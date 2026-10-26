import uuid

from acervo.core.signing import sign, verify

SECRET = "test-session-secret"
NODE = uuid.uuid4()
VERSION = uuid.uuid4()
SESSION = uuid.uuid4()
EXPIRES = 1_800_000_060
NOW = 1_800_000_000


def test_a_valid_signature_verifies() -> None:
    for version in (None, VERSION):
        signature = sign(SECRET, "file", NODE, version, SESSION, EXPIRES)
        assert verify(SECRET, "file", NODE, version, SESSION, EXPIRES, signature, NOW)


def test_an_expired_signature_does_not() -> None:
    signature = sign(SECRET, "file", NODE, None, SESSION, EXPIRES)

    assert not verify(SECRET, "file", NODE, None, SESSION, EXPIRES, signature, EXPIRES)


def test_a_signature_for_another_node_or_version_does_not() -> None:
    signature = sign(SECRET, "file", NODE, VERSION, SESSION, EXPIRES)

    assert not verify(SECRET, "file", uuid.uuid4(), VERSION, SESSION, EXPIRES, signature, NOW)
    assert not verify(SECRET, "file", NODE, uuid.uuid4(), SESSION, EXPIRES, signature, NOW)
    assert not verify(SECRET, "file", NODE, None, SESSION, EXPIRES, signature, NOW)


def test_a_signature_from_another_session_does_not() -> None:
    signature = sign(SECRET, "file", NODE, None, SESSION, EXPIRES)

    assert not verify(SECRET, "file", NODE, None, uuid.uuid4(), EXPIRES, signature, NOW)


def test_a_tampered_signature_or_expiry_does_not() -> None:
    signature = sign(SECRET, "file", NODE, None, SESSION, EXPIRES)
    tampered = signature[:-1] + ("0" if signature[-1] != "0" else "1")

    assert not verify(SECRET, "file", NODE, None, SESSION, EXPIRES, tampered, NOW)
    assert not verify(SECRET, "file", NODE, None, SESSION, EXPIRES + 3600, signature, NOW)
    assert not verify("another-secret", "file", NODE, None, SESSION, EXPIRES, signature, NOW)
    assert not verify(SECRET, "file", NODE, None, SESSION, EXPIRES, "é", NOW)


def test_a_link_signed_for_one_purpose_fails_for_another() -> None:
    signature = sign(SECRET, "file", NODE, None, SESSION, EXPIRES)

    assert not verify(SECRET, "cover", NODE, None, SESSION, EXPIRES, signature, NOW)
    assert not verify(SECRET, "export", NODE, None, SESSION, EXPIRES, signature, NOW)
