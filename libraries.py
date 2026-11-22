"""Libraries: folders of .def files with a library.toml, used by a program.

A program lists its libraries in libraries.toml, one table each:

    web    = { from = "https://example.com/libs.git#web" }                    in the project
    core   = { from = "https://example.com/libs.git#core", global = "0.1.0" } global
    shapes = { from = "my-libraries/shapes", link = true }                    local

- in the project: a copy in libraries/NAME (git keeps it out: libraries/.gitignore)
- global: a copy in GLOBAL/NAME/VERSION, shared by every program
- local: a folder of the project, used where it is

A library may have a libraries.toml too, of the same shape, with `from` only: a
relative `from` is a folder of the same source (`../language/javascript`), and it is
installed the way the library itself is. `use web/server` is web's server.def, and
`use core` is core's main.def.
"""
import os
import posixpath
import shutil
import subprocess
import tempfile
import tomllib
from pathlib import Path
from typing import Optional

from deflang.exception import DefException

HOW_TO_INSTALL = "install it with: python -m deflang install <git URL#folder> (or a folder of the project, with --link)"
SETTINGS = Path.home() / ".def-lang" / "settings.toml"
DEFAULT_GLOBAL = Path.home() / ".def-lang" / "libraries"


# ------------------------------------------------------------ settings

def global_folder() -> Path:
    """Where global libraries are: $DEFLANG_GLOBAL, else `def-lang setup`'s choice, else ~/.def-lang/libraries."""
    if os.environ.get("DEFLANG_GLOBAL"):
        return Path(os.environ["DEFLANG_GLOBAL"]).expanduser()
    if SETTINGS.is_file():
        try:
            chosen = tomllib.loads(SETTINGS.read_text()).get("global_folder")
        except tomllib.TOMLDecodeError as error:
            raise DefException(f"{SETTINGS}: {error}")
        if chosen:
            return Path(chosen).expanduser()
    return DEFAULT_GLOBAL


def set_global_folder(folder: str):
    """`def-lang setup --global-folder PATH`."""
    path = Path(folder).expanduser().resolve()
    SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS.write_text(f'global_folder = "{path.as_posix()}"\n')
    return path


# ------------------------------------------------------------ libraries.toml

def listed(owner: Path) -> dict:
    """The libraries.toml of a program or a library: {name: {"from": ..., "link": ..., "global": ...}}."""
    file = owner / "libraries.toml"
    if not file.is_file():
        return {}
    try:
        found = tomllib.loads(file.read_text())
    except tomllib.TOMLDecodeError as error:
        raise DefException(f"{file}: {error}")
    for name, entry in found.items():
        if not isinstance(entry, dict) or "from" not in entry:
            raise DefException(f'{file}: write {name} as {name} = {{ from = "..." }}')
    return found


def check_entry(program: Path, name: str, entry: dict):
    """The rules of a program's entry: global only from git, link only to a folder of the project."""
    source = entry["from"]
    if _is_git(source):
        if entry.get("link"):
            raise DefException(f"{name}: a library from git can't be linked: it is copied (or global)")
        return
    if entry.get("global"):
        raise DefException(f"{name}: only a library from git can be global")
    if not entry.get("link"):
        raise DefException(f"{name}: a folder is used where it is: write link = true")
    if not _inside(program, (program / source).resolve()):
        raise DefException(f"{name}: {source} is outside the project: a local library is a folder of the project")


def folder_of(owner: Path, name: str) -> Optional[Path]:
    """Where the library `name` of a program or a library is: its copy in libraries/,
    a linked folder, a global copy, or (in a library's libraries.toml) a folder of the
    same source."""
    copy = owner / "libraries" / name
    if (copy / "library.toml").is_file():
        return copy
    entry = listed(owner).get(name)
    if not entry:
        return None
    if entry.get("global"):
        found = global_folder() / name / str(entry["global"])
    elif _is_git(entry["from"]):
        return None  # not installed yet
    else:
        found = (owner / entry["from"]).resolve()
    return found if (found / "library.toml").is_file() else None


def read(folder: Path) -> dict:
    """A library's library.toml."""
    file = folder / "library.toml"
    if not file.is_file():
        raise DefException(f"{folder} is not a library: it has no library.toml")
    try:
        found = tomllib.loads(file.read_text())
    except tomllib.TOMLDecodeError as error:
        raise DefException(f"{file}: {error}")
    if "name" not in found:
        raise DefException(f"{file} needs a name")
    return found


def write_list(program: Path, entries: dict):
    lines = ["# The libraries of this program, and where they come from. Written by",
             "# `python -m deflang install`; run it with no arguments to install them all again.", ""]
    for name, entry in sorted(entries.items()):
        source = entry["from"].replace("\\", "/").replace('"', '\\"')
        extra = ", link = true" if entry.get("link") else f', global = "{entry["global"]}"' if entry.get("global") else ""
        lines.append(f'{name} = {{ from = "{source}"{extra} }}')
    (program / "libraries.toml").write_text("\n".join(lines) + "\n")


# ------------------------------------------------------------ installing

def install(program: Path, source: str, link: bool = False, globally: bool = False, say=print, already=()) -> list:
    """Install the library at `source` into the program, with the libraries its own
    libraries.toml lists (installed the same way), except those `already` done.
    Returns their names."""
    entries = listed(program)
    done = []
    skip = set(already)
    if link and globally:
        raise DefException("a library is linked or global, not both")
    if link and _is_git(source):
        raise DefException("a library from git can't be linked: it is copied into the project, or global (--global)")
    with tempfile.TemporaryDirectory() as workspace:
        workspace = Path(workspace)

        def one(source: str):
            folder = _fetch(source, program, workspace)
            info = read(folder)
            name = info["name"]
            if name in done or name in skip:
                return
            if globally:
                if "version" not in info:
                    raise DefException(f"{name} has no version in its library.toml: a global library needs one")
                entry = {"from": source, "global": str(info["version"])}
            elif link:
                entry = {"from": _relative(folder, program), "link": True}
            else:
                entry = {"from": source}
            check_entry(program, name, entry)
            done.append(name)
            if globally:
                target = global_folder() / name / entry["global"]
                if not target.exists():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copytree(folder, target, ignore=shutil.ignore_patterns(".git", "__pycache__"))
                where = " (global)"
            elif link:
                where = " (linked)"
            else:
                _keep_out_of_git(program)
                target = program / "libraries" / name
                if target.exists():
                    shutil.rmtree(target)
                shutil.copytree(folder, target, ignore=shutil.ignore_patterns(".git", "__pycache__"))
                where = ""
            entries[name] = entry
            say(f"installed {name} {info.get('version', '')}".rstrip() + where)
            for need, need_entry in listed(folder).items():
                one(_source_of(need_entry["from"], source, folder, program))

        one(source)
    write_list(program, entries)
    return done


def install_all(program: Path, say=print) -> list:
    """Install every library in the program's libraries.toml again."""
    done = []
    for name, entry in listed(program).items():
        check_entry(program, name, entry)
        if name not in done:
            done += install(program, entry["from"], link=bool(entry.get("link")), globally=bool(entry.get("global")),
                            say=say, already=done)
    return done


def _fetch(source: str, program: Path, workspace: Path) -> Path:
    """The folder of a source: a folder (relative to the program), or `URL#subfolder` of a git repo."""
    if _is_git(source):
        url, _, inside = source.partition("#")
        clone = workspace / url.replace("/", "_").replace(":", "_")
        if not clone.exists():
            try:
                subprocess.run(["git", "clone", "--depth", "1", "--quiet", url, str(clone)], check=True, capture_output=True, text=True)
            except FileNotFoundError:
                raise DefException("installing from git needs git")
            except subprocess.CalledProcessError as error:
                raise DefException(f"cannot get {url}: {error.stderr.strip()}")
        folder = clone / inside if inside else clone
        if not folder.is_dir():
            raise DefException(f"no folder {inside} in {url}")
        return folder
    folder = (program / source).resolve()
    if not folder.is_dir():
        raise DefException(f"no folder {source}")
    return folder


def _source_of(need: str, source: str, folder: Path, program: Path) -> str:
    """Where a library a library uses comes from: a git URL as it is; a relative folder
    from the same source as the library that uses it."""
    if _is_git(need):
        return need
    if _is_git(source):
        url, _, inside = source.partition("#")
        return url + "#" + posixpath.normpath(posixpath.join(inside or ".", need))
    return _relative((folder / need).resolve(), program)


def _keep_out_of_git(program: Path):
    """libraries/ only holds copies that `install` makes again: git leaves them out."""
    folder = program / "libraries"
    folder.mkdir(exist_ok=True)
    ignore = folder / ".gitignore"
    if not ignore.exists():
        ignore.write_text("# copies made by `def-lang install`: run it to make them again\n*\n")


def _is_git(source: str) -> bool:
    return "://" in source or source.split("#")[0].endswith(".git")


def _inside(program: Path, folder: Path) -> bool:
    return folder == program.resolve() or folder.is_relative_to(program.resolve())


def _relative(folder: Path, program: Path) -> str:
    return os.path.relpath(folder, program).replace(os.sep, "/")
