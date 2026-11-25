from th import redact


def test_aws_access_key():
    assert redact.redact("AKIAIOSFODNN7EXAMPLE") == "[REDACTED]"
    assert redact.redact("aws_key=AKIAIOSFODNN7EXAMPLE") == "aws_key=[REDACTED]"
    # too short: not a key
    assert redact.redact("AKIAIOSFODNN7") == "AKIAIOSFODNN7"


def test_authorization_bearer_basic():
    assert (
        redact.redact("Authorization: Bearer eyJhbGciOiJIUzI1NiJ9")
        == "Authorization: Bearer [REDACTED]"
    )
    assert (
        redact.redact("authorization = basic QWxhZGRpbjpvcGVuIHNlc2FtZQ==")
        == "authorization = basic [REDACTED]"
    )
    assert redact.redact("AUTHORIZATION:Bearer token123") == "AUTHORIZATION:Bearer [REDACTED]"
    # unknown scheme after authorization is not redacted by this pattern
    assert redact.redact("Authorization: Oauth abc") == "Authorization: Oauth abc"


def test_password_like_keys():
    for key in ("password", "passwd", "pwd", "token", "secret", "api_key", "api-key", "apikey"):
        assert redact.redact(f"{key}=s3cr3t") == f"{key}=[REDACTED]", key
    assert redact.redact("DB_PASSWORD=supersecret extra") == "DB_PASSWORD=[REDACTED] extra"
    assert redact.redact("PASSWORD = s3cr3t") == "PASSWORD = [REDACTED]"
    assert redact.redact("password=") == "password="
    assert redact.redact("password =") == "password ="


def test_private_key_block():
    block = (
        "-----BEGIN PRIVATE KEY-----\n"
        "MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC...\n"
        "-----END PRIVATE KEY-----\n"
    )
    assert redact.redact(block) == "[REDACTED]\n"
    mixed = (
        "text -----BEGIN EC PRIVATE KEY-----\n"
        "AAA\n"
        "-----END EC PRIVATE KEY----- more"
    )
    assert redact.redact(mixed) == "text [REDACTED] more"


def test_sk_ghp_tokens():
    assert redact.redact("sk-1234567890abcdefghij") == "[REDACTED]"  # exactly 20
    assert redact.redact("sk-" + "a" * 25) == "[REDACTED]"
    assert redact.redact("sk-1234567890abcdefghi") == "sk-1234567890abcdefghi"  # 19 chars
    assert redact.redact("sk-live_51abcdef") == "sk-live_51abcdef"  # underscore breaks the run
    assert redact.redact("ghp_" + "a" * 36) == "[REDACTED]"  # exactly 36
    assert redact.redact("ghp_" + "a" * 35) == "ghp_" + "a" * 35  # 35 chars


def test_slack_tokens():
    for prefix in ("xoxb", "xoxp", "xoxa", "xoxr", "xoxs"):
        assert redact.redact(f"{prefix}-12345-abcd-SECRET") == "[REDACTED]", prefix


def test_overlapping_secrets_stable():
    assert (
        redact.redact("Authorization: Bearer sk-1234567890abcdefghij")
        == "Authorization: Bearer [REDACTED]"
    )
    assert redact.redact("password=sk-1234567890abcdefghij") == "password=[REDACTED]"
    # re-redacting is idempotent
    once = redact.redact("token=hunter2")
    assert redact.redact(once) == once


def test_benign_text_unchanged():
    assert redact.redact("git commit -m 'fix: typo'") == "git commit -m 'fix: typo'"
    assert redact.redact("ls -la /usr/bin") == "ls -la /usr/bin"
    assert redact.redact("http://example.com/x?id=1") == "http://example.com/x?id=1"
    assert redact.redact("nopasswordhere=ok") == "nopasswordhere=ok"
    assert redact.redact("") == ""
    assert redact.redact("   ") == "   "


def test_redact_is_idempotent_and_never_crashes():
    assert redact.redact(None) is None
    for text in ("password=s3cr3t", "AKIAIOSFODNN7EXAMPLE", "ghp_" + "z" * 40):
        assert redact.redact(redact.redact(text)) == redact.redact(text)
