#!/usr/bin/env python3
"""
Simple CI/CD Homework App
Prints a greeting, writes output to a file, and demonstrates secret handling.
"""

import os
import pathlib
import datetime


def run(output_dir: str = "output") -> None:
    """Main entry point: greet, process, and write result."""
    # 1. Print a greeting
    now = datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    print(f"[{now}] Hello from the CI/CD Homework App!")

    # 2. Read optional secret from environment (masked in logs)
    secret = os.environ.get("APP_SECRET", "")
    if secret:
        masked = secret[:2] + "*" * max(0, len(secret) - 2)
        print(f"[{now}] APP_SECRET is set: {masked}")
    else:
        print(f"[{now}] APP_SECRET is not set (optional).")

    # 3. Write a result file
    out_path = pathlib.Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    result_file = out_path / "result.txt"
    result_file.write_text(
        f"Run timestamp : {now}\n"
        f"Secret present: {'yes' if secret else 'no'}\n"
        f"Status        : OK\n"
    )
    print(f"[{now}] Result written to {result_file}")


if __name__ == "__main__":
    run()
