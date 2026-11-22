"""Runs def-lang one line at a time.

A line is either a statement (comment / use / argument / def / def body /
indented conditional line / error) or an expression. Expressions are parsed into a tree with
the current definitions (tree.py) and then evaluated.
"""
import ast
import contextlib
import os
import re
from pathlib import Path
from typing import Callable, List, Optional

from deflang.definition import SLOT_REGEX, Definition
from deflang.exception import DefException
from deflang.tree import Parser
from deflang.values import Code, Shared, Variables, as_text, as_code

_COMMENT = re.compile(r"comment\s+is\s+(.+)")
DEFAULT_COMMENT = "//"
_USE = re.compile(r"use\s+(.+)")
_USE_FROM = re.compile(r"(.+?)\s+from\s+(\S+)")  # use visits, total as t from counter
_ARGUMENT = re.compile(r"argument\s+is\s+(.+)")
_INDENT = re.compile(r"indent\s+(\d+)\s*")
# `shared NAME`, and maybe more: `shared visits is 0` is `shared visits`, then `visits is 0`
_SHARED = re.compile(r"shared\s+(\w+)(.*)")
_SAME = object()  # own_variables(): the file of the lines running now
DEFAULT_INDENT = 4  # spaces per level; a tab is always one level
_DEF = re.compile(r"def\s+(.+)")
_DEF_FLAG = re.compile(r"(as\s+written|regex)\s+")
_LANGUAGE = re.compile(r"language\s+(\w+)\s*")
_WORD = re.compile(r"(\w+)\s+")
# Python is the one language built into the interpreter; others are declared
# with `language NAME` (see the core library's primitives.def).
BUILT_IN_PYTHON = "built-in python"
_ERROR = re.compile(r"error\s+(.+)")
_ECHO = re.compile(r"`(.+)`\s*")  # `line` prints the line, then runs it


class Execute:
    def __init__(self, output: Optional[Callable] = None):
        """`output` receives the value of each line inside an imported file,
        and the text of each `backtick` line before it runs."""
        self._output = output
        self.definitions: List[Definition] = []
        self._aliases: List[tuple] = []
        # `comment is X`: lines starting with X are comments, from there to the end of
        # the file; each file starts with the default
        self._comment = DEFAULT_COMMENT
        self._indent = DEFAULT_INDENT
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
        # languages: the flag word -> its runner (a Definition with a Python body)
        self.languages = {"python": BUILT_IN_PYTHON}
        self._stores = {}
        self.clean()

    def clean(self):
        """Forget values and the def being written. Definitions and imports stay."""
        self._argument_name = "A"
        self._current_def: Optional[Definition] = None
        # each file's variables, and the shared ones; `variables` is what the lines
        # running now see (see Variables)
        self._files = {}
        self._shared = Shared()
        self.variables = Variables(None, self._files, self._shared)
        self.answer = None
        self._error_message = ""

    # ------------------------------------------------------------ statements

    def run(self, code: str):
        line = str(code).rstrip("\r\n")
        if not line.strip():
            return None
        # a body in another language keeps its lines as they are: a JavaScript `// ...`
        # there is part of the code, not a def-lang comment
        current = self._current_def
        if line[0].isspace() and current is not None and current.language is not None:
            # its own language checks its indentation; tabs become `indent` spaces
            current.add_line(self._expand_tabs(line), self._argument_name)
            return None
        if line.lstrip().startswith(self._comment):
            return None

        level = self._level(line)
        if level and current is not None:
            # a def-lang body: stored with 4 spaces a level, the way it runs (_run_body)
            current.add_line(" " * DEFAULT_INDENT * level + line.strip(), self._argument_name)
            return None
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
        only if that line ran and left `self.answer` True. Before it runs, `self.answer`
        is the answer of the last line on its own level, so a def like `otherwise ?`
        turns around its neighbour's answer, not a deeper line's."""
        answers = self._answers
        if level > len(answers):
            raise DefException(f"indented line with no line above it to belong to: {line}")
        if level:
            above = answers[level - 1]
            if above is None:
                raise DefException(f"indented line, but the line above it gave no answer (self.answer is None): {line}")
            if above is not True and not self.checking:
                del answers[level:]
                answers.append(False)  # skipped: the lines below it are skipped too
                return None
        if level < len(answers):
            self.answer = answers[level]
        elif level:
            self.answer = answers[level - 1]
        result, statement = self._line(line, level)
        if not statement:
            del answers[level:]
            answers.append(self.answer)
        return result

    def _line(self, line: str, level: int):
        """A line without its indentation: (its value, whether it was a statement)."""
        pending, self._current_def = self._current_def, None
        if m := _ECHO.fullmatch(line):
            if self._output is not None:
                self._output(m.group(1).strip())
            return self._line(m.group(1).strip(), level)
        if m := _SHARED.fullmatch(line):
            name, rest = m.group(1), m.group(2).strip()
            self.share(name)
            if rest:
                # the rest is an ordinary line, with the name in front again
                return self._line(f"{name} {rest}", level)
        elif m := _INDENT.fullmatch(line):
            if int(m.group(1)) < 1:
                raise DefException("indent must be 1 or more")
            self._indent = int(m.group(1))
        elif m := _COMMENT.fullmatch(line):
            self._comment = m.group(1).strip()
        elif m := _USE.fullmatch(line):
            self._use(m.group(1).strip())
        elif m := _ARGUMENT.fullmatch(line):
            self._argument_name = m.group(1).strip()
        elif m := _DEF.fullmatch(line):
            self._define(m.group(1), pending)
        elif m := _LANGUAGE.fullmatch(line):
            self._language(m.group(1))
        elif m := _ERROR.fullmatch(line):
            self._error_message = m.group(1).strip()
            if not self.checking:
                raise DefException(self._error_message)
        elif self.checking:
            from deflang.check import check_line
            check_line(self, line)
            return None, False
        else:
            return self._parser.parse(line).evaluate(self), False
        return None, True

    def _language(self, name: str):
        """`language NAME`: the indented Python below runs the bodies of `def NAME ...`.
        It gets `BODY` (the def's body text), `VAR` (the argument values) and
        `fill(BODY, values)` (puts values where A0, A1, ... are) and returns the def's value."""
        if name == "python":
            return  # built in; the core library declares it too, to document it
        runner = Definition(f"language {name}", language="python", is_language=True)
        self.languages[name] = runner
        self._current_def = runner

    def _define(self, rest: str, pending: Optional[Definition]):
        flags = set()
        language = None
        while True:
            if m := _DEF_FLAG.match(rest):
                flags.add(" ".join(m.group(1).split()))
            elif language is None and (m := _WORD.match(rest)) and m.group(1) in self.languages:
                language = m.group(1)
                flags.add(language)
            else:
                break
            rest = rest[m.end():]

        if pending is not None and not pending.body and not pending.is_language:
            # another way to write the def above: they share one body
            first = {name for name, on in [("as written", pending.as_written),
                                           ("regex", pending.regex)] if on} | ({pending.language} if pending.language else set())
            if flags and flags != first:
                raise DefException(f"a def group's lines must have the flags of its first line ({', '.join(sorted(first)) or 'none'}): def {rest}")
            pending.add_patterns(rest.strip(), self._argument_name)
            self._current_def = pending
            return

        definition = Definition(
            rest.strip(),
            as_written="as written" in flags,
            regex="regex" in flags,
            language=language,
            file=self._import_files[-1] if self._import_files else None,
        )
        definition.add_patterns(rest.strip(), self._argument_name)
        self.definitions.append(definition)
        self._current_def = definition

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
        made = self._shared.made.get(path, set())
        for part in names.split(","):
            name, _, other = part.strip().partition(" as ")
            name, other = name.strip(), other.strip() or name.strip()
            if name not in made:
                raise DefException(f"{file} has no shared variable '{name}': it would say `shared {name}`")
            self._shared.bound(self.variables.file)[other] = (path, name)

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
        saved = self._argument_name, self._comment, self._indent, self._answers, self.variables
        # each file starts as if it said `argument is A`, `comment is //` and `indent 4`,
        # with variables of its own
        self._argument_name, self._comment, self._indent, self._answers = "A", DEFAULT_COMMENT, DEFAULT_INDENT, []
        self.variables = Variables(path, self._files, self._shared)
        self._import_dirs.append(path.parent)
        self._import_files.append(path)
        started = {}  # each def of this file -> the line it starts on, to check its body
        skipping = False
        try:
            for number, line in enumerate(lines, start=1):
                if skipping and (not line.strip() or line[0].isspace()):
                    continue  # the body of a line that had an error
                skipping = False
                try:
                    result = self.run(line)
                    if result is not None and self._output is not None:
                        self._output(result)
                except DefException as error:
                    message = " ".join(map(str, error.args))
                    if not self.checking:
                        raise DefException(f"{path.name}:{number}: {message}")
                    self.problems.append((path, number, message))
                    skipping = True
                if self._current_def is not None and id(self._current_def) not in started:
                    started[id(self._current_def)] = (self._current_def, number)
            if self.checking:
                from deflang.check import check_bodies
                check_bodies(self, path, started.values())
        finally:
            self._import_dirs.pop()
            self._import_files.pop()
            self._argument_name, self._comment, self._indent, self._answers, self.variables = saved
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
        """Read a changed file's defs again, in place of its old ones. Only the defs and
        `use` lines, and which names are `shared`: its other lines (like the `is 0` of
        `shared visits is 0`) don't run again. A newly used file
        (like the css library) is loaded; one already loaded is skipped, as always. If
        the new file has an error, the old defs stay."""
        lines = []
        in_def = False
        for line in path.read_text().splitlines():
            top = line.rstrip()
            if (m := _SHARED.fullmatch(top)) is not None:
                in_def = False
                lines.append(f"shared {m.group(1)}")  # not its value again
            elif _DEF.fullmatch(top) or _ARGUMENT.fullmatch(top) or _COMMENT.fullmatch(top) or _INDENT.fullmatch(top) or _USE.fullmatch(top):
                in_def = bool(_DEF.fullmatch(top))
                lines.append(line)
            elif in_def and (not line.strip() or line[0].isspace()):
                lines.append(line)
            else:
                in_def = False
                lines.append("")  # keeps the line numbers of errors right
        old = [d for d in self.definitions if d.file == path]
        where = self.definitions.index(old[0]) if old else len(self.definitions)
        before = self.definitions
        self.definitions = [d for d in before if d.file != path]
        try:
            self._read(path, lines)
        except BaseException:
            self.definitions = before
            raise
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
        # the lines a def runs have levels of their own; its answer still comes out
        outer = self._answers, self._indent
        self._answers, self._indent = [], DEFAULT_INDENT
        try:
            if definition.language is None:
                return self._run_body(definition, arguments)
            runner = self.languages[definition.language]
            if runner is BUILT_IN_PYTHON:
                return definition.function()(self, arguments)
            if not runner.body:
                raise DefException(f"language {definition.language} has no body: indent the Python that runs it below `language {definition.language}`")
            fill = lambda body, values: SLOT_REGEX.sub(lambda m: str(values[int(m.group(1))]), body)
            result = runner.function("self, BODY, VAR, fill")(self, "\n".join(definition.lines()), arguments, fill)
            # what a language makes is code, which another language puts in unescaped
            return Code(result) if isinstance(result, str) else result
        except DefException:
            raise
        except RecursionError:
            raise DefException(f"'{text}' never finishes (it keeps matching itself)")
        except Exception as error:
            raise DefException(f"in '{text}': {type(error).__name__}: {error}")
        finally:
            self._answers, self._indent = outer

    def _run_body(self, definition: Definition, arguments: list):
        """Run a def-lang body with A0, A1, ... replaced by the arguments.
        Its value is the value of the last line that had one.
        Variables it sets are its own and end with it (see own_variables). A `as written`
        def gets the caller's code, so it runs where that code was written: no variables
        of its own."""
        texts = arguments if definition.as_written else [as_code(value) for value in arguments]
        result = None
        with contextlib.nullcontext() if definition.as_written else self.own_variables(definition.file):
            for line in definition.lines():
                value = self.run(SLOT_REGEX.sub(lambda m: texts[int(m.group(1))], line))
                if value is not None:
                    result = value
        return result

    @contextlib.contextmanager
    def own_variables(self, file=_SAME):
        """Lines run inside get variables of their own, on top of `file`'s (by default
        the file of the lines running now): what they set is gone afterwards, except the
        shared variables that file uses. A def call has this with the file the def was
        made in; the web server gives one to each request."""
        outer = self.variables, self._answers
        file = self.variables.file if file is _SAME else file
        self.variables, self._answers = Variables(file, self._files, self._shared, own={}), []
        try:
            yield self.variables
        finally:
            self.variables, self._answers = outer

    def store(self, name: str) -> dict:
        """A library's own state: the same dict every time for the same name."""
        return self._stores.setdefault(name, {})

    def share(self, name: str):
        """`shared NAME`: NAME is a shared variable of this file. This file, its lines and
        its defs use it; other files get it with `use NAME from FILE`."""
        file = self.variables.file
        self._shared.made.setdefault(file, set()).add(name)
        self._shared.bound(file)[name] = (file, name)

    def file_path(self, name: str) -> Path:
        """A file named in a program: relative to the program's folder (also from
        a def file in a sub-folder), not to the folder you started from."""
        path = Path(name)
        if path.is_absolute():
            return path
        base = self.program_dir or (self._import_dirs[-1] if self._import_dirs else Path(os.getcwd()))
        return (base / path).resolve()

    def say(self, value):
        """Print a value: through `output` when the REPL gave one, otherwise print()."""
        (self._output or print)(as_text(value))

    def lookup(self, name: str):
        if name in self.variables:
            return self.variables[name]
        try:
            return ast.literal_eval(name)
        except (ValueError, SyntaxError):
            raise DefException(f"unknown name '{name}'") from None

    def alias(self, phrase: str, replacement: str):
        """`X means Y`: from now on, write Y wherever X appears as whole words."""
        phrase = " ".join(phrase.split())
        words = r"\s+".join(re.escape(word) for word in phrase.split())
        pattern = re.compile(rf"(?<!\S){words}(?!\S)")
        self._aliases = [a for a in self._aliases if a[2] != phrase]
        self._aliases.append((pattern, replacement.strip(), phrase))
        # longer phrases first, so "less than or equal to" isn't broken up by "less than"
        self._aliases.sort(key=lambda a: -len(a[2]))

    def apply_aliases(self, text: str) -> str:
        for pattern, replacement, _ in self._aliases:
            text = pattern.sub(lambda _: replacement, text)
        return text
