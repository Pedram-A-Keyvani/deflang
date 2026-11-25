"""Parse a line into a tree once, then evaluate the tree (see solution.txt)."""
import ast
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, List, Union

from deflang.definition import Definition, Match, read_value
from deflang.exception import DefException
from deflang.values import Line, as_text, parse_number

if TYPE_CHECKING:
    from core.execute import Execute

# Quoted strings are swapped for placeholders before matching, so a pattern
# like `A0 ?` can't match the "?" inside "Is it?".
_PLACEHOLDER = re.compile("(\\d+)")


# ---------------------------------------------------------------- nodes


@dataclass
class Literal:
    value: object

    def evaluate(self, engine: "Execute"):
        return self.value


@dataclass
class Name:
    name: str

    def evaluate(self, engine: "Execute"):
        return engine._lookup(self.name)


@dataclass
class Call:
    definition: Definition
    arguments: List[Union["Node", str]]  # a node, or text kept as its words (read_argument)
    text: str
    lost: bool = False  # read the best it could, but an argument is no value

    def evaluate(self, engine: "Execute"):
        values = [argument if isinstance(argument, str) else argument.evaluate(engine) for argument in self.arguments]
        return engine.call(self.definition, values, self.text)


Node = Union[Literal, Name, Call]


# ---------------------------------------------------------------- parser


def _edges(match):
    """Where a match's fixed words start and end."""
    spans = match.keyword_spans
    return min(s[0] for s in spans), max(s[1] for s in spans)


def is_sentence(match, text: str) -> bool:
    """A definition that keeps its arguments as words and starts the line with two or
    more fixed words, like `api ... runs ...`, `all of ... are ...`: a sentence."""
    return (not match.definition.reads_values and len(match.keyword_spans) >= 2
            and _edges(match)[0] == len(text) - len(text.lstrip()))


def wraps(a, b, text: str) -> bool:
    """Whether match a wraps match b on the line `text`:
    - brackets: a's fixed words surround b's (`api ... runs x is 1 and sends ...`, `is 5 > 3 ?`);
    - a sentence wraps what follows its fixed words (`all of x are > 1`), except a
      closing word at the very end of the line, like the `?` of a question."""
    if len(a.keyword_spans) < 2 or not b.keyword_spans or a.keyword_spans <= b.keyword_spans:
        return False
    first, last = _edges(a)
    inside_first, inside_last = _edges(b)
    if first <= inside_first and inside_last <= last:
        return True
    # a closing word at the very end (a question's `?`) isn't wrapped; a text there
    # (joined text, whose quotes are empty fixed words) is
    closing = inside_last >= len(text.rstrip()) and any(s[0] < s[1] for s in b.keyword_spans)
    return is_sentence(a, text) and inside_first >= last and not closing


class Parser:
    def __init__(self, engine: "Execute"):
        self.engine = engine

    def parse(self, text: str) -> Node:
        """Parsing is a pure function of the text, the language snapshot and the
        environment that affects how a line is read. All of those are in the key of
        the language's one cache; nothing else about the interpreter is."""
        engine = self.engine
        scopes = tuple(tuple(files) for files in engine._scopes_now())
        environment = (scopes, frozenset(engine._variables), engine._acting,
                       engine._variables.file, engine["program"])
        return engine._language.parse(self, text, environment)

    def _parse_uncached(self, text: str) -> Node:
        masked, strings = self._mask_strings(text)
        return self._parse(self.engine.apply_aliases(masked), strings)

    @staticmethod
    def _mask_strings(text: str):
        strings = []

        def replace(m: re.Match):
            strings.append(m.group(1))
            return f"{len(strings) - 1}"

        masked = re.sub(r'"([^"]*)"', replace, text)
        if '"' in masked:
            raise DefException(f"missing closing quote in: {text.strip()}")
        return masked, strings

    @staticmethod
    def _unmask(text: str, strings: List[str]) -> str:
        return _PLACEHOLDER.sub(lambda m: f'"{strings[int(m.group(1))]}"', text)

    def _parse(self, text: str, strings: List[str]) -> Node:
        text = text.strip()
        if not text:
            return Literal(None)

        value = parse_number(text)
        if value is not None:
            return Literal(value)

        if text.startswith("[") and text.endswith("]"):
            try:
                return Literal(ast.literal_eval(self._unmask(text, strings)))
            except (ValueError, SyntaxError):
                pass

        # a text on its own is a value
        if (m := _PLACEHOLDER.fullmatch(text)) is not None:
            return Literal(strings[int(m.group(1))])

        # the best match, unless one of its arguments can't be a value (like the
        # `length of` in `length of "hello"`, read as joined text): then the next
        chosen = None
        for best in self._ranked(text):
            if best.ambiguous:
                raise DefException(self._ambiguous(best, self._unmask(text, strings)))
            node = self._call(best, text, strings)
            if not self._lost(node):
                return node
            chosen = chosen or node
        if chosen is not None:
            chosen.lost = True  # no reading works: the caller tries its next one too
            return chosen
        return Name(self._unmask(text, strings))

    def _call(self, best: Match, text: str, strings: List[str]) -> "Call":
        arguments = best.arguments
        if best.definition.read_argument is read_value:
            nodes = [self._parse(a, strings) for a in arguments]  # the kernel's way: as expressions
        else:
            # its own way (a flag changed it): it gets the words, and `read` reads them
            nodes = [best.definition.read_argument(self._unmask(a, strings), self._read_text) for a in arguments]
        return Call(best.definition, nodes, self._unmask(text, strings))

    def _read_text(self, text: str):
        """Text read as an expression: the default way an argument is read."""
        masked, strings = self._mask_strings(text)
        return self._parse(masked, strings)

    def _lost(self, node: "Call") -> bool:
        """An argument that reads as no value: a name that is no variable."""
        if not node.definition.reads_values:
            if node.definition.language != "def" or any(isinstance(a, Line) for a in node.arguments):
                return False  # Python, ...: what its body does with the words is its own; a line kept for later runs later
            # a def-lang body runs the words as code: they must read as a value
            arguments = []
            for text in node.arguments:
                masked, strings = self._mask_strings(text)
                arguments.append(self._parse(self.engine.apply_aliases(masked), strings))
        else:
            arguments = node.arguments
        for argument in arguments:
            if isinstance(argument, Call) and argument.lost:
                return True
            if isinstance(argument, Name) and argument.name not in self.engine._variables:
                try:
                    ast.literal_eval(argument.name)
                except (ValueError, SyntaxError):
                    return True
        return False

    def _scoped(self, matches: List[Match]) -> List[Match]:
        """Where several files define the same phrase (the same fixed words in the same
        places), only the ones in the line's scope stay (Execute.in_scope). With none, or
        several files', in scope, the first stays, and choosing it is an error (_parse)."""
        groups = {}
        for m in matches:
            if m.keyword_spans:
                arguments = tuple(m.match.span(name) for name in sorted(m.match.re.groupindex))
                groups.setdefault((m.keyword_spans, arguments), []).append(m)
        dropped = set()
        for group in groups.values():
            if len({m.definition.file for m in group}) < 2:
                continue
            scoped = [m for m in group if self.engine.in_scope(m.definition.file)] or group
            dropped.update(id(m) for m in group if not any(m is s for s in scoped[:1]))
            if len({m.definition.file for m in scoped}) > 1:
                scoped[0].ambiguous = sorted({m.definition.file for m in scoped}, key=lambda f: self.engine._use_name(f) if f else "")
        return [m for m in matches if id(m) not in dropped]

    def _ambiguous(self, match: Match, text: str) -> str:
        names = [self.engine._use_name(file) if file is not None else "the program" for file in match.ambiguous]
        return (f"'{text}' is a phrase of {', of '.join(names[:-1])} and of {names[-1]}: say which, "
                f"like `in the scope of {names[0]}, …`")

    def _ranked(self, text: str) -> List[Match]:
        """Pick the definition that becomes the outermost node.

        1. A match whose fixed words are all part of a longer match is dropped,
           e.g. `greater than` loses to `greater than or equal to`, and the `is`
           inside `each of them is` doesn't count as an assignment. A def with
           no fixed words at all, like `(A0: one|two)`, is never dropped.
        2. A match that another one wraps is dropped (see `wraps`): brackets, and sentences.
        3. The same phrase from several files (the same fixed words in the same places):
           the one in the scope of the line (`in the scope of web/http`, see _scoped).
        4. A word list (no fixed words, like the number words) that matches the
           whole text is one value: `one hundred and two`.
        5. Then the def defined first (see the order in the core library), so
           `a is 2 + 3` is `a is (2 + 3)`.
        """
        language = self.engine._language
        definitions = language.refresh(self.engine.definitions, self.engine.kernel["aliases"])
        # the word index picks the patterns that could match this line; the regexes decide
        candidates: List[Match] = []
        for definition_index, pattern_indices in language.candidate_patterns(text).items():
            definition = definitions[definition_index]
            if definition.seen_by(self.engine._variables.file):
                candidates.extend(definition.matches(text, pattern_indices))
        if not candidates:
            return []
        spans = [c.keyword_spans for c in candidates]
        kept = [c for c, s in zip(candidates, spans) if not (s and any(s < other for other in spans))]
        kept = [c for c in kept if not any(wraps(o, c, text) for o in kept if o is not c)]
        kept = self._scoped(kept)
        words = [c for c in kept if not c.keyword_spans]
        order = {id(d): i for i, d in enumerate(definitions)}
        rank = lambda c: (order[id(c.definition)], c.pattern_index)
        return sorted(words, key=rank) + sorted([c for c in kept if c not in words], key=rank)
