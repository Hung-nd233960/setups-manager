"""Command-line entry point for setups-manager."""

import argparse

from setups_manager import __version__


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="setups-manager", description="Check and manage the Setups machine configuration (CLI now, Textual TUI next).")
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    parser.parse_args(argv)
    print("Hello from setups-manager!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
