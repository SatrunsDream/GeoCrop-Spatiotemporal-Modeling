#!/usr/bin/env python3
"""
Write ~/.netrc for NASA Earthdata (URS) and OPeNDAP so Daymet THREDDS/OPeNDAP downloads work.
Both ``urs.earthdata.nasa.gov`` and ``opendap.earthdata.nasa.gov`` use the same login/password.

Option A — non-interactive (e.g. CI or one-off shell):
  export EARTHDATA_USERNAME='your_login'
  export EARTHDATA_PASSWORD='your_password'
  python scripts/setup_earthdata_netrc.py

Option B — interactive:
  python scripts/setup_earthdata_netrc.py
  (prompts for username and password; nothing is printed to the log)

Register at https://urs.earthdata.nasa.gov if needed.
"""

from __future__ import annotations

import getpass
import netrc
import os
import stat
import sys
from pathlib import Path


def main() -> None:
    home = Path.home()
    path = home / ".netrc"
    urs = "urs.earthdata.nasa.gov"
    opendap = "opendap.earthdata.nasa.gov"

    existing = path.read_text(encoding="utf-8") if path.is_file() else ""
    if urs in existing and opendap in existing:
        print(f"{path} already has {urs} and {opendap}.")
        return

    user = os.environ.get("EARTHDATA_USERNAME", "").strip()
    password = os.environ.get("EARTHDATA_PASSWORD", "").strip()

    if path.is_file() and urs in existing and opendap not in existing:
        auth = netrc.netrc(path).authenticators(urs)
        if auth:
            user, _account, password = auth
        if not password and not user:
            print("Could not read URS credentials from .netrc; set EARTHDATA_* or run on a fresh file.", file=sys.stderr)
            sys.exit(1)

    if not user:
        user = input("Earthdata username: ").strip()
    if not password:
        password = getpass.getpass("Earthdata password: ")

    if not user or not password:
        print("Username and password are required.", file=sys.stderr)
        sys.exit(1)

    lines: list[str] = []
    if urs not in existing:
        lines.append(f"machine {urs} login {user} password {password}\n")
    if opendap not in existing:
        lines.append(f"machine {opendap} login {user} password {password}\n")
    if not lines:
        print(f"{path} already configured.")
        return

    with open(path, "a", encoding="utf-8") as f:
        if existing and not existing.endswith("\n"):
            f.write("\n")
        f.writelines(lines)

    path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    print(f"Updated {path} (chmod 600): added {len(lines)} machine line(s).")


if __name__ == "__main__":
    main()
