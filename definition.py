"""A user definition created with `def ...`: its patterns and its body.

Patterns are readable by default:  `def A0 is between A1 and A2`
  - words and symbols are fixed words,
  - A0, A1, ... are arguments,
  - (A0: regex) is an argument that only matches that regex.
`def regex ...` keeps the old raw-regex patterns (alternatives split by " or ").

Bodies are def-lang lines by default. A flag that names a language makes the
body that language: `def python ...` bodies are Python (built in), and any other
language is declared with `language NAME` and a Python body that runs it (like the
html library's `language html`).
"""
import ast
import builtins
import re
import textwrap
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from deflang.exception import DefException
from deflang.values import Code, as_text, number, parse_number, as_code

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


def regex_to_regex(text: str, argument_name: str) -> str:
    restricted = re.compile(rf"\({re.escape(argument_name)}(\d+):\s*")
    regex = restricted.sub(lambda m: f"(?P<a{m.group(1)}>", text)
    return argument_regex(argument_name).sub(lambda m: rf"(?P<a{m.group(1)}>[\s\S]+)", regex)


@dataclass
class Match:
    definition: "Definition"
    match: re.Match
    pattern_index: int

    @property
    def keyword_spans(self) -> frozenset:
        """Positions of the fixed words, e.g. `is` in `A0 is A1`."""
        named = set(self.match.re.groupindex.values())
        return frozenset(
            self.match.span(group)
            for group in range(1, self.match.re.groups + 1)
            if group not in named and self.match.start(group) != -1
        )

    @property
    def arguments(self) -> List[str]:
        names = sorted(self.match.re.groupindex, key=lambda n: int(n[1:]))
        return [self.match.group(name).strip() for name in names]


@dataclass
class Definition:
    source: str
    as_written: bool = False
    regex: bool = False
    language: Optional[str] = None  # the body's language; None is def-lang
    is_language: bool = False        # the runner of a `language NAME` declaration
    file: Optional[object] = None    # the .def file it was read from (a Path), None if typed in
    flags: dict = field(default_factory=dict)  # its flags: {"written": None, "cache": "60"}
    internal: bool = False           # only its own file sees it (the `internal` modifier)
    patterns: List[re.Pattern] = field(default_factory=list)
    body: List[str] = field(default_factory=list)
    _function: Optional[Callable] = field(default=None, repr=False)

    @property
    def python(self) -> bool:
        return self.language == "python"

    def add_patterns(self, source: str, argument_name: str):
        """One `def` line. Several def lines in a row share the body below them."""
        texts = source.split(" or ") if self.regex else [source]
        for text in texts:
            convert = regex_to_regex if self.regex else readable_to_regex
            regex = convert(text.strip(), argument_name)
            try:
                self.patterns.append(re.compile(regex))
            except re.error as error:
                raise DefException(f"invalid def pattern '{text.strip()}': {error}")

    def add_line(self, line: str, argument_name: str):
        slot = (lambda m: f"a[{m.group(1)}]") if self.python else (lambda m: _SLOT.format(m.group(1)))
        self.body.append(argument_regex(argument_name).sub(slot, line))
        self._function = None

    def matches(self, text: str) -> List[Match]:
        return [
            Match(self, m, index)
            for index, pattern in enumerate(self.patterns)
            if (m := pattern.fullmatch(text)) is not None
        ]

    def lines(self) -> List[str]:
        """The def-lang body, without its common indentation."""
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
                "DefException": DefException,
            }
            try:
                exec(compile(source, f"<def {self.source}>", "exec"), namespace)
            except SyntaxError as error:
                raise DefException(f"syntax error in body of 'def {self.source}': {error.msg} (line {error.lineno})")
            self._function = namespace["__body"]
        return self._function
