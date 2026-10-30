"""The (mock) Service Binding Manager.

Given the fully qualified name of an FPB (usually a usage with redefined
parameters), it fetches the parameter values from the model, invokes the
bound Python service, and prints the out parameters with their computed
values.

Binding approaches, tried in this order for `invoke`:
  1. metadata — the FPB definition carries @ServiceBinding/@ParameterBinding
  2. csv      — a mapping row exists in bindings/*.csv or generated/*.csv
  3. pull     — the definition is listed in bindings/pull_registry.csv; the
                SBM launches the script and the script calls back into the
                SBM API (get_value / deliver_result) itself
"""

import csv
import importlib
import re
import subprocess
import sys
from pathlib import Path

from .model_repo import ActionDef, ActionUsage, ModelRepository, parse_value

REPO_ROOT = Path(__file__).resolve().parent.parent
MODEL_DIR = REPO_ROOT / "model"
BINDINGS_DIR = REPO_ROOT / "bindings"
GENERATED_DIR = REPO_ROOT / "generated"
PULL_REGISTRY = BINDINGS_DIR / "pull_registry.csv"

if str(REPO_ROOT) not in sys.path:          # so 'services.*' etc. import cleanly
    sys.path.insert(0, str(REPO_ROOT))


class SbmError(Exception):
    pass


def _fmt(value):
    return repr(value) if isinstance(value, str) else str(value)


def _csv_rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.reader(f):
            if row and not row[0].lstrip().startswith("#"):
                yield [cell.strip() for cell in row]


class ServiceBindingManager:

    def __init__(self, model_dir=None):
        if model_dir is not None:
            # a model kept in another project: its services live next to it,
            # so that project's root (the model dir's parent) must import too
            project_root = str(Path(model_dir).resolve().parent)
            if project_root not in sys.path:
                sys.path.insert(0, project_root)
        self.repo = ModelRepository(model_dir or MODEL_DIR)
        self.csv_bindings = {}    # def fqn -> {"function": str, "in": {}, "out": {}}
        self.pull_registry = {}   # def fqn -> script path (relative to repo root)
        self._load_inventory()

    def _load_inventory(self):
        csv_files = [p for p in sorted(BINDINGS_DIR.glob("*.csv"))
                     if p != PULL_REGISTRY]
        csv_files += sorted(GENERATED_DIR.glob("*.csv"))
        for path in csv_files:
            for fqn, kind, target in _csv_rows(path):
                if kind == "function":
                    self._csv_entry(fqn)["function"] = target
                elif kind in ("in", "out"):
                    owner, param = fqn.rsplit("::", 1)
                    self._csv_entry(owner)[kind][param] = target
                else:
                    raise SbmError(f"{path.name}: unknown row kind '{kind}'")
        if PULL_REGISTRY.exists():
            for fqn, script in _csv_rows(PULL_REGISTRY):
                self.pull_registry[fqn] = script

    def _csv_entry(self, def_fqn):
        return self.csv_bindings.setdefault(
            def_fqn, {"function": None, "in": {}, "out": {}})

    # ------------------------------------------------------------------
    # API used by pull-style services (approach 1)
    # ------------------------------------------------------------------

    def get_value(self, param_fqn):
        value = self.repo.parameter_value(param_fqn)
        print(f"[SBM] value request: {param_fqn} = {_fmt(value)}")
        return value

    def deliver_result(self, fpb_fqn, results):
        print(f"[SBM] service delivered its result for '{fpb_fqn}'")
        self._print_results(fpb_fqn, results)

    # ------------------------------------------------------------------
    # invoke (approaches 2, 3, and SBM-driven approach 1)
    # ------------------------------------------------------------------

    def invoke(self, fqn, overrides=None):
        element = self.repo.resolve(fqn)
        definition = self.repo.definition_of(element)
        print(f"[SBM] invoking FPB '{fqn}'"
              + (f" (definition: {definition.fqn})"
                 if isinstance(element, ActionUsage) else ""))

        approach = self.approach_for(definition)
        if approach is None:
            raise SbmError(
                f"no binding known for '{definition.fqn}'. Annotate it, add it "
                f"to the CSV inventory, register a pull script — or run:\n"
                f"  python -m sbm generate {definition.fqn}")

        if approach == "pull":
            self._invoke_pull(fqn, definition)
            return

        values = self._gather_in_values(element, definition, overrides)
        if approach == "metadata":
            print("[SBM] binding approach: model metadata (@ServiceBinding)")
            sb = definition.metadata["ServiceBinding"]
            module, function = sb["module"], sb["function"]
            names = {p.name: p.metadata.get("ParameterBinding", {})
                            .get("pythonName", p.name)
                     for p in definition.parameters}
        else:
            print("[SBM] binding approach: CSV inventory")
            entry = self.csv_bindings[definition.fqn]
            if not entry["function"]:
                raise SbmError(f"CSV binding for '{definition.fqn}' has no "
                               f"'function' row")
            module, function = entry["function"].rsplit(":", 1)
            names = {**entry["in"], **entry["out"]}

        kwargs = {}
        for p in definition.params("in"):
            py_name = names.get(p.name, p.name)
            if p.name not in values:          # optional and left unbound
                print(f"[SBM]   in  {p.name} unbound (optional)"
                      f"  ->  python '{py_name}' omitted")
                continue
            kwargs[py_name] = values[p.name]
            print(f"[SBM]   in  {p.name} = {_fmt(values[p.name])}"
                  f"  ->  python '{py_name}'")

        print(f"[SBM] calling {module}.{function}"
              f"({', '.join(f'{k}={_fmt(v)}' for k, v in kwargs.items())})")
        try:
            fn = getattr(importlib.import_module(module), function)
        except (ImportError, AttributeError) as e:
            raise SbmError(f"cannot load service '{module}:{function}': {e}")
        try:
            result = fn(**kwargs)
        except NotImplementedError as e:
            raise SbmError(f"the bound service is not implemented yet: {e}")

        results = self._map_result(definition, names, result)
        self._print_results(fqn, results)
        return results          # {out param name: value}, for programmatic callers

    def approach_for(self, definition):
        if "ServiceBinding" in definition.metadata:
            return "metadata"
        if definition.fqn in self.csv_bindings:
            return "csv"
        if definition.fqn in self.pull_registry:
            return "pull"
        return None

    def _invoke_pull(self, fqn, definition):
        script = self.pull_registry[definition.fqn]
        print(f"[SBM] binding approach: pull (registered script '{script}')")
        print(f"[SBM] launching the service; it will call back for its values")
        print("-" * 60, flush=True)
        subprocess.run([sys.executable, str(REPO_ROOT / script), fqn],
                       check=True, cwd=REPO_ROOT)

    def _gather_in_values(self, element, definition, overrides=None):
        values = self.repo.effective_values(element)
        values.update(overrides or {})
        missing = [p.name for p in definition.params("in")
                   if p.name not in values and not p.optional]
        if missing:
            raise SbmError(
                f"in parameter(s) of '{element.fqn}' have no bound value: "
                f"{', '.join(missing)} (redefine them in a usage or pass --set)")
        return values

    def _map_result(self, definition, names, result):
        outs = definition.params("out")
        if isinstance(result, dict):
            results = {}
            for p in outs:
                key = names.get(p.name, p.name)
                if key not in result:
                    raise SbmError(f"service result has no key '{key}' for out "
                                   f"parameter '{p.name}' (got: {list(result)})")
                results[p.name] = result[key]
            return results
        if len(outs) == 1:
            return {outs[0].name: result}
        raise SbmError(f"service returned a single value but "
                       f"'{definition.fqn}' has {len(outs)} out parameters")

    def _print_results(self, fpb_fqn, results):
        print(f"[SBM] ---- results of '{fpb_fqn}' ----")
        for name, value in results.items():
            print(f"[SBM]   out {name} = {_fmt(value)}")

    # ------------------------------------------------------------------
    # +1: generate a service stub and its CSV mapping
    # ------------------------------------------------------------------

    def generate(self, fqn, force=False):
        definition = self.repo.definition_of(self.repo.resolve(fqn))
        snake = re.sub(r"(?<!^)(?=[A-Z])", "_", definition.name).lower()
        module_name = f"{snake}_service"
        py_path = GENERATED_DIR / f"{module_name}.py"
        csv_path = GENERATED_DIR / f"{definition.name}_binding.csv"
        if py_path.exists() and not force:
            raise SbmError(f"'{py_path}' already exists (it may contain your "
                           f"implementation) — use --force to overwrite")

        ins = definition.params("in")
        outs = definition.params("out")
        GENERATED_DIR.mkdir(exist_ok=True)

        signature = ", ".join(p.name for p in ins)
        out_dict = ", ".join(f'"{p.name}": ...' for p in outs)
        py_path.write_text(
            f'"""Generated service stub for {definition.fqn}.\n'
            f"\nFill in the body of {snake}(); the mapping CSV next to this file"
            f"\nis already registered with the Service Binding Manager.\n"
            f'"""\n\n\n'
            f"def {snake}({signature}):\n"
            f"    # TODO: call the real service here and return the out\n"
            f"    # parameter values, e.g.:\n"
            f"    #   return {{{out_dict}}}\n"
            f'    raise NotImplementedError("{module_name}.{snake} is an '
            f'unfilled generated stub")\n',
            encoding="utf-8")

        rows = [f"# generated binding for {definition.fqn}",
                f"{definition.fqn},function,generated.{module_name}:{snake}"]
        rows += [f"{definition.fqn}::{p.name},{p.direction},{p.name}"
                 for p in ins + outs]
        csv_path.write_text("\n".join(rows) + "\n", encoding="utf-8")

        print(f"[SBM] generated service stub:  {py_path.relative_to(REPO_ROOT)}")
        print(f"[SBM] generated CSV mapping:   {csv_path.relative_to(REPO_ROOT)}")
        print(f"[SBM] fill in the stub, then invoke a usage of "
              f"'{definition.fqn}' as usual")
