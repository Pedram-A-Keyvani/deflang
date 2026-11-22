"""`def-lang check`: read a program without running it, and list its errors.

Statements run as always (use, def, language, comment is, argument is), so the
defs are known. Other lines are only read into a tree, never run: `start the server`
opens no port and `give weight` asks nothing. Only `X means Y` runs, because the lines
below it are read with it.

What a line can't know without running is guessed from the defs' Python bodies: an
`as written` argument that a body stores under (`self.variables[A0]`, `self.share(A0`)
is a variable's name, so `x is 5` makes `x` known; any other is code, and is read too.
"""
import ast
import re

from deflang.definition import SLOT_REGEX
from deflang.exception import DefException
from deflang.tree import Call, Name

_NAME = re.compile(r"self\.variables(?:\[|\.setdefault\(|\.get\()\s*a\[(\d+)\]|self\.share\(\s*a\[(\d+)\]")
_FIXED_NAME = re.compile(r"""self\.variables\[\s*["'](\w+)["']\s*\]""")
_ALIAS = re.compile(r"self\.alias\(")
_WORDS = re.compile(r"[\w ]+")


def check_line(engine, line: str):
    _walk(engine, engine._parser.parse(line), strict=True)
    # an answer isn't known without running: the lines below it are read either way
    engine.answer = True


def check_bodies(engine, path, started):
    """Compile the Python bodies of the file's defs, so a syntax error shows on its def line."""
    for definition, number in started:
        if definition.language != "python":
            continue
        try:
            definition.function("self, BODY, VAR, fill" if definition.is_language else "self, a")
        except DefException as error:
            engine.problems.append((path, number, " ".join(map(str, error.args))))


def _known(engine, name: str) -> bool:
    if name in engine.variables:
        return True
    try:
        ast.literal_eval(name)
        return True
    except (ValueError, SyntaxError):
        return False


def _walk(engine, node, strict: bool):
    """strict: the line itself. In code an `as written` def gets (like `> 0` in
    `all of x are > 0`), only a plain word that is unknown is an error."""
    if isinstance(node, Name):
        if not _known(engine, node.name) and (strict or _WORDS.fullmatch(node.name)):
            raise DefException(f"unknown name '{node.name}'")
    elif isinstance(node, Call):
        if not node.definition.as_written:
            for argument in node.arguments:
                _walk(engine, argument, strict)
            return
        if node.definition.language is None:
            # a def-lang body: its lines with the words put in, as when it runs
            for line in node.definition.lines():
                text = SLOT_REGEX.sub(lambda m: node.arguments[int(m.group(1))], line).strip()
                if text and text != node.text.strip():
                    try:
                        _walk(engine, engine._parser.parse(text), strict=False)
                    except RecursionError:
                        pass
            return
        if not node.definition.python:
            return  # another language's body: not def-lang
        body = "\n".join(node.definition.body)
        if _ALIAS.search(body):
            node.evaluate(engine)
            return
        for name in _FIXED_NAME.findall(body):
            engine.variables.setdefault(name, None)
        names = {int(n) for pair in _NAME.findall(body) for n in pair if n}
        for index in sorted(names):
            if index < len(node.arguments):
                text = node.arguments[index].strip()
                for name in [text] + text.split():
                    engine.variables.setdefault(name, None)
        for index, text in enumerate(node.arguments):
            text = text.strip()
            if index in names or not text or text == node.text.strip():
                continue
            try:
                _walk(engine, engine._parser.parse(text), strict=False)
            except RecursionError:
                pass


def check(path, program_dir, texts=None):
    """The problems of the program at path: [(file, line, message)], and the files read."""
    from deflang.execute import Execute
    engine = Execute()
    engine.checking = True
    engine.program_dir = program_dir
    engine.texts = dict(texts or {})
    path = path.resolve()
    engine._imported.add(path)
    text = engine.texts[path] if path in engine.texts else path.read_text()
    engine._read(path, text.splitlines())
    return sorted(engine.problems, key=lambda p: (str(p[0]), p[1])), sorted(engine._imported)
