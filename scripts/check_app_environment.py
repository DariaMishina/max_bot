#!/usr/bin/env python3
"""Validate one App API environment without printing its secrets."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", required=True, type=Path)
    parser.add_argument("--expected", required=True, choices=("staging", "production"))
    parser.add_argument("--compare-with", type=Path)
    args = parser.parse_args()

    if not args.env_file.is_file():
        parser.error(f"environment file does not exist: {args.env_file}")
    os.environ["APP_CONFIG_FILE"] = str(args.env_file)

    from app.config import AppSettings, app_config

    if app_config.app_environment != args.expected:
        parser.error(
            f"expected {args.expected}, got {app_config.app_environment} in {args.env_file}"
        )
    if args.compare_with:
        if not args.compare_with.is_file():
            parser.error(f"comparison environment file does not exist: {args.compare_with}")
        other = AppSettings(_env_file=args.compare_with)
        plain_fields = (
            "app_db_name",
            "app_db_user",
            "app_api_public_url",
            "app_api_port",
            "app_rustore_key_id",
        )
        duplicate_fields = [
            name for name in plain_fields if getattr(app_config, name) == getattr(other, name)
        ]
        secret_fields = (
            "app_db_password",
            "app_jwt_secret",
            "app_rustore_private_key",
            "app_rustore_callback_key",
        )
        for name in secret_fields:
            left = getattr(app_config, name)
            right = getattr(other, name)
            left_value = left.get_secret_value() if left is not None else ""
            right_value = right.get_secret_value() if right is not None else ""
            if left_value and left_value == right_value:
                duplicate_fields.append(name)
        if duplicate_fields:
            parser.error(
                "environments share values that must be separate: "
                + ", ".join(sorted(duplicate_fields))
            )
    print(
        "environment-check: OK "
        f"environment={app_config.app_environment} "
        f"database={app_config.app_db_name} "
        f"port={app_config.app_api_port} "
        f"sandbox={str(app_config.app_rustore_sandbox).lower()}"
    )


if __name__ == "__main__":
    main()
