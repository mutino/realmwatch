#!/usr/bin/env python3
"""Prepare monitor directories and an upstream secret. Never rotate an existing secret."""
import os
from pathlib import Path
import secrets

root = Path(__file__).resolve().parent.parent
os.umask(0o077)
(root / "data/public").mkdir(parents=True, exist_ok=True)
(root / "data/public").chmod(0o755)
(root / "data").chmod(0o755)
(root / "secrets").mkdir(mode=0o700, exist_ok=True)
secret = root / "secrets/upstream_secret"
try:
    with secret.open("x") as target:
        target.write(secrets.token_urlsafe(48) + "\n")
    secret.chmod(0o444)  # Container UID 65534; parent remains private on host.
    print("Created upstream secret. Configure the same value in your gateway locally.")
except FileExistsError:
    print("Existing upstream secret preserved.")
print("Prepared data/public and secrets. No game files or containers were changed.")
