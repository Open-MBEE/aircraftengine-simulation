"""CLI of the mock Service Binding Manager.

Copy of fpb-demo's sbm/ (with the --model-dir and [0..1] optional-parameter
extensions). Here it is run from the repository root as
'python -m SysMLengineMethod2.sbm ...' and loads SysMLengineMethod2/model/
by default; the examples below use fpb-demo's own model names.

    python -m sbm list
    python -m sbm invoke DemoProcesses::scaleByTen [--set param=value ...]
    python -m sbm generate DemoProcesses::ConvertCurrency [--force]

    --model-dir DIR (before the command) loads the *.sysml files from DIR
    instead of ./model; DIR's parent is put on the import path so services
    of that project resolve.
"""

import argparse
import sys

from .core import SbmError, ServiceBindingManager
from .model_repo import ModelError, parse_value


def cmd_list(sbm, _args):
    print("FPB definitions:")
    for d in sbm.repo.defs.values():
        if d.supertype is None:       # skip the library base type itself
            continue
        approach = sbm.approach_for(d) or "UNBOUND"
        params = ", ".join(f"{p.direction} {p.name}" for p in d.parameters)
        print(f"  {d.fqn}  [{approach}]  ({params})")
    print("FPB usages:")
    for u in sbm.repo.usages.values():
        redefs = ", ".join(f"{k}={v!r}" for k, v in u.redefinitions.items())
        print(f"  {u.fqn} : {u.def_name}  ({redefs})")


def cmd_invoke(sbm, args):
    overrides = {}
    for item in args.set or []:
        name, _, raw = item.partition("=")
        if not _:
            raise SbmError(f"--set expects param=value, got '{item}'")
        overrides[name] = parse_value(raw)
    sbm.invoke(args.fqn, overrides)


def cmd_generate(sbm, args):
    sbm.generate(args.fqn, force=args.force)


def main():
    parser = argparse.ArgumentParser(
        prog="python -m sbm", description="Mock Service Binding Manager")
    parser.add_argument("--model-dir", metavar="DIR",
                        help="directory of *.sysml files (default: ./model)")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="list FPB definitions, bindings, and usages")

    p_invoke = sub.add_parser("invoke", help="invoke an FPB by FQN")
    p_invoke.add_argument("fqn", help="e.g. DemoProcesses::scaleByTen")
    p_invoke.add_argument("--set", action="append", metavar="PARAM=VALUE",
                          help="override/bind an in parameter value")

    p_gen = sub.add_parser(
        "generate", help="generate a Python service stub + CSV mapping")
    p_gen.add_argument("fqn", help="FQN of an FPB definition (or usage)")
    p_gen.add_argument("--force", action="store_true",
                       help="overwrite an existing generated stub")

    args = parser.parse_args()
    try:
        sbm = ServiceBindingManager(args.model_dir)
        {"list": cmd_list, "invoke": cmd_invoke,
         "generate": cmd_generate}[args.command](sbm, args)
    except (SbmError, ModelError) as e:
        sys.stdout.flush()
        print(f"[SBM] ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
