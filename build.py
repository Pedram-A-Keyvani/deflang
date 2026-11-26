"""Ahead-of-time builds of a def-lang program.

`compile` reads a program the way `check` does: definitions, entries, imports and
statements marked `reading` build the language. Expressions and other statements
are recorded, not evaluated, so a build neither prints nor serves nor stops the
program. The artifact is a pickle of the same kernel state the interpreter would
have, plus the lines that still have to run and the file contexts they ran in;
`load` puts it into a fresh Execute, so compile and run share one parser and one
evaluator (see KERNEL.md).

A JSON manifest next to the artifact records the sources it came from, so
`run` can tell whether a build is still fresh.
"""
import json
import pickle
from contextlib import contextmanager
from pathlib import Path
from typing import List, Optional, Tuple

from deflang import kernel as kernels
from deflang.exception import DefException
from deflang.execute import Execute
from deflang.values import Variables

FORMAT = 2
SUFFIX = ".defbuild"


def program_file(name: str) -> Path:
    """A folder is a package: its main.def. `x` is x.def."""
    path = Path(name)
    if path.is_dir():
        return path / "main.def"
    return path if path.suffix == ".def" else Path(f"{path}.def")


def artifact_for(name: str, output: Optional[str] = None) -> Path:
    """Where a build is written: build/NAME.defbuild by default."""
    file = program_file(name).resolve()
    if output:
        given = Path(output)
        return given if given.suffix else given / (file.stem + SUFFIX)
    return file.parent / "build" / (file.stem + SUFFIX)


def manifest_for(artifact: Path) -> Path:
    return artifact.with_name(artifact.name + ".json")


def _settings(place: dict) -> dict:
    """What a compiled build keeps of a file: how it is read, not its values."""
    return {key: place[key] for key in ("comment", "argument", "indent", "names") if key in place}


def compile_program(name: str, output: Optional[str] = None) -> Path:
    """Read `name` without evaluating its expressions and write a build artifact."""
    file = program_file(name).resolve()
    if not file.is_file():
        raise DefException(f"no program {file}")
    execute = Execute(output=lambda value: None)  # a build prints or serves nothing
    execute.program_dir = file.parent
    execute.compiling = True
    for number, line in enumerate(file.read_text().splitlines(), start=1):
        execute._line_number = number
        execute.run(line)

    artifact = {
        "format": FORMAT,
        "program": str(file),
        "definitions": list(execute.definitions),
        "entries": {kind: dict(execute.kernel[kind]) for kind in kernels.KINDS},
        "aliases": dict(execute.kernel["aliases"]),
        "files": {str(path): _settings(place) for path, place in execute.kernel["files"].items()},
        "lines": list(execute.compiled_lines),
    }
    sources = {str(file): file.stat().st_mtime_ns}
    sources.update({str(path): path.stat().st_mtime_ns for path in execute._file_times})

    target = artifact_for(name, output)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("wb") as stream:
        pickle.dump(artifact, stream, protocol=pickle.HIGHEST_PROTOCOL)
    manifest_for(target).write_text(json.dumps({
        "format": FORMAT,
        "program": str(file),
        "artifact": target.name,
        "definitions": len(execute.definitions),
        "lines": len(execute.compiled_lines),
        "sources": sources,
    }, indent=2, sort_keys=True) + "\n")
    return target


def fresh(artifact: Path) -> bool:
    """Whether the build still matches every file it read."""
    manifest = manifest_for(artifact)
    if not artifact.is_file() or not manifest.is_file():
        return False
    try:
        data = json.loads(manifest.read_text())
        return (data.get("format") == FORMAT and
                data.get("artifact") == artifact.name and
                all(Path(path).is_file() and Path(path).stat().st_mtime_ns == time
                    for path, time in data.get("sources", {}).items()))
    except (OSError, ValueError):
        return False


def load(artifact: Path, execute: Execute) -> List[Tuple]:
    """Put a build into `execute`; return its (kind, line, file, number) lines."""
    if not artifact.is_file():
        raise DefException(f"no compiled program {artifact}")
    with artifact.open("rb") as stream:
        data = pickle.load(stream)
    if data.get("format") != FORMAT:
        raise DefException(f"{artifact} is a build of another def-lang version")

    execute.clean()
    execute.compiling = False
    execute.checking = False
    execute.reloading = False
    execute.program_dir = Path(data["program"]).parent
    for kind in kernels.KINDS:
        execute.kernel[kind].clear()
        execute.kernel[kind].update(data["entries"].get(kind, {}))
    execute.kernel["aliases"].clear()
    execute.kernel["aliases"].update(data.get("aliases", {}))
    execute.kernel["files"].clear()
    for name, place in data.get("files", {}).items():
        restored = kernels.new_place()
        restored.update(place)
        execute.kernel["files"][Path(name)] = restored
    execute._set_definitions(list(data.get("definitions", ())))

    # library-local hooks are modes in a build; restore them with this engine, so
    # `later`'s lines remember the file of the line that calls them
    for definition in execute.definitions:
        definition.restore_hooks(execute)
    for kind in kernels.KINDS:
        for entry in execute.kernel[kind].values():
            for definition in (getattr(entry, "does", None), getattr(entry, "words", None)):
                if definition is not None:
                    definition.restore_hooks(execute)
    execute._language.refresh(execute.definitions, execute.kernel["aliases"])
    return [tuple(line) for line in data.get("lines", ())]


@contextmanager
def _replay_file(execute: Execute, path: Optional[Path]):
    """Read recorded lines as the file they came from, without reading it again."""
    if path is None:  # the program itself: Execute already has its place
        yield
        return
    path = Path(path)
    saved = (execute._answers, execute._variables, execute._call_indent, execute._call_comment,
             execute._entries, execute._acting, execute._scope_base, execute._scope_levels,
             execute._current_def, execute._current_entry, execute._line_number)
    execute._answers = []
    execute._call_indent = execute._call_comment = None
    execute._entries, execute._acting = [], False
    execute._scope_base, execute._scope_levels = (), []
    execute._current_def = execute._current_entry = None
    execute._variables = Variables(path, execute._place(path), execute.kernel["shared"])
    execute._import_dirs.append(path.parent)
    execute._import_files.append(path)
    try:
        yield
    finally:
        execute._import_files.pop()
        execute._import_dirs.pop()
        (execute._answers, execute._variables, execute._call_indent, execute._call_comment,
         execute._entries, execute._acting, execute._scope_base, execute._scope_levels,
         execute._current_def, execute._current_entry, execute._line_number) = saved


def run_lines(execute: Execute, lines: List[Tuple], output=None):
    """Run the lines a build recorded, with the same `Execute.run` as the interpreter."""
    contexts = []
    try:
        for kind, line, file, number in lines:
            if kind == "enter":
                context = _replay_file(execute, file)
                context.__enter__()
                contexts.append(context)
            elif kind == "leave":
                if contexts:
                    contexts.pop().__exit__(None, None, None)
            elif kind == "run":
                execute._line_number = number
                result = execute.run(line)
                if result is not None and output is not None:
                    output(result)
    finally:
        for context in reversed(contexts):
            context.__exit__(None, None, None)
