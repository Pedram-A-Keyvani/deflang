"""The kernel: one tree with an entry for every language, flag, modifier and statement,
and everything else the interpreter has. A Python body reads and changes it as self[...]:

    kernel["language"]["html"]     how a body runs (and "flag", "modifier", "statement")
    kernel["definitions"]          every definition, in the order made
    kernel["aliases"]              {phrase: words}: what `X means Y` adds
    kernel["files"][PATH]          a file's "comment", "argument", "indent", "variables",
                                   and "names": the shared variables it uses
    kernel["shared"]               {(FILE, NAME): value}: the shared variables' values
    kernel["variables"]            what the running code sees (see values.Variables)
    kernel["file"]                 the file running now
    kernel["program"]              the program's folder
    kernel["answer"]               the last question's answer
    kernel["store"]["web"]         a library's own state, made on first use

What the interpreter does stays a method: self.run(text), self.say(value).

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

# the fields each kind may have (`does` and `replaces` are every kind's)
FIELDS = {
    "language": {"does", "editor", "flags", "replaces"},
    "flag": {"does", "takes", "replaces"},
    "modifier": {"does", "applies to", "replaces"},
    "statement": {"does", "words", "replaces"},
}

APPLIES_TO = ("definition", "name")

# the keys of the tree that change with what runs; the rest are kept in one dict
RUNNING = ("definitions", "variables", "file", "program", "answer")
DEFAULT_COMMENT, DEFAULT_ARGUMENT, DEFAULT_INDENT = "//", "A", 4


def new_place() -> dict:
    """A file's place in the kernel, kernel["files"][PATH]: its settings as read so far
    (each file starts with them), its variables, and the shared variables it names."""
    return {"comment": DEFAULT_COMMENT, "argument": DEFAULT_ARGUMENT, "indent": DEFAULT_INDENT,
            "variables": {}, "names": {}}


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
    # the entry of another file it replaces: it takes its place only with `replaces FILE`
    replaced: Optional["Entry"] = None

    def accepts(self, flag: str) -> bool:
        """Whether this language takes the flag: def and python take every flag; another
        language, those its `flags` field lists."""
        if self.built_in:
            return True
        return flag in [f.strip() for f in self.fields.get("flags", "").split(",") if f.strip()]


def built_in() -> dict:
    """The kernel a program starts with (the keys that don't change with what runs)."""
    from collections import defaultdict
    kernel = {kind: {} for kind in KINDS}
    kernel.update(aliases={}, files={}, shared={}, store=defaultdict(dict))
    for name in ("def", "python"):
        kernel["language"][name] = Entry("language", name, built_in=True)
    for name in ("written", "regex"):
        kernel["flag"][name] = Entry("flag", name, built_in=True)
    for name in ("use", "comment", "argument", "indent", "error"):
        kernel["statement"][name] = Entry("statement", name, built_in=True)
    return kernel
