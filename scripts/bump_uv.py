"""Update every tracked uv toolchain reference to one release."""

from __future__ import annotations

import argparse

from .uv_tools import update_uv_version


def main() -> None:
    """Parse the requested uv version and synchronize repository references."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", help="Bare semantic version, such as 0.13.4.")
    args = parser.parse_args()
    try:
        update_uv_version(args.version)
    except ValueError as exc:
        parser.error(str(exc))
    print(f"Updated uv toolchain references to {args.version}.")


if __name__ == "__main__":
    main()
