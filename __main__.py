"""The def-lang command:

    python -m deflang                          the console (type lines, then `on` to run them)
    python -m deflang run FILE.def | FOLDER    run a program: a fresh build if there is
                                                one, else the interpreter
        --compiled                              require that build (compile first)
        --interpreter                           read the sources instead
        --debug                                 read the sources in debug mode
    python -m deflang compile FILE | FOLDER [-o PATH]   build ahead of time (build/NAME.defbuild)
    python -m deflang check FILE.def | FOLDER  list its errors without running it
                                               (--json for editors; --text FILE: FILE's
                                               text is read from stdin, saved or not)
    python -m deflang install URL#FOLDER       install a library from a git repo into the project
                                               (libraries/), with the libraries it uses
    python -m deflang install URL#FOLDER --global   the same, into the global folder
    python -m deflang install FOLDER --link    a local library: a folder of the project
    python -m deflang install                  install the program's libraries.toml again
    python -m deflang setup --global-folder PATH   where global libraries are kept
                                               (default ~/.def-lang/libraries)

`install` works on the program in the current folder; `--into FOLDER` picks another.
"""
import re
import sys
from pathlib import Path

from deflang import build, libraries
from deflang.exception import DefException
from deflang.execute import Execute

try:
    import readline  # noqa: F401  arrow keys and history in input()
except ImportError:
    pass

RED = "\u001b[38;5;160m"
GRAY = "\u001b[38;5;244m"
DEFAULT = "\033[0m"


def program_file(name: str) -> Path:
    """A folder is a package: its main.def. `x` is x.def."""
    path = Path(name)
    if path.is_dir():
        return path / "main.def"
    return path if path.suffix == ".def" else Path(f"{path}.def")


def run(name: str, execute: Execute, artifact: Path = None):
    """Run sources, or replay a build through the same Execute and parser."""
    if artifact is not None:
        lines = build.load(artifact, execute)
        build.run_lines(execute, lines, output=lambda value: print(f"{GRAY}{value}{DEFAULT}"))
        return
    file = program_file(name)
    if not file.is_file():
        raise DefException(f"no program {file}")
    execute.program_dir = file.resolve().parent
    for line in file.read_text().splitlines():
        result = execute.run(line)
        if result is not None:
            print(f"{GRAY}{result}{DEFAULT}")


def run_command(rest: list):
    """Choose a run mode. `check` never uses a build."""
    mode = "auto"
    for flag in ("--compiled", "--interpreter", "--debug"):
        if flag in rest:
            mode = flag[2:]
            rest = [item for item in rest if item != flag]
    if len(rest) != 1:
        print(__doc__.strip())
        return 2
    name = rest[0]
    execute = Execute(output=lambda value: print(f"{GRAY}{value}{DEFAULT}"))
    artifact = build.artifact_for(name)
    if mode == "debug":
        print(f"{GRAY}interpreter (debug){DEFAULT}", file=sys.stderr)
        return run(name, execute)
    if mode == "compiled":
        if not build.fresh(artifact):
            raise DefException(f"{artifact} is missing or stale: compile it first")
        return run(name, execute, artifact)
    if mode == "interpreter":
        return run(name, execute)
    return run(name, execute, artifact if build.fresh(artifact) else None)


def compile_command(rest: list):
    output = None
    for flag in ("-o", "--output"):
        if flag in rest:
            at = rest.index(flag)
            if at + 1 >= len(rest):
                raise DefException(f"{flag} needs a path")
            output = rest[at + 1]
            rest = rest[:at] + rest[at + 2:]
            break
    if len(rest) != 1:
        print(__doc__.strip())
        return 2
    print(build.compile_program(rest[0], output))
    return 0


def program_folder(file: Path) -> Path:
    """The program a file belongs to: the nearest folder up with a main.def or a
    libraries.toml, so its imports find the program's libraries."""
    for folder in [file.parent, *file.parent.parents]:
        if (folder / "main.def").is_file() or (folder / "libraries.toml").is_file():
            return folder
    return file.parent


def check(rest: list):
    from deflang.check import check as check_program
    as_json = "--json" in rest
    rest = [r for r in rest if r != "--json"]
    texts = {}
    if "--text" in rest:
        at = rest.index("--text")
        texts[Path(rest[at + 1]).resolve()] = sys.stdin.read()
        rest = rest[:at] + rest[at + 2:]
    if len(rest) != 1:
        print(__doc__.strip())
        return 2
    file = program_file(rest[0]).resolve()
    if not file.is_file() and file not in texts:
        raise DefException(f"no program {file}")
    problems, read = check_program(file, program_folder(file), texts)
    if as_json:
        import json
        print(json.dumps({
            "problems": [{"file": str(f), "line": n, "message": m} for f, n, m in problems],
            "read": [str(f) for f in read],
        }))
    else:
        for f, n, m in problems:
            print(f"{RED}{f}:{n}: {m}{DEFAULT}")
    return 1 if problems else 0


def console():
    print(f"{GRAY}In{DEFAULT}")
    execute = Execute(output=lambda value: print(f"{GRAY}{value}{DEFAULT}"))
    codes = []
    last_run = -1
    while True:
        try:
            line = input("   ")
            if m := re.match(r"\s*run\s+(.+)", line):
                run(m.group(1).strip(), execute)
                break
            if line.lower() == "on":
                for i, code in enumerate(codes[last_run + 1:], start=last_run + 1):
                    last_run = i
                    result = execute.run(code)
                    if result is not None:
                        print(f"{GRAY}{result}{DEFAULT}")
            elif line.lower() == "clean":
                last_run = -1
                codes = []
                execute.clean()
            elif line.lower() == "off":
                break
            else:
                codes.append(line)
        except EOFError:
            break
        except KeyboardInterrupt:
            print()
            break
        except DefException as error:
            for message in error.args:
                print(f"{RED}{message}{DEFAULT}")
    print(f"{GRAY}Out{DEFAULT}")


def main(arguments=None):
    arguments = sys.argv[1:] if arguments is None else arguments
    try:
        if not arguments:
            return console()
        command, rest = arguments[0], arguments[1:]
        if command == "run":
            return run_command(rest)
        if command == "compile":
            return compile_command(rest)
        if command == "check":
            return check(rest)
        if command == "install":
            program = Path.cwd()
            if "--into" in rest:
                at = rest.index("--into")
                program = Path(rest[at + 1]).resolve()
                rest = rest[:at] + rest[at + 2:]
            link, globally = "--link" in rest, "--global" in rest
            rest = [r for r in rest if r not in ("--link", "--global")]
            if not rest:
                if not libraries.listed(program):
                    raise DefException(f"{program} has no libraries.toml yet: install a library first ({libraries.HOW_TO_INSTALL})")
                libraries.install_all(program)
                return None
            for source in rest:
                # a folder is relative to where you are, like any command
                if "://" not in source and Path(source).exists():
                    source = str(Path(source).resolve())
                libraries.install(program, source, link=link, globally=globally)
            return None
        if command == "setup" and rest[:1] == ["--global-folder"] and len(rest) == 2:
            print(f"global libraries are kept in {libraries.set_global_folder(rest[1])}")
            return None
        print(__doc__.strip())
        return 2
    except DefException as error:
        print(f"{RED}{' '.join(map(str, error.args))}{DEFAULT}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main() or 0)
