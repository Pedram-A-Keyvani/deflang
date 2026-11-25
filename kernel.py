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

Built in are only the language `python` (every `does` is Python) and the statement
`use` (it loads the libraries). The rest is declared in libraries, each kind the same
way: `language def`, `flag written`, `modifier shared`, `statement comment`.

A file declares an entry with its kind and a one-word name, and its fields one level in:

    language html
        editor html
        does
            ...Python...
"""
from dataclasses import dataclass, field
from typing import Optional

from deflang.definition import Definition

KINDS = ("language", "flag", "modifier", "statement")

# what an entry acts on, given to its `does` as self["entry"] (see Execute._do):
#   a language:  "definition" (the one that runs), "template" (its body, the places of its
#                arguments marked), "values", "fill", "body" (filled in; the definition's
#                value when `does` ends), "as written" (its arguments are words), "in place"
#   a flag:      "definition" (being made, before its pattern is read); and the words
#                in its places, A0, A1, ..., when it is written by `words`
#   a modifier:  "definition" (just made), or "name"
#   a statement: its words, as the arguments of its `does` (A0, A1, ...)
# A `does` runs where the entry acts: in the variables of the line.

# the fields each kind may have (`does in LANGUAGE` and `replaces` are every kind's)
FIELDS = {
    "language": {"does", "editor", "replaces"},
    "flag": {"does", "words", "replaces"},
    "modifier": {"does", "replaces"},
    "statement": {"does", "words", "replaces"},
}

# the keys of the tree that change with what runs; the rest are kept in one dict
RUNNING = ("definitions", "variables", "file", "program", "answer", "mode", "entry")
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
    does: Optional[Definition] = None           # its body, in the language `does in` names
    words: Optional[Definition] = None          # a statement's words, as patterns
    file: Optional[object] = None               # the file that declared it; None: built in
    built_in: bool = False
    line: int = 0                               # its line in that file
    reading_does: bool = False                  # while its `does` lines are read
    # the entry of another file it replaces: it takes its place only with `replaces FILE`
    replaced: Optional["Entry"] = None


def built_in() -> dict:
    """The kernel a program starts with (the keys that don't change with what runs)."""
    from collections import defaultdict
    kernel = {kind: {} for kind in KINDS}
    kernel.update(aliases={}, files={}, shared={}, store=defaultdict(dict))
    kernel["language"]["python"] = Entry("language", "python", built_in=True)
    kernel["statement"]["use"] = Entry("statement", "use", built_in=True)
    return kernel
