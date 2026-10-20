"""Verify that tracked uv toolchain references use one version."""

from __future__ import annotations

import argparse

from .uv_tools import check_uv_versions


def main() -> None:
    """Validate and print the synchronized uv version."""
    parser = argparse.ArgumentParser(description=__doc__)
    try:
        version = check_uv_versions()
    except ValueError as exc:
        parser.error(str(exc))
    print(f"uv toolchain references are synchronized at {version}.")


if __name__ == "__main__":
    main()
