"""Generate a PBKDF2-HMAC-SHA256 password hash for SOFIA_ADMIN_PASSWORD_HASH.

    python -m app.cli.hash_password 'your-password'
    python -m app.cli.hash_password 'your-password' --role observer

The value is printed on stdout and is safe to paste into .env. The plaintext is
never stored.
"""

import argparse
import getpass
import sys

from app.core.security import hash_password


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a Next Gent Sofia Trade v1 password hash.")
    parser.add_argument("password", nargs="?", help="Password. Omit to be prompted without echo.")
    parser.add_argument(
        "--role",
        choices=("operator", "observer"),
        default="operator",
        help="Which env var the hash is for (default: operator).",
    )
    args = parser.parse_args(argv)

    password = args.password or getpass.getpass("Password: ")
    if not password:
        print("error: password must not be empty", file=sys.stderr)
        return 2
    if len(password) < 12:
        print(
            "warning: password is shorter than 12 characters",
            file=sys.stderr,
        )

    encoded = hash_password(password)
    var = "SOFIA_ADMIN_PASSWORD_HASH" if args.role == "operator" else "SOFIA_OBSERVER_PASSWORD_HASH"
    print(encoded)
    print("\n# add to .env:", file=sys.stderr)
    print(f"{var}={encoded}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())