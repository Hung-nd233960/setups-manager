"""setups: check this machine against the Setups conventions.

setups check                 run every check (exit 1 if anything needs attention)
setups check --quick         skip the slow ones (cache sizes, online updates)
setups check --group repos   only some groups (or --only <id>); --json for tools and agents
setups list                  list the checks
setups tui                   the terminal UI (for people; agents use the commands above)
"""

import argparse
import json
import sys
from collections import Counter

from setups_manager import __version__
from setups_manager.context import Context
from setups_manager.model import Result, Status
from setups_manager.registry import GROUPS, REGISTRY
from setups_manager.runner import run_all, select

LABELS = {
    Status.OK: "ok",
    Status.WARN: "WARN",
    Status.ERROR: "ERROR",
    Status.SKIP: "skip",
}


def summary(results: list[Result]) -> dict[str, int]:
    counts = Counter(r.status for r in results)
    return {str(s): counts.get(s, 0) for s in Status}


def print_text(results: list[Result]) -> None:
    group_of = {c.id: c.group for c in REGISTRY.values()}
    width = max((len(r.check) for r in results), default=0)
    group = None
    for r in results:
        if group_of[r.check] != group:
            group = group_of[r.check]
            print(f"\n== {group}")
        print(f"  {LABELS[r.status]:<5}  {r.check:<{width}}  {r.title}")
        if r.status.needs_attention:
            indent = " " * (width + 11)
            for line in r.detail.splitlines():
                print(f"{indent}{line}")
            if r.fix:
                ask = " (asks first)" if r.fix.confirm else ""
                print(f"{indent}fix: {r.fix.label}{ask}")
                if r.fix.command:
                    print(f"{indent}     $ {' '.join(r.fix.command)}")
    counts = summary(results)
    print("\n== summary: " + ", ".join(f"{n} {s}" for s, n in counts.items() if n))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="setups",
        description="Check this machine against the Setups conventions.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("check", help="run the checks")
    run.add_argument("--json", action="store_true", help="machine-readable output")
    run.add_argument("--quick", action="store_true", help="skip slow checks")
    run.add_argument(
        "--group", action="append", choices=GROUPS, help="only this group (repeatable)"
    )
    run.add_argument(
        "--only", action="append", metavar="ID", help="only this check (repeatable)"
    )
    commands.add_parser("list", help="list the checks")
    commands.add_parser(
        "tui", help="open the terminal UI (interactive; not for agents)"
    )
    args = parser.parse_args(argv)

    if args.command == "tui":
        from setups_manager.tui.app import SetupsApp  # lazy: `check` stays Textual-free

        SetupsApp().run()
        return 0

    ctx = Context.detect()
    if args.command == "list":
        for c in select(ctx):
            slow = " (slow)" if c.slow else ""
            print(f"{c.group:<8} {c.id:<13} {c.description}{slow}")
        return 0

    try:
        checks = select(ctx, ids=args.only, groups=args.group, quick=args.quick)
    except ValueError as e:
        parser.error(str(e))
    if not args.json:
        print(f"Running {len(checks)} checks...", file=sys.stderr)
    results = run_all(checks, ctx)
    if args.json:
        report = {
            "summary": summary(results),
            "results": [r.to_dict() for r in results],
        }
        print(json.dumps(report, indent=2))
    else:
        print_text(results)
    return 1 if any(r.status.needs_attention for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
