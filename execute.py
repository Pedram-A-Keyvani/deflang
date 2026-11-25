"""Runs def-lang one line at a time.

A line is, told apart from its start (see KERNEL.md): a statement (`use`, built in,
or one a library declares: `comment is #`), an entry (`language`, `flag`,
`modifier` or `statement`, then a name, with its fields one level in), a modifier in
front of a line (`internal def ...`, `shared visits is 0`), a definition
(`language[flags] pattern`, then its body), or an expression. Expressions are parsed into
a tree with the current definitions (tree.py) and then evaluated.
"""
import ast
import contextlib
import os
import re
from pathlib import Path
from typing import Callable, List, Optional

from deflang import kernel as kernels
from deflang.definition import SLOT_REGEX, Definition
from deflang.exception import DefException
from deflang.tree import Parser
from deflang.kernel import DEFAULT_COMMENT, DEFAULT_INDENT, new_place
from deflang.values import Variables, as_text

_USE = re.compile(r"use\s+(.+)")
_USE_FROM = re.compile(r"(.+?)\s+from\s+(\S+)")  # use visits, total as t from counter
_NOT_A_STATEMENT = object()  # _statement(): no statement's words match the line
_SAME = object()  # own_variables(): the file of the lines running now
# a definition: `language pattern` or `language[flags] pattern`; the pattern after a space
_DEFINITION = re.compile(r"(\w+)(\[[^\]]*\])?\s+(\S.*)")
# an entry: `language html`, `modifier internal`, `statement comment`
_ENTRY = re.compile(r"(language|flag|modifier|statement)(?:\s+(.*))?")
_WORD = re.compile(r"(\w+)\s+(\S.*)")


class Execute:
    def __init__(self, output: Optional[Callable] = None):
        """`output` receives the value of each line inside an imported file,
        and the text of each `backtick` line before it runs."""
        self._output = output
        self.definitions: List[Definition] = []
        # the kernel's tree (kernel.py), which Python bodies see as self[...]; the keys
        # that change with what runs (variables, file, ...) are answered by __getitem__
        self.kernel = kernels.built_in()
        self._alias_cache = ((), [])  # the aliases as compiled patterns, longest first
        # lines a def runs (run_lines) have the indent and comment marker of the file the
        # def was written in, whatever the file being read says
        self._call_indent: Optional[int] = None
        self._call_comment: Optional[str] = None
        # what the entries running now act on, innermost last: self["entry"] (see _do)
        self._entries: List[dict] = []
        # lines that run for an entry's `does` (and what they call): they run even while
        # `check` reads or a file is read again, since they decide how lines are read
        self._acting = False
        # the answer of the last line on each level: a line one level deeper runs
        # only if it is True (see _run_at)
        self._answers: list = []
        # `def-lang check` (check.py): read without running; errors are collected here
        self.checking = False
        self.problems: List[tuple] = []  # (file, line, message)
        self.texts: dict = {}            # file -> its text, instead of what is on disk
        self._imported = set()
        self._import_dirs: List[Path] = []
        self._import_files: List[Path] = []
        # each imported file and its time when it was read, to see if it changed
        self._file_times = {}
        # folder of the program being run; relative paths start here
        self.program_dir: Optional[Path] = None
        self._parser = Parser(self)
        self._current_entry: Optional[kernels.Entry] = None  # the entry whose fields are being read
        self._line_number = 0  # the line of the file being read, for an entry's place
        self.reloading = False  # reload(): only what defines runs again
        self.clean()

    def clean(self):
        """Forget values and the def being written. Definitions and imports stay."""
        self._current_def: Optional[Definition] = None
        # each file's variables and the shared names it uses, and the shared values;
        # _variables is what the lines running now see (see Variables)
        for place in self.kernel["files"].values():
            place["variables"].clear()
            place["names"].clear()
        self.kernel["shared"].clear()
        self._place(None)["argument"] = "A"
        self._variables = Variables(None, self._place(None), self.kernel["shared"])
        self._answer = None

    # ------------------------------------------------------------ the kernel's tree: self[...]

    def __getitem__(self, key: str):
        if key == "definitions":
            return self.definitions
        if key == "variables":
            return self._variables
        if key == "file":
            return self._variables.file
        if key == "program":
            return self.program_dir or (self._import_dirs[-1] if self._import_dirs else Path(os.getcwd()))
        if key == "answer":
            return self._answer
        if key == "mode":
            return "checking" if self.checking else "reloading" if self.reloading else "running"
        if key == "entry":
            return self._entries[-1] if self._entries else None
        if key in self.kernel:
            return self.kernel[key]
        raise DefException(f"the kernel has no '{key}' (it has: {', '.join(self.keys())})")

    def __setitem__(self, key: str, value):
        """Only the answer is set; every other part of the tree is changed in place."""
        if key != "answer":
            raise DefException(f"self['{key}'] isn't replaced, only what is in it is changed; only self['answer'] is set")
        self._answer = value

    def keys(self) -> list:
        return [*self.kernel, *kernels.RUNNING]

    def __iter__(self):
        return iter(self.keys())

    def __contains__(self, key) -> bool:
        return key in self.keys()

    def _place(self, file) -> dict:
        """A file's place in the kernel: kernel["files"][file]."""
        return self.kernel["files"].setdefault(file, new_place())

    # the settings of the file being read: its place in the kernel
    def _reading(self) -> dict:
        return self._place(self._import_files[-1] if self._import_files else None)

    @property
    def _comment(self) -> str:
        """`comment is X`: lines starting with X are comments, to the end of the file."""
        return self._call_comment or self._reading()["comment"]

    @_comment.setter
    def _comment(self, value: str):
        self._reading()["comment"] = value

    @property
    def _argument_name(self) -> str:
        """`argument is X`: arguments are X0, X1, ..., to the end of the file."""
        return self._reading()["argument"]

    @_argument_name.setter
    def _argument_name(self, value: str):
        self._reading()["argument"] = value

    @property
    def _indent(self) -> int:
        """`indent N`: N spaces make one level, to the end of the file (a def call: 4)."""
        return self._call_indent or self._reading()["indent"]

    @_indent.setter
    def _indent(self, value: int):
        self._reading()["indent"] = value

    # ------------------------------------------------------------ statements

    def run(self, code: str):
        line = str(code).rstrip("\r\n")
        if not line.strip():
            return None
        # a body in another language keeps its lines as they are: a JavaScript `// ...`
        # there is part of the code, not a def-lang comment
        if line[0].isspace() and self._current_entry is not None:
            return self._entry_line(self._current_entry, line)
        current = self._current_def
        if line[0].isspace() and current is not None:
            # a body is kept as it is written (tabs become `indent` spaces); its language
            # reads it when the def runs (a def-lang body: run_lines)
            current.add_line(self._expand_tabs(line), self._argument_name)
            return None
        if line.lstrip().startswith(self._comment):
            return None

        level = self._level(line)
        if level and self.reloading and not self._acting:
            return None  # a line that belongs to a question: it doesn't run again
        return self._run_at(line.strip(), level)

    def _level(self, line: str) -> int:
        """How many levels a line is indented: `indent` spaces a level, a tab one level."""
        lead = line[:len(line) - len(line.lstrip())]
        width = sum(self._indent if c == "\t" else 1 for c in lead)
        if width % self._indent:
            raise DefException(f"indented {width} spaces, but indent is {self._indent}: use a multiple of {self._indent}: {line.strip()}")
        return width // self._indent

    def _expand_tabs(self, line: str) -> str:
        lead = line[:len(line) - len(line.lstrip())]
        return lead.replace("\t", " " * self._indent) + line[len(lead):]

    def _run_at(self, line: str, level: int):
        """Run a line of `level`. A line belongs to the last line one level up, and runs
        only if that line ran and left self["answer"] True. Before it runs, self["answer"]
        is the answer of the last line on its own level, so a def like `otherwise ?`
        turns around its neighbor's answer, not a deeper line's."""
        answers = self._answers
        if level > len(answers):
            raise DefException(f"indented line with no line above it to belong to: {line}")
        if level:
            above = answers[level - 1]
            if above is None:
                raise DefException(f"indented line, but the line above it gave no answer (self['answer'] is None): {line}")
            if above is not True and not self.checking:
                del answers[level:]
                answers.append(False)  # skipped: the lines below it are skipped too
                return None
        if level < len(answers):
            self._answer = answers[level]
        elif level:
            self._answer = answers[level - 1]
        result, statement = self._line(line, level)
        if not statement:
            del answers[level:]
            answers.append(self._answer)
        return result

    def _line(self, line: str, level: int):
        """A line without its indentation: (its value, whether it was a statement).
        Told apart from its start, in this order: a statement, an entry, a modifier, a
        definition; anything else is an expression."""
        pending, self._current_def = self._current_def, None
        self._end_entry()
        if m := _USE.fullmatch(line):
            self._use(m.group(1).strip())
        elif (value := self._statement(line)) is not _NOT_A_STATEMENT:
            # a statement whose `does` gives a value (`` `line` ``) is like an expression
            return value, value is None
        elif m := _ENTRY.fullmatch(line):
            self._declare(m.group(1), (m.group(2) or "").strip())
        elif (modifiers := self._modifiers(line))[0]:
            return self._modified(modifiers[0], modifiers[1], level, pending)
        elif (m := _DEFINITION.fullmatch(line)) and m.group(1) in self.kernel["language"]:
            self._define(m.group(1), m.group(2), m.group(3), pending)
        elif self.reloading and not self._acting:
            return None, True  # an expression: it doesn't run again
        elif self.checking and not self._acting:
            # read, never run; but an entry's `does` runs: it decides how lines are read
            from deflang.check import check_line
            check_line(self, line)
            return None, False
        else:
            return self._parser.parse(line).evaluate(self), False
        return None, True

    # ------------------------------------------------------------ the kernel's entries

    def _declare(self, kind: str, name: str):
        """`language html`, `modifier internal`, ...: a new entry; its fields follow. One
        that another file declared already replaces it only with `replaces FILE`."""
        if not re.fullmatch(r"[\w-]+", name):
            raise DefException(f"an entry is its kind and a one-word name, like `{kind} {'html' if kind == 'language' else 'name'}`, with its fields below")
        file = self._import_files[-1] if self._import_files else None
        old = self.kernel[kind].get(name)
        if old is not None and old.built_in:
            raise DefException(f"{kind} {name} is built in: it can't be replaced")
        entry = kernels.Entry(kind, name, file=file, line=self._line_number)
        if old is not None and old.file != file:
            entry.replaced = old  # it takes old's place at `replaces` (see _entry_line, _end_entry)
        else:
            if old is not None:
                entry.replaced = old.replaced  # the same file again (reloaded): it still replaces it
            self.kernel[kind][name] = entry
        self._current_entry = entry

    def _end_entry(self):
        """The entry being read ends: one that replaces another file's must have said so."""
        entry, self._current_entry = self._current_entry, None
        if entry is not None and entry.replaced is not None and "replaces" not in entry.fields:
            old = entry.replaced
            error = DefException(f"{entry.kind} {entry.name} is there already (declared in {old.file.name if old.file else 'the program'}): "
                                 f"to replace it, write `replaces {self._use_name(old.file)}` under `{entry.kind} {entry.name}`")
            error.line = entry.line
            raise error

    def _use_name(self, path: Optional[Path]) -> str:
        """How `use` names a file: `language/css`, `core`, `def/helpers`."""
        if path is None:
            return "FILE"
        if (path.parent / "library.toml").is_file():
            from deflang import libraries
            name = libraries.read(path.parent)["name"]
            return name if path.stem == "main" else f"{name}/{path.stem}"
        try:
            return path.relative_to(self["program"]).with_suffix("").as_posix()
        except ValueError:
            return path.stem

    def _entry_line(self, entry, line: str):
        """A line under an entry: a field one level in, or `does`'s Python further in."""
        expanded = self._expand_tabs(line)
        width = len(expanded) - len(expanded.lstrip())
        if entry.reading_does and width > self._indent:
            entry.does.add_line(expanded, self._argument_name)
            return None
        text = line.strip()
        if text.startswith(self._comment):
            return None
        entry.reading_does = False
        if width != self._indent:
            raise DefException(f"the fields of {entry.kind} {entry.name} are one level in: {text}")
        names = sorted(kernels.FIELDS[entry.kind], key=len, reverse=True)
        found = next((name for name in names if text == name or text.startswith(name + " ")), None)
        if found is None:
            raise DefException(f"{entry.kind} {entry.name} has no field '{text.split()[0]}' (its fields are: {', '.join(sorted(kernels.FIELDS[entry.kind]))})")
        value = text[len(found):].strip()
        if found == "does":
            m = re.fullmatch(r"in\s+(\w+)(\[[^\]]*\])?", value)
            if m is None:
                raise DefException(f"`does` says the language of its body: does in def, does in python{', not does ' + value if value else ''}")
            if m.group(1) not in self.kernel["language"]:
                raise DefException(f"does in {m.group(1)}: there is no language {m.group(1)} yet (use language/{m.group(1)})")
            # its body runs where the entry acts, in the variables of that line; its flags
            # say how it gets its arguments (`does in def[written]`: their words)
            entry.does = Definition(f"{entry.kind} {entry.name}", language=m.group(1), file=entry.file,
                                    indent=self._indent, comment=self._comment, in_place=True)
            entry.does.flags = self._flags(m.group(2), m.group(1))
            for name, words in entry.does.flags.items():
                self._do(self.kernel["flag"][name], {"definition": entry.does}, words)
            entry.reading_does = True
        elif found == "words":
            entry.words = Definition(value, language="python", file=entry.file)
            entry.words.add_patterns(value, self._argument_name)
        elif found == "replaces":
            old = entry.replaced
            if old is None:
                raise DefException(f"{entry.kind} {entry.name} replaces nothing: no other file declared it before this one")
            if not value or self._resolve(value) != old.file:
                raise DefException(f"{entry.kind} {entry.name} was declared in {self._use_name(old.file)}, not in {value or 'nothing'}: replaces {self._use_name(old.file)}")
            self.kernel[entry.kind][entry.name] = entry  # from here on, it is the one
        entry.fields[found] = value
        return None

    def _do(self, entry, acts_on: dict, arguments=()):
        """Run an entry's `does`, in its language, with what it acts on as self["entry"]
        (`acts_on`: see kernel.py); a statement's words are its arguments. Gives what
        its `does` gives."""
        if entry.does is None or not entry.does.body:
            raise DefException(f"{entry.kind} {entry.name} has no `does`: write `does in LANGUAGE` under it, and its body one level in")
        acts_on["kind"] = entry.kind
        self._entries.append(acts_on)  # the same dict: what `does` changes in it, the caller sees
        try:
            return self.call(entry.does, list(arguments), f"{entry.kind} {entry.name}")
        finally:
            self._entries.pop()

    def _statement(self, line: str):
        """A statement a library declared (`statement NAME` with `words`): run it, and give
        what its `does` returns; _NOT_A_STATEMENT when no statement's words match."""
        for entry in self.kernel["statement"].values():
            if entry.words is not None and (found := entry.words.matches(line)):
                return self._do(entry, {}, found[0].arguments)
        return _NOT_A_STATEMENT

    def _modifiers(self, line: str):
        """The modifiers in front of a line, and the rest: ([entries], rest)."""
        modifiers, rest = [], line
        while (m := _WORD.fullmatch(rest)) and m.group(1) in self.kernel["modifier"]:
            modifiers.append(self.kernel["modifier"][m.group(1)])
            rest = m.group(2)
        return modifiers, rest

    def _modified(self, modifiers: list, rest: str, level: int, pending):
        """`internal def ...` (modifiers in front of a definition) or `shared visits is 0`
        (in front of a name): each modifier's `does` acts on the definition, or the name;
        a name's line then runs as usual."""
        if (m := _DEFINITION.fullmatch(rest)) and m.group(1) in self.kernel["language"]:
            definition = self._define(m.group(1), m.group(2), m.group(3), pending)
            for entry in modifiers:
                self._do(entry, {"definition": definition})
            return None, True
        name = re.match(r"[\w-]+", rest).group(0)
        for entry in modifiers:
            self._do(entry, {"name": name})
        if rest.strip() != name and not self.reloading:
            return self._line(rest, level)  # the rest is an ordinary line
        return None, True

    def _flags(self, text: Optional[str], where: str) -> dict:
        """`[written, cache 60 seconds]`: the flags of a definition, {name: its words}. A
        flag is written as its name, or as its `words` (`cache A0 seconds`): then its
        `does` gets the words in their places, A0, A1, ..., as they are written."""
        if text is None:
            return {}
        inner = text[1:-1].strip()
        if not inner:
            raise DefException(f"no flags in {where}[]: leave the brackets out")
        flags = {}
        for item in (part.strip() for part in inner.split(",")):
            for name, entry in self.kernel["flag"].items():
                if entry.words is not None and (found := entry.words.matches(item)):
                    flags[name] = found[0].arguments
                    break
                if entry.words is None and item == name:
                    flags[name] = []
                    break
            else:
                first = (item.split() or [item])[0]
                if first in self.kernel["flag"]:
                    shape = self.kernel["flag"][first].fields.get("words", first)
                    raise DefException(f"flag {first} is written `{shape}`, not `{item}`")
                raise DefException(f"unknown flag '{item}' (the flags are: {', '.join(sorted(self.kernel['flag']))})")
        return flags

    def _define(self, language: str, flag_text: Optional[str], pattern: str, pending: Optional[Definition]) -> Definition:
        """`def say A0`, `python[written] repeat A0 times : A1`: a definition, whose body
        is the indented lines below it. Several definition lines in a row share one body."""
        flags = self._flags(flag_text, language)

        if pending is not None and not pending.body:
            # another way to write the definition above: they share one body
            if pending.language != language or pending.flags != flags:
                raise DefException(f"a group's definition lines must have the language and flags of its first line: {language}{flag_text or ''} {pattern}")
            pending.add_patterns(pattern.strip(), self._argument_name)
            self._current_def = pending
            return pending

        definition = Definition(
            pattern.strip(),
            language=language,
            file=self._import_files[-1] if self._import_files else None,
            indent=self._indent,
            comment=self._comment,
        )
        definition.flags = flags
        # the flags first: they may change how the pattern is read (its read_pattern)
        for name, words in flags.items():
            self._do(self.kernel["flag"][name], {"definition": definition}, words)
        definition.add_patterns(pattern.strip(), self._argument_name)
        self.definitions.append(definition)
        self._current_def = definition
        return definition

    def _use(self, text: str):
        """`use FILE` runs a file once. `use NAMES from FILE` also gives this file the shared
        variables NAMES of FILE: `use visits from counter`, `use visits as count from counter`."""
        if (m := _USE_FROM.fullmatch(text)) is None:
            if " as " in text:
                raise DefException(f"`as` is only for names: use NAME as OTHER from {text.split(' as ')[0].strip()}")
            self._import(text)
            return
        names, file = m.group(1), m.group(2)
        path = self._import(file)
        theirs = self._place(path)["names"]
        for part in names.split(","):
            name, _, other = part.strip().partition(" as ")
            name, other = name.strip(), other.strip() or name.strip()
            if theirs.get(name) != (path, name):
                raise DefException(f"{file} has no shared variable '{name}': it would say `shared {name}`")
            self._place(self._variables.file)["names"][other] = (path, name)

    def _import(self, name: str) -> Path:
        path = self._resolve(name)
        if path in self._imported:
            return path
        self._imported.add(path)

        try:
            text = self.texts[path] if path in self.texts else path.read_text()
            self._read(path, text.splitlines())
        except BaseException:
            self._imported.discard(path)
            raise
        return path

    def _read(self, path: Path, lines: List[str]):
        """Run the lines of the file at path, as that file: its folder for imports, its defs marked as its."""
        self._file_times[path] = path.stat().st_mtime_ns
        saved = self._answers, self._variables, self._call_indent, self._call_comment, self._entries, self._acting
        # each file starts as if it said `argument is A`, `comment is //` and `indent 4`,
        # with variables of its own
        place = self._place(path)
        place.update({key: value for key, value in new_place().items() if key in ("comment", "argument", "indent")})
        self._answers, self._call_indent, self._call_comment, self._entries, self._acting = [], None, None, [], False
        self._variables = Variables(path, place, self.kernel["shared"])
        self._import_dirs.append(path.parent)
        self._import_files.append(path)
        started = {}  # each def of this file -> the line it starts on, to check its body
        skipping = False

        def failed(error: DefException, number: int):
            number = getattr(error, "line", None) or number  # an entry's error: its own line
            message = " ".join(map(str, error.args))
            if not self.checking:
                raise DefException(f"{path.name}:{number}: {message}")
            self.problems.append((path, number, message))

        try:
            for number, line in enumerate(lines, start=1):
                self._line_number = number
                if skipping and (not line.strip() or line[0].isspace()):
                    continue  # the body of a line that had an error
                skipping = False
                try:
                    result = self.run(line)
                    if result is not None and self._output is not None:
                        self._output(result)
                except DefException as error:
                    failed(error, number)
                    skipping = True
                if self._current_def is not None and id(self._current_def) not in started:
                    started[id(self._current_def)] = (self._current_def, number)
            try:
                self._end_entry()  # the file's last entry
            except DefException as error:
                failed(error, len(lines))
            if self.checking:
                from deflang.check import check_bodies, check_entries
                check_bodies(self, path, started.values())
                check_entries(self, path)
        finally:
            self._current_entry = None
            self._import_dirs.pop()
            self._import_files.pop()
            self._answers, self._variables, self._call_indent, self._call_comment, self._entries, self._acting = saved
            self._current_def = None

    def changed_files(self) -> List[Path]:
        """The imported files saved since they were read."""
        changed = []
        for path, time in list(self._file_times.items()):
            try:
                if path.stat().st_mtime_ns != time:
                    changed.append(path)
            except FileNotFoundError:
                pass  # deleted: its defs stay
        return changed

    def reload(self, path: Path):
        """Read a changed file's defs again, in place of its old ones. Only what defines
        runs again: statements, entries, definitions and modifiers; not its expressions,
        nor the rest of a modifier's line (the `is 0` of `shared visits is 0`). A newly used file
        (like the css library) is loaded; one already loaded is skipped, as always. If
        the new file has an error, the old defs stay."""
        lines = path.read_text().splitlines()
        old = [d for d in self.definitions if d.file == path]
        where = self.definitions.index(old[0]) if old else len(self.definitions)
        before = self.definitions
        self.definitions = [d for d in before if d.file != path]
        self.reloading = True
        try:
            self._read(path, lines)
        except BaseException:
            self.definitions = before
            raise
        finally:
            self.reloading = False
        new = [d for d in self.definitions if d.file == path]
        rest = [d for d in self.definitions if d.file != path]
        # in the same place as before, so which def binds looser stays the same
        self.definitions = rest[:where] + new + rest[where:]

    def _resolve(self, name: str) -> Path:
        """`use x`: x.def next to the file that uses it, or in the program's folder; else a
        library: `use core` is the core library's main.def, `use web/server` the web
        library's server.def. A library is found among the program's libraries, or, for a
        file of a library, among the libraries that library's libraries.toml lists."""
        from deflang import libraries
        program = self.program_dir or Path(os.getcwd())
        for directory in self._import_dirs[-1:] + [program]:
            path = (directory / f"{name}.def").resolve()
            if path.is_file():
                return path
        library, _, inside = name.partition("/")
        folders = [libraries.folder_of(program, library)]
        here = self._import_dirs[-1] if self._import_dirs else None
        if here and (here / "library.toml").is_file():
            folders.append(libraries.folder_of(here, library))
        for folder in filter(None, folders):
            path = (folder / f"{inside or 'main'}.def").resolve()
            if path.is_file():
                return path
            raise DefException(f"cannot use '{name}': the library {library} has no {inside or 'main'}.def")
        raise DefException(f"cannot use '{name}': no file {name}.def, and no library '{library}' ({libraries.HOW_TO_INSTALL})")

    # ------------------------------------------------------------ used by the tree and by def bodies

    def call(self, definition: Definition, arguments: list, text: str):
        """Run a definition: a Python body itself; another language's body by that
        language's `does`, which acts on it (self["entry"]: its body, its values, ...).
        The definition's value is what that `does` gives, or else the body it leaves."""
        # the lines a def runs have levels of their own; its answer still comes out
        outer = self._answers, self._call_indent
        self._answers, self._call_indent = [], DEFAULT_INDENT
        try:
            if definition.language == "python":
                return definition.function()(self, arguments)
            entry = self.kernel["language"].get(definition.language)
            if entry is None or entry.does is None or not entry.does.body:
                raise DefException(f"language {definition.language} has no `does`: write the Python that runs it under `does`, one level in")
            fill = lambda body, values: SLOT_REGEX.sub(lambda m: str(values[int(m.group(1))]), body)
            template = "\n".join(definition.lines())
            acts_on = {"definition": definition, "template": template, "values": arguments, "fill": fill,
                       "body": fill(template, [as_text(value) for value in arguments]),
                       "as written": not definition.reads_values, "in place": definition.in_place}
            result = self._do(entry, acts_on)
            return acts_on["body"] if result is None else result
        except DefException:
            raise
        except RecursionError:
            raise DefException(f"'{text}' never finishes (it keeps matching itself)")
        except Exception as error:
            raise DefException(f"in '{text}': {type(error).__name__}: {error}")
        finally:
            self._answers, self._call_indent = outer

    def run_lines(self, text: str, definition: Optional[Definition] = None):
        """Run lines the way a file's lines run: each on its level, comments skipped, a line
        one level deeper only if the line above it left self["answer"] True. With the
        indent and comment marker `definition` was written with (else 4 and //). Gives the
        value of the last line that had one."""
        # the definition or entry being written stays so: these lines are no part of it
        outer = (self._answers, self._call_indent, self._call_comment, self._entries, self._current_def,
                 self._current_entry, self._acting)
        self._current_def = self._current_entry = None
        # an entry's `does` acts for it, and so does what it calls; lines run without a
        # definition (`run_lines(text)`, like an echoed line) are the program's lines again
        self._acting = definition is not None and (self._acting or definition.in_place)
        if self._entries and self._entries[-1]["kind"] == "language":
            # the lines a language runs act for the entry around it, not for the language
            self._entries = self._entries[:-1]
        self._answers = []
        self._call_indent = definition.indent if definition is not None else DEFAULT_INDENT
        self._call_comment = definition.comment if definition is not None else DEFAULT_COMMENT
        result = None
        try:
            for line in str(text).split("\n"):
                value = self.run(line)
                if value is not None:
                    result = value
        finally:
            (self._answers, self._call_indent, self._call_comment, self._entries, self._current_def,
             self._current_entry, self._acting) = outer
        return result

    @contextlib.contextmanager
    def own_variables(self, file=_SAME):
        """Lines run inside get variables of their own, on top of `file`'s (by default
        the file of the lines running now): what they set is gone afterwards, except the
        shared variables that file uses. A def call has this with the file the def was
        made in; the web server gives one to each request."""
        outer = self._variables, self._answers
        file = self._variables.file if file is _SAME else file
        self._variables, self._answers = Variables(file, self._place(file), self.kernel["shared"], own={}), []
        try:
            yield self._variables
        finally:
            self._variables, self._answers = outer

    def say(self, value):
        """Print a value: through `output` when the REPL gave one, otherwise print()."""
        (self._output or print)(as_text(value))

    def _lookup(self, name: str):
        if name in self._variables:
            return self._variables[name]
        try:
            return ast.literal_eval(name)
        except (ValueError, SyntaxError):
            raise DefException(f"unknown name '{name}'") from None

    def apply_aliases(self, text: str) -> str:
        """`X means Y` (kernel["aliases"]): Y wherever X appears as whole words, longer
        phrases first, so "less than or equal to" isn't broken up by "less than". Only on the
        program's lines: an entry's `does` means what it says."""
        if self._acting:
            return text
        aliases = self.kernel["aliases"]
        state = tuple(aliases.items())
        if state != self._alias_cache[0]:
            compiled = []
            for phrase, words in aliases.items():
                phrase = " ".join(str(phrase).split())
                pattern = re.compile(r"(?<!\S)" + r"\s+".join(map(re.escape, phrase.split())) + r"(?!\S)")
                compiled.append((len(phrase), pattern, str(words).strip()))
            compiled.sort(key=lambda item: -item[0])
            self._alias_cache = (state, compiled)
        for _, pattern, words in self._alias_cache[1]:
            text = pattern.sub(lambda _: words, text)
        return text
