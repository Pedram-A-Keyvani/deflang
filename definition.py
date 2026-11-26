"""A definition, `LANGUAGE[FLAGS] PATTERN` and its body: its patterns and its body.

Patterns are readable:  `python A0 is between A1 and A2`
  - words and symbols are fixed words,
  - A0, A1, ... are arguments,
  - (A0: regex) is an argument that only matches that regex,
  - "A0" is an argument that only matches a text.

A definition has three hooks, with the kernel's defaults; a flag or a modifier may
change them (the core library's words do, like `set pattern to regex`):
  - read_pattern(text, argument_name): its pattern's text, as regexes;
  - read_argument(text, read): an argument's text, as what the body gets; the default
    reads it as an expression, for its value; text that is kept stays its words;
  - seen_by(file): whether a line of that file may use it.

The body is kept as it is written; its language runs it (Python is built in).
"""
import ast
import builtins
import re
import textwrap
from dataclasses import dataclass, field
from functools import cached_property
from typing import Callable, Iterable, List, Optional

from deflang.exception import DefException
from deflang.values import Code, Line, as_text, number, parse_number, as_code

# where argument N goes in a def-lang body line
_SLOT = "{}"
SLOT_REGEX = re.compile("(\\d+)")


def argument_regex(name: str) -> re.Pattern:
    """Matches argument placeholders such as A0, A1 (also right after a regex escape like \\sA1)."""
    return re.compile(rf"(?:(?<!\w)|(?<=\\\w)){re.escape(name)}(\d+)(?!\w)")


def _closing_paren(text: str, start: int) -> int:
    depth = 1
    i = start
    while i < len(text):
        if text[i] == "\\":
            i += 2
            continue
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    raise DefException(f"missing ')' in: {text}")


def readable_to_regex(text: str, argument_name: str) -> str:
    restricted = re.compile(rf"\({re.escape(argument_name)}(\d+):")
    argument = re.compile(rf"{re.escape(argument_name)}(\d+)")
    tokens = []  # (is_symbol, regex)
    pos = 0
    while pos < len(text):
        if text[pos].isspace():
            pos += 1
            continue
        m = restricted.match(text, pos)
        if m:
            end = _closing_paren(text, m.end())
            tokens.append((False, f"(?P<a{m.group(1)}>{text[m.end():end].strip()})"))
            pos = end + 1
            continue
        end = pos
        while end < len(text) and not text[end].isspace():
            end += 1
        word = text[pos:end]
        pos = end
        # an argument with a symbol right after it, like `A1,` in `A0 and A1, as A2`
        if (m := re.fullmatch(rf"({re.escape(argument_name)}\d+)([^\w\s\"]+)", word)) is not None:
            word, pos = m.group(1), end - len(m.group(2))  # the symbol is the next word
        if m := argument.fullmatch(word):
            tokens.append((False, rf"(?P<a{m.group(1)}>[\s\S]+)"))
        elif (m := argument.fullmatch(word[1:-1])) and word[0] == word[-1] == '"':
            # "A0": a text value; its quotes count as fixed words (empty groups)
            tokens.append((True, rf"()(?P<a{m.group(1)}>\ue000\d+\ue001)()"))
        else:
            tokens.append((not any(c.isalnum() for c in word), f"({re.escape(word)})"))

    regex = ""
    for i, (is_symbol, part) in enumerate(tokens):
        if i:
            # `A0 + A1` also matches "2+3", but `A0 is A1` needs the spaces
            regex += r"\s*" if is_symbol or tokens[i - 1][0] else r"\s+"
        regex += part
    return regex


def read_readable(text: str, argument_name: str) -> List[str]:
    """The kernel's way to read a pattern (a definition's `read_pattern`, until an entry
    changes it): words, A0, (A0: regex), "A0". One regex."""
    return [readable_to_regex(text, argument_name)]


def read_regex(text: str, argument_name: str) -> List[str]:
    """A raw regular expression, as the `regex` flag's `set pattern to regex` writes it.
    Kept here as a function so a compiled definition can be restored from its mode."""
    restricted = re.compile(r"\(" + re.escape(argument_name) + r"(\d+):\s*")
    argument = re.compile(r"(?:(?<!\w)|(?<=\\\w))" + re.escape(argument_name) + r"(\d+)(?!\w)")
    alternatives = []
    for one in text.split(" or "):
        one = restricted.sub(lambda m: "(?P<a" + m.group(1) + ">", one.strip())
        alternatives.append(argument.sub(lambda m: "(?P<a" + m.group(1) + r">[\s\S]+)", one))
    return alternatives


def read_value(text: str, read: Callable):
    """The kernel's way to read an argument (a definition's `read_argument`, until an
    entry changes it): `read(text)` reads it as an expression, run for its value."""
    return read(text)


def seen_everywhere(file) -> bool:
    """The kernel's answer to which files see a definition (its `seen_by`): every file."""
    return True


_PROBE = object()


def _read_written(text: str, read: Callable):
    """A definition that keeps its arguments' words."""
    return text


def _read_kept(engine=None):
    """A definition that keeps lines to run later, in the file of the calling line."""
    if engine is None:
        return lambda text, read: Line(text)
    return lambda text, read: Line(text, engine["file"])


@dataclass
class Match:
    definition: "Definition"
    match: re.Match
    pattern_index: int
    ambiguous: Optional[list] = None  # the files that define this same phrase, none in scope (tree._scoped)

    @cached_property
    def keyword_spans(self) -> frozenset:
        """Positions of the fixed words, e.g. `is` in `A0 is A1`."""
        named = set(self.match.re.groupindex.values())
        return frozenset(
            self.match.span(group)
            for group in range(1, self.match.re.groups + 1)
            if group not in named and self.match.start(group) != -1
        )

    @cached_property
    def arguments(self) -> List[str]:
        names = sorted(self.match.re.groupindex, key=lambda n: int(n[1:]))
        return [self.match.group(name).strip() for name in names]


@dataclass
class Hook:
    """A piece of behavior an entry adds to a cycle: a Definition, not a Python closure,
    so it travels in a language snapshot and a compiled build."""
    cycle: str
    phase: str
    definition: "Definition"
    owner: str  # the declaring entry: FILE/NAME, or NAME for lines typed in


@dataclass
class Definition:
    source: str
    language: Optional[str] = None  # the body's language: def, python, html, ...
    file: Optional[object] = None    # the .def file it was read from (a Path), None if typed in
    flags: dict = field(default_factory=dict)  # its flags: {"written": None, "cache": "60"}
    indent: int = 4                  # the indent and comment marker of its file where it
    comment: str = "//"              # was written, for its body's lines (run_lines)
    in_place: bool = False           # an entry's `does`: it runs where the entry acts
    read_pattern: Callable = field(default=read_readable, repr=False)
    read_argument: Callable = field(default=read_value, repr=False)
    seen_by: Callable = field(default=seen_everywhere, repr=False)
    # the modes the three hooks were set to, so a compiled definition restores them
    # without pickling the library's local functions and lambdas
    pattern_mode: str = "readable"
    argument_mode: str = "values"
    visibility: str = "everywhere"
    patterns: List[re.Pattern] = field(default_factory=list)
    body: List[str] = field(default_factory=list)
    hooks: List[Hook] = field(default_factory=list, repr=False)  # cycle hooks an entry attached
    _function: Optional[Callable] = field(default=None, repr=False)

    @property
    def python(self) -> bool:
        return self.language == "python"

    @property
    def reads_values(self) -> bool:
        """Whether its arguments are read as expressions, for their values (the kernel's
        way), rather than kept as the words they are written with."""
        return self.read_argument("x", lambda text: _PROBE) is _PROBE

    def add_patterns(self, source: str, argument_name: str):
        """One definition line. Several in a row share the body below them."""
        for regex in self.read_pattern(source.strip(), argument_name):
            try:
                self.patterns.append(re.compile(regex))
            except re.error as error:
                raise DefException(f"invalid def pattern '{source.strip()}': {error}")

    def add_line(self, line: str, argument_name: str):
        slot = (lambda m: f"a[{m.group(1)}]") if self.python else (lambda m: _SLOT.format(m.group(1)))
        self.body.append(argument_regex(argument_name).sub(slot, line))
        self._function = None

    def restore_hooks(self, engine=None):
        """Rebuild the three hooks from their modes. Library bodies set them with local
        functions and lambdas, which a build cannot pickle; the modes can."""
        flags = self.flags or {}
        pattern = getattr(self, "pattern_mode", None) or ("regex" if "regex" in flags else "readable")
        argument = getattr(self, "argument_mode", None) or ("written" if "written" in flags else
                                                             "kept" if "later" in flags else "values")
        visibility = getattr(self, "visibility", None) or "everywhere"
        self.pattern_mode, self.argument_mode, self.visibility = pattern, argument, visibility
        self.read_pattern = read_regex if pattern == "regex" else read_readable
        self.read_argument = (_read_written if argument == "written" else
                              _read_kept(engine) if argument == "kept" else read_value)
        self.seen_by = (lambda file: file == self.file) if visibility == "file" else seen_everywhere

    def __getstate__(self):
        state = dict(self.__dict__)
        # compiled Python bodies and library-local functions are rebuilt, not pickled
        state["_function"] = None
        state["read_pattern"] = None
        state["read_argument"] = None
        state["seen_by"] = None
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)
        self._function = None
        self.restore_hooks()

    def matches(self, text: str, pattern_indices: Optional[Iterable[int]] = None) -> List[Match]:
        """Run all patterns, or only the ones the language's word index picked."""
        indices = range(len(self.patterns)) if pattern_indices is None else pattern_indices
        return [
            Match(self, m, index)
            for index in indices
            if (m := self.patterns[index].fullmatch(text)) is not None
        ]

    def lines(self) -> List[str]:
        """The body, without its common indentation."""
        return textwrap.dedent("\n".join(self.body)).splitlines()

    def function(self, parameters: str = "self, a") -> Callable:
        """A Python body compiled once into `__body(parameters)`."""
        if self._function is None:
            body = textwrap.dedent("\n".join(self.body)) or "pass"
            source = f"def __body({parameters}):\n" + textwrap.indent(body, "    ")
            namespace = {
                "__builtins__": builtins,
                "ast": ast,
                "number": number,
                "parse_number": parse_number,
                "as_code": as_code,
                "as_text": as_text,
                "Code": Code,
                "Line": Line,
                "DefException": DefException,
            }
            try:
                exec(compile(source, f"<def {self.source}>", "exec"), namespace)
            except SyntaxError as error:
                raise DefException(f"syntax error in body of 'def {self.source}': {error.msg} (line {error.lineno})")
            self._function = namespace["__body"]
        return self._function
