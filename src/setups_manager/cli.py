"""setups: check this machine against the Setups conventions.

setups check                 run every check (exit 1 if anything needs attention)
setups check --quick         skip the slow ones (cache sizes, online updates)
setups check --group repos   only some groups (or --only <id>); --json for tools and agents
setups list                  list the checks
setups fix --list            the results that have a fix command (with their keys)
setups fix <key>... [--yes]  run those fixes (confirm-fixes need --yes), then re-check
setups tui                   the terminal UI (for people; agents use the commands above)
"""

import argparse
import json
import sys
from collections import Counter

from setups_manager import __version__, actions, shell
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


def print_fixable(targets: list[actions.FixTarget]) -> None:
    if not targets:
        print("Nothing to fix automatically.")
    for t in targets:
        ask = " (asks first)" if t.fix.confirm else ""
        print(f"{t.key}  {t.result.title}")
        print(f"    fix: {t.fix.label}{ask}")
        print(f"    $ {' '.join(t.command)}")


def run_fixes(args: argparse.Namespace, ctx: Context, parser) -> int:
    """`setups fix`: list the fixes, or run the named ones. Never prompts."""
    if args.list:
        checks = select(ctx, quick=args.quick)
        print_fixable(actions.fixable(run_all(checks, ctx)))
        return 0
    keys = list(dict.fromkeys(args.keys))
    if not keys:
        parser.error("give one or more fix keys, or --list")
    if bad := [k for k in keys if ":" not in k]:
        parser.error(f"not a fix key (expected <check>:<index>): {', '.join(bad)}")
    try:
        checks = select(ctx, ids={k.rsplit(":", 1)[0] for k in keys})
    except ValueError as e:
        parser.error(str(e))
    by_key = {t.key: t for t in actions.fixable(run_all(checks, ctx))}
    if missing := [k for k in keys if k not in by_key]:
        print(f"No automatic fix for: {', '.join(missing)}", file=sys.stderr)
        return 2
    if not args.yes and (asks := [k for k in keys if by_key[k].fix.confirm]):
        # nothing runs, not even the fixes that would not ask
        print("These fixes ask first; nothing was run. Add --yes to run them:")
        print_fixable([by_key[k] for k in asks])
        return 2
    failed = False
    for key in keys:
        target = by_key[key]
        print(f"== {key}: {target.fix.label}")
        print(f"$ {' '.join(target.command)}", flush=True)
        for item in actions.run_fix(target):
            if isinstance(item, shell.Exit):
                print(f"exit {item.code}")
                failed = failed or item.code != 0
            else:
                print(item, flush=True)
    print("\nRe-checking:", file=sys.stderr)
    print_text(run_all(checks, ctx))
    return 1 if failed else 0


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
    fix = commands.add_parser(
        "fix",
        help="list or run the fixes of failing checks",
        description="Run the fix commands that checks suggest. Keys come from "
        "`setups fix --list` (<check>:<index>). Fixes marked 'asks first' need --yes.",
    )
    fix.add_argument("keys", nargs="*", metavar="KEY", help="e.g. repos:2")
    fix.add_argument("--list", action="store_true", help="list fixable results")
    fix.add_argument(
        "--quick", action="store_true", help="with --list: skip slow checks"
    )
    fix.add_argument("--yes", action="store_true", help="also run fixes that ask first")
    commands.add_parser(
        "tui", help="open the terminal UI (interactive; not for agents)"
    )
    args = parser.parse_args(argv)

    if args.command == "tui":
        from setups_manager.tui.app import SetupsApp  # lazy: `check` stays Textual-free

        SetupsApp().run()
        return 0

    ctx = Context.detect()
    if args.command == "fix":
        return run_fixes(args, ctx, parser)
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
