"""The kernel: one tree with an entry for every language, flag, modifier and statement.

    kernel["language"]["html"]     how a body runs
    kernel["flag"]["written"]      how one definition works
    kernel["modifier"]["internal"] where something is visible
    kernel["statement"]["comment"] a whole line the reader knows

A file declares an entry with its kind and a one-word name, and its fields one level in:

    language html
        editor html
        does
            ...Python...

The built-in entries are `def` and `python`, the flags `written` and `regex`, and the
statements `use`, `comment`, `argument`, `indent` and `error`. Libraries add the rest.
"""
from dataclasses import dataclass, field
from typing import Optional

from deflang.definition import Definition

KINDS = ("language", "flag", "modifier", "statement")

# what each kind's `does` gets
PARAMETERS = {
    "language": "self, BODY, VAR, fill",  # the def's body text, its argument values, fill()
    "modifier": "self, TARGET",           # the definition, or the name, it modifies
    "flag": "self, TARGET, VALUE",        # the definition, and the flag's value (or None)
    "statement": "self, a",               # the words its `words` matched: A0, A1, ...
}

# the fields each kind may have (`does` is every kind's)
FIELDS = {
    "language": {"does", "editor", "flags"},
    "flag": {"does", "takes"},
    "modifier": {"does", "applies to"},
    "statement": {"does", "words"},
}

APPLIES_TO = ("definition", "name")


@dataclass
class Entry:
    kind: str
    name: str
    fields: dict = field(default_factory=dict)  # field -> its text: "editor" -> "html"
    does: Optional[Definition] = None           # its Python, compiled with PARAMETERS[kind]
    words: Optional[Definition] = None          # a statement's words, as patterns
    file: Optional[object] = None               # the file that declared it; None: built in
    built_in: bool = False
    line: int = 0                               # its line in that file
    reading_does: bool = False                  # while its `does` lines are read

    def accepts(self, flag: str) -> bool:
        """Whether this language takes the flag: def and python take every flag; another
        language, those its `flags` field lists."""
        if self.built_in:
            return True
        return flag in [f.strip() for f in self.fields.get("flags", "").split(",") if f.strip()]


def built_in() -> dict:
    """The kernel a program starts with."""
    kernel = {kind: {} for kind in KINDS}
    for name in ("def", "python"):
        kernel["language"][name] = Entry("language", name, built_in=True)
    for name in ("written", "regex"):
        kernel["flag"][name] = Entry("flag", name, built_in=True)
    for name in ("use", "comment", "argument", "indent", "error"):
        kernel["statement"][name] = Entry("statement", name, built_in=True)
    return kernel
