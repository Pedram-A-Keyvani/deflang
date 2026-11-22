"""Libraries: folders of .def files with a library.toml, installed into a program.

    program/
      libraries.toml        which libraries, and where they come from
      libraries/web/        an installed copy (library.toml, server.def, script.def)

A linked library (`install --link`) isn't copied: libraries.toml says where it is.
`use web/server` is web's server.def, and `use core` is core's main.def.
"""
import shutil
import subprocess
import tempfile
import tomllib
from pathlib import Path
from typing import Optional

from deflang.exception import DefException

HOW_TO_INSTALL = "install it with: python -m deflang install <folder or git URL>"


def listed(program: Path) -> dict:
    """The libraries.toml of a program: {name: {"from": source, "link": bool}}."""
    file = program / "libraries.toml"
    if not file.is_file():
        return {}
    try:
        found = tomllib.loads(file.read_text())
    except tomllib.TOMLDecodeError as error:
        raise DefException(f"{file}: {error}")
    return {name: entry if isinstance(entry, dict) else {"from": entry} for name, entry in found.items()}


def folder_of(program: Path, name: str) -> Optional[Path]:
    """Where the library `name` of a program is: its installed copy, or the folder it links to."""
    copy = program / "libraries" / name
    if (copy / "library.toml").is_file():
        return copy
    entry = listed(program).get(name)
    if entry and entry.get("link"):
        linked = (program / entry["from"]).resolve()
        if (linked / "library.toml").is_file():
            return linked
    return None


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
    lines = ["# The libraries of this program, and where they come from. Written by", "# `python -m deflang install`; run it with no arguments to install them all again.", ""]
    for name, entry in sorted(entries.items()):
        source = entry["from"].replace("\\", "/").replace('"', '\\"')
        lines.append(f'{name} = {{ from = "{source}", link = true }}' if entry.get("link") else f'{name} = "{source}"')
    (program / "libraries.toml").write_text("\n".join(lines) + "\n")


def _fetch(source: str, program: Path, workspace: Path) -> Path:
    """The folder of a source: a folder (relative to the program), or `URL#subfolder` of a git repo."""
    if _is_git(source):
        url, _, inside = source.partition("#")
        clone = workspace / "clone"
        try:
            subprocess.run(["git", "clone", "--depth", "1", "--quiet", url, str(clone)], check=True, capture_output=True, text=True)
        except FileNotFoundError:
            raise DefException("installing from git needs git")
        except subprocess.CalledProcessError as error:
            raise DefException(f"cannot get {url}: {error.stderr.strip()}")
        return clone / inside if inside else clone
    folder = (program / source).resolve()
    if not folder.is_dir():
        raise DefException(f"no folder {source}")
    return folder


def install(program: Path, source: str, link: bool = False, say=print, already=()) -> list:
    """Install the library at `source` into the program, with the libraries it needs
    (from the same place: a sibling folder of the source), except those `already` done.
    Returns their names."""
    entries = listed(program)
    done = []
    skip = set(already)
    with tempfile.TemporaryDirectory() as workspace:
        workspace = Path(workspace)
        folder = _fetch(source, program, workspace)
        if link and _is_git(source):
            raise DefException("--link needs a folder, not a git URL")

        def one(folder: Path, source: str):
            info = read(folder)
            name = info["name"]
            if name in done or name in skip:
                return
            done.append(name)
            target = program / "libraries" / name
            if target.exists():
                shutil.rmtree(target)
            if link:
                entries[name] = {"from": _relative(folder, program), "link": True}
            else:
                shutil.copytree(folder, target, ignore=shutil.ignore_patterns(".git", "__pycache__"))
                entries[name] = {"from": source if _is_git(source) else _relative(folder, program)}
            say(f"installed {name} {info.get('version', '')}".rstrip() + (" (linked)" if link else ""))
            for need in info.get("needs", []):
                sibling = folder.parent / need
                if not (sibling / "library.toml").is_file():
                    raise DefException(f"{name} needs the library {need}, which isn't next to it: {HOW_TO_INSTALL}")
                one(sibling, _sibling_source(source, need, folder, program))

        one(folder, source)
    write_list(program, entries)
    return done


def install_all(program: Path, say=print) -> list:
    """Install every library in the program's libraries.toml again."""
    done = []
    for name, entry in listed(program).items():
        if name not in done:
            done += install(program, entry["from"], link=bool(entry.get("link")), say=say, already=done)
    return done


def _is_git(source: str) -> bool:
    return "://" in source or source.split("#")[0].endswith(".git")


def _relative(folder: Path, program: Path) -> str:
    """A folder near the program as a relative path (`../../libraries/core`), one far away as it is."""
    import os
    relative = os.path.relpath(folder, program)
    return relative if relative.split(os.sep).count("..") <= 3 else str(folder)


def _sibling_source(source: str, need: str, folder: Path, program: Path) -> str:
    """Where a needed library comes from: next to the one that needs it."""
    if _is_git(source):
        url, _, inside = source.partition("#")
        parent = inside.rsplit("/", 1)[0] if "/" in inside else ""
        return url + "#" + (parent + "/" if parent else "") + need
    return _relative(folder.parent / need, program)
