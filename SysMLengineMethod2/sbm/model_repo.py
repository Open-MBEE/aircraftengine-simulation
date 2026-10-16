"""Regex-based mini-repository for SysML v2 textual models.

Deliberately NOT a real SysML v2 parser. It supports exactly the subset the
FPB demo uses:

    package P {
        action def Name :> Base {
            @Metadata { attr = "value"; }
            in  param : Type = default { @Metadata { attr = "value"; } }
            in  param : Type[0..1];          # optional: may stay unbound
            out param : Type;
        }
        action name : Name {
            in :>> param = value;
        }
    }
"""

import re
from dataclasses import dataclass, field
from pathlib import Path


class ModelError(Exception):
    pass


@dataclass
class Parameter:
    direction: str                 # 'in' | 'out' | 'inout'
    name: str
    type_name: str | None = None
    default: object = None
    metadata: dict = field(default_factory=dict)   # {metadata name: {attr: value}}
    multiplicity: str | None = None                # e.g. '[0..1]'

    @property
    def optional(self):
        """True for a lower multiplicity bound of 0, e.g. [0..1] or [0..*]."""
        return bool(self.multiplicity
                    and re.match(r"\[\s*0\s*(\.\.|\])", self.multiplicity))


@dataclass
class ActionDef:
    package: str
    name: str
    supertype: str | None = None
    parameters: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    @property
    def fqn(self):
        return f"{self.package}::{self.name}"

    def params(self, direction=None):
        if direction is None:
            return list(self.parameters)
        return [p for p in self.parameters
                if p.direction == direction or p.direction == "inout"]


@dataclass
class ActionUsage:
    package: str
    name: str
    def_name: str
    redefinitions: dict = field(default_factory=dict)   # {param name: value}

    @property
    def fqn(self):
        return f"{self.package}::{self.name}"


# --- lexical helpers ---------------------------------------------------------

_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)
_LINE_COMMENT = re.compile(r"//[^\n]*")

_PACKAGE = re.compile(r"(?:\blibrary\s+)?\bpackage\s+(\w+)\s*\{")
_ACTION_DEF = re.compile(r"\baction\s+def\s+(\w+)\s*(?::>\s*([\w:]+))?\s*\{")
_ACTION_USAGE = re.compile(r"\baction\s+(?!def\b)(\w+)\s*:\s*([\w:]+)\s*\{")
_PARAM = re.compile(
    r"\b(in|out|inout)\s+(\w+)\s*(?::\s*([\w:]+)\s*(\[[^\]]*\])?)?"
    r"\s*(?:=\s*([^;{]+?))?\s*([;{])")
_META_START = re.compile(r"@(\w+)\s*\{")
_ATTR_VALUE = re.compile(r"(\w+)\s*=\s*([^;]+);")
_REDEF = re.compile(
    r"(?:\b(?:in|out|inout)\s+)?(?::>>|\bredefines\b)\s*(\w+)\s*=\s*([^;]+);")


def _strip_comments(text):
    text = _BLOCK_COMMENT.sub("", text)
    text = _LINE_COMMENT.sub("", text)
    return re.sub(r"\bdoc\b", "", text)   # 'doc' keywords left by /* */ removal


def _block(text, brace_idx):
    """Return (body, index of closing brace) for the balanced {...} at brace_idx."""
    depth = 0
    for i in range(brace_idx, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[brace_idx + 1:i], i
    raise ModelError("unbalanced braces in model text")


def parse_value(raw):
    raw = raw.strip()
    if raw.startswith('"') and raw.endswith('"'):
        return raw[1:-1]
    if raw in ("true", "false"):
        return raw == "true"
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        return raw   # unresolved reference etc. — keep the raw text


def _parse_attr_values(meta_body):
    return {m.group(1): parse_value(m.group(2))
            for m in _ATTR_VALUE.finditer(meta_body)}


def _parse_metadata_blocks(body):
    result = {}
    pos = 0
    while (m := _META_START.search(body, pos)):
        meta_body, end = _block(body, m.end() - 1)
        result[m.group(1)] = _parse_attr_values(meta_body)
        pos = end + 1
    return result


def _parse_def_body(body):
    """Sequentially scan a def body for metadata blocks and parameters."""
    params, metadata = [], {}
    pos = 0
    while True:
        m_meta = _META_START.search(body, pos)
        m_param = _PARAM.search(body, pos)
        if not m_meta and not m_param:
            return params, metadata
        if m_meta and (not m_param or m_meta.start() < m_param.start()):
            meta_body, end = _block(body, m_meta.end() - 1)
            metadata[m_meta.group(1)] = _parse_attr_values(meta_body)
            pos = end + 1
        else:
            direction, name, type_name, multiplicity, default, term = m_param.groups()
            param = Parameter(direction, name, type_name,
                              parse_value(default) if default else None,
                              multiplicity=multiplicity)
            if term == "{":
                param_body, end = _block(body, m_param.end() - 1)
                param.metadata = _parse_metadata_blocks(param_body)
                pos = end + 1
            else:
                pos = m_param.end()
            params.append(param)


# --- the repository ----------------------------------------------------------

class ModelRepository:
    """Loads every *.sysml file in a directory and resolves FQNs."""

    def __init__(self, model_dir):
        self.defs = {}     # fqn -> ActionDef
        self.usages = {}   # fqn -> ActionUsage
        for path in sorted(Path(model_dir).glob("*.sysml")):
            self._load_text(path.read_text(encoding="utf-8"))

    def _load_text(self, text):
        text = _strip_comments(text)
        pos = 0
        while (m := _PACKAGE.search(text, pos)):
            pkg_name = m.group(1)
            pkg_body, end = _block(text, m.end() - 1)
            self._load_package(pkg_name, pkg_body)
            pos = end + 1

    def _load_package(self, pkg_name, body):
        for m in _ACTION_DEF.finditer(body):
            def_body, _ = _block(body, m.end() - 1)
            params, metadata = _parse_def_body(def_body)
            d = ActionDef(pkg_name, m.group(1), m.group(2), params, metadata)
            self.defs[d.fqn] = d
        for m in _ACTION_USAGE.finditer(body):
            usage_body, _ = _block(body, m.end() - 1)
            redefs = {r.group(1): parse_value(r.group(2))
                      for r in _REDEF.finditer(usage_body)}
            u = ActionUsage(pkg_name, m.group(1), m.group(2), redefs)
            self.usages[u.fqn] = u

    # -- resolution -----------------------------------------------------------

    def resolve(self, fqn):
        element = self.usages.get(fqn) or self.defs.get(fqn)
        if element is None:
            known = sorted(list(self.usages) + list(self.defs))
            raise ModelError(
                f"unknown element '{fqn}'; known elements:\n  " + "\n  ".join(known))
        return element

    def definition_of(self, element):
        if isinstance(element, ActionDef):
            return element
        d = (self.defs.get(element.def_name)
             or self.defs.get(f"{element.package}::{element.def_name}"))
        if d is None:
            raise ModelError(f"cannot resolve definition '{element.def_name}' "
                             f"of usage '{element.fqn}'")
        return d

    def effective_values(self, element):
        """Definition defaults overlaid with the usage's redefined values."""
        definition = self.definition_of(element)
        values = {p.name: p.default for p in definition.parameters
                  if p.default is not None}
        if isinstance(element, ActionUsage):
            values.update(element.redefinitions)
        return values

    def parameter_value(self, param_fqn):
        """Value of a single parameter given its fully qualified name."""
        try:
            owner_fqn, param_name = param_fqn.rsplit("::", 1)
        except ValueError:
            raise ModelError(f"'{param_fqn}' is not a parameter FQN")
        owner = self.resolve(owner_fqn)
        definition = self.definition_of(owner)
        if param_name not in {p.name for p in definition.parameters}:
            raise ModelError(
                f"'{definition.fqn}' has no parameter '{param_name}' "
                f"(has: {', '.join(p.name for p in definition.parameters)})")
        values = self.effective_values(owner)
        if param_name not in values:
            raise ModelError(f"parameter '{param_fqn}' has no bound value")
        return values[param_name]
