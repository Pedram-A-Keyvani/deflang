"""The def-lang command:

    python -m deflang                          the console (type lines, then `on` to run them)
    python -m deflang run FILE.def | FOLDER    run a program (a folder runs its main.def)
    python -m deflang check FILE.def | FOLDER  list its errors without running it
                                               (--json for editors; --text FILE: FILE's
                                               text is read from stdin, saved or not)
    python -m deflang install SOURCE [--link]  install a library from a folder or a git URL
                                               (`URL#subfolder`), with the libraries it needs
    python -m deflang install                  install the program's libraries.toml again

`install` works on the program in the current folder; `--into FOLDER` picks another.
"""
import re
import sys
from pathlib import Path

from deflang import libraries
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


def run(name: str, execute: Execute):
    file = program_file(name)
    if not file.is_file():
        raise DefException(f"no program {file}")
    execute.program_dir = file.resolve().parent
    for line in file.read_text().splitlines():
        result = execute.run(line)
        if result is not None:
            print(f"{GRAY}{result}{DEFAULT}")


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
        if command == "run" and len(rest) == 1:
            return run(rest[0], Execute(output=lambda value: print(f"{GRAY}{value}{DEFAULT}")))
        if command == "check":
            return check(rest)
        if command == "install":
            program = Path.cwd()
            if "--into" in rest:
                at = rest.index("--into")
                program = Path(rest[at + 1]).resolve()
                rest = rest[:at] + rest[at + 2:]
            link = "--link" in rest
            rest = [r for r in rest if r != "--link"]
            if not rest:
                if not libraries.listed(program):
                    raise DefException(f"{program} has no libraries.toml yet: install a library first ({libraries.HOW_TO_INSTALL})")
                libraries.install_all(program)
                return None
            for source in rest:
                # a folder is relative to where you are, like any command
                if "://" not in source and Path(source).exists():
                    source = str(Path(source).resolve())
                libraries.install(program, source, link=link)
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
