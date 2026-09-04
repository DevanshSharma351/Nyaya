"""Block credentials from being committed.

Runs against staged content, not the working tree, so it sees exactly what
would be committed. Exits non-zero on a finding, which aborts the commit.

Deliberately conservative: a false positive costs one `--no-verify` or one
allowlist entry, whereas a leaked key that reaches a public remote must be
treated as compromised and rotated even after the commit is rewritten.
"""

from __future__ import annotations

import re
import subprocess
import sys

# Provider key formats. Anchored on each vendor's distinctive prefix so that
# ordinary base64 and hashes do not trip them.
PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("OpenAI key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}")),
    ("Anthropic key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}")),
    ("Groq key", re.compile(r"\bgsk_[A-Za-z0-9]{20,}")),
    ("GitHub token", re.compile(r"\b(?:ghp|gho|ghs|ghr)_[A-Za-z0-9]{36}")),
    ("GitHub fine-grained token", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{60,}")),
    ("AWS access key id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Slack token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}")),
    ("Langfuse key", re.compile(r"\b(?:pk|sk)-lf-[A-Za-z0-9-]{20,}")),
    ("Private key block", re.compile(r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----")),
    ("JWT", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")),
]

# A populated assignment to a credential-shaped variable name.
ASSIGNMENT = re.compile(
    r"""(?ix)
    \b(?P<name>[A-Z0-9_]*(?:API_?KEY|SECRET|PASSWORD|PASSWD|TOKEN|CREDENTIAL|PRIVATE_?KEY)[A-Z0-9_]*)
    \s*[:=]\s*
    (?P<quote>["']?)(?P<value>[^\s"',})]{8,})(?P=quote)
    """
)

# Values that look like assignments but are placeholders, local dev defaults, or
# code references rather than live credentials.
BENIGN_VALUES = re.compile(
    r"""(?ix)
    ^(
      | none | null | true | false
      | change_?me | your_?[a-z_]* | replace_?me | example | placeholder | dummy | test
      | \.{3} | x{3,} | \*{3,} | <[^>]+>       # <your-key-here>
      | .*_dev_pw | admin | postgres | nyaya
      | os\.environ.* | os\.getenv.* | settings\..* | self\..*
      | \$\{.*\} | \{\{.*\}\}                   # ${VAR} / {{ var }} interpolation
    )$
    """
)

# In source code, an *unquoted* value is an expression - `token = build(x)`,
# `password = settings.pw` - and carries no secret itself. A literal credential
# in code is quoted. Config formats are the exception: there, `KEY=value` is
# unquoted and is exactly where a real secret lives.
CONFIG_SUFFIXES = {
    ".env",
    ".yaml",
    ".yml",
    ".ini",
    ".cfg",
    ".conf",
    ".toml",
    ".properties",
    ".tfvars",
}
CONFIG_NAMES = re.compile(r"(?:^|/)(?:\.env(?:\..*)?|.*\.env)$")

# Paths where credential-shaped strings are expected and harmless.
SKIP_PATHS = re.compile(r"(?:^|/)(uv\.lock|package-lock\.json|\.venv/|node_modules/)")

# Documentation of the checker itself necessarily contains example patterns.
SELF = "scripts/check_secrets.py"


def staged_files() -> list[str]:
    out = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
        capture_output=True,
        text=True,
        check=True,
    )
    return [f for f in out.stdout.splitlines() if f and not SKIP_PATHS.search(f)]


def staged_content(path: str) -> str:
    out = subprocess.run(["git", "show", f":{path}"], capture_output=True, text=True)
    return out.stdout if out.returncode == 0 else ""


def scan(path: str, content: str) -> list[str]:
    findings: list[str] = []
    for lineno, line in enumerate(content.splitlines(), start=1):
        if "pragma: allowlist secret" in line:
            continue

        for label, pattern in PATTERNS:
            if pattern.search(line):
                findings.append(f"{path}:{lineno}: {label}")

        match = ASSIGNMENT.search(line)
        if match and not _is_benign(path, match.group("quote"), match.group("value")):
            findings.append(
                f"{path}:{lineno}: populated credential variable {match.group('name')!r}"
            )
    return findings


def _is_config_file(path: str) -> bool:
    """Whether unquoted `KEY=value` in this file could be a live credential."""
    from pathlib import PurePosixPath

    return PurePosixPath(path).suffix in CONFIG_SUFFIXES or bool(CONFIG_NAMES.search(path))


def _is_benign(path: str, quote: str, value: str) -> bool:
    """Decide whether an assigned value is a real credential."""
    value = value.strip()
    if BENIGN_VALUES.match(value):
        return True
    # Unquoted in source code -> an expression, not a literal secret. In a
    # config file, unquoted is the normal way to write a real one.
    return bool(not quote and not _is_config_file(path))


def main() -> int:
    files = staged_files()
    if SELF in files:
        files.remove(SELF)  # this file documents the patterns it looks for

    findings: list[str] = []
    scanned = 0
    for path in files:
        content = staged_content(path)
        # Skip binaries by content, not by extension: an extensionless shell
        # script is exactly the sort of file a credential ends up in.
        if not content or "\x00" in content[:8192]:
            continue
        scanned += 1
        findings.extend(scan(path, content))

    if findings:
        print("\n  BLOCKED: possible secrets in staged content\n", file=sys.stderr)
        for f in findings:
            print(f"    {f}", file=sys.stderr)
        print(
            "\n  If a finding is a false positive, append "
            "'# pragma: allowlist secret' to that line.\n"
            "  Never commit a real credential - move it to .env, which is ignored.\n",
            file=sys.stderr,
        )
        return 1

    print(f"secret scan: {scanned} staged file(s), no findings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
