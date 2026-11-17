"""Key-shaped fixtures built at runtime so no literal secret is committed."""

FAKE_AWS = "AK" + "IA" + "A" * 16
FAKE_ANTHROPIC = "sk-" + "ant-api03-" + "x" * 24
FAKE_STRIPE_LIVE = "sk_" + "live_" + "a" * 24
FAKE_GITHUB = "gh" + "p_" + "a" * 36
FAKE_PRIVATE_KEY = "-----BEGIN RSA " + "PRIVATE KEY-----"
