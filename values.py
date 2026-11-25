"""Helpers for def-lang values. They are also available inside def bodies."""
import re
from collections.abc import MutableMapping
from typing import Optional

from deflang.exception import DefException

_NUMBER = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?")


class Code(str):
    """Text a language made (HTML, JavaScript): your own code, so a language puts it
    into another def as it is, never escaped."""


class Line(str):
    """A line kept to run later, where it was written (a definition whose arguments are
    kept, like the flag `later`'s): its text, and `line.file`, the file it is in."""

    def __new__(cls, text: str, file=None):
        line = super().__new__(cls, text)
        line.file = file
        return line


def parse_number(text: str):
    """Return the number written in `text`, or None if it isn't a number literal."""
    text = text.strip()
    if not _NUMBER.fullmatch(text):
        return None
    try:
        return int(text)
    except ValueError:
        return tidy(float(text))


def tidy(value: float):
    """5.0 -> 5, 2.5 -> 2.5"""
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def number(value):
    """Convert a value to a number, or raise a DefException explaining why not."""
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return tidy(value)
    if isinstance(value, str):
        parsed = parse_number(value)
        if parsed is not None:
            return parsed
    raise DefException(f"expected a number, got {describe(value)}")


def describe(value) -> str:
    return "nothing" if value is None else repr(value)


def as_text(value) -> str:
    """How a value looks when printed or joined into text."""
    if value is None:
        return ""
    if isinstance(value, float):
        return str(tidy(value))
    return str(value)


def as_code(value) -> str:
    """Turn a value back into def-lang source code that evaluates to it."""
    if isinstance(value, str):
        return f'"{value}"' if '"' not in value else repr(value)
    if isinstance(value, float):
        return str(tidy(value))
    return repr(value)


class Variables(MutableMapping):
    """The variables some lines see: a def call's own (if they run in one), then their
    file's, with the shared names the file uses. Setting a shared name the file uses
    changes the shared one; any other name is the def call's own, or else the file's.

    `place` is the file's place in the kernel (kernel["files"][FILE]): its "variables",
    and its "names", the shared variables it uses: {NAME: (FILE, NAME)}. `shared` is
    kernel["shared"], their values: {(FILE, NAME): value}."""

    def __init__(self, file, place: dict, shared: dict, own: Optional[dict] = None):
        self.file = file
        self.mine = place["variables"]
        self.names = place["names"]
        self.shared = shared
        self.own = own

    def _key(self, name):
        """The shared variable `name` means in this file, or None."""
        if self.own and name in self.own:
            return None
        return self.names.get(name)

    def __getitem__(self, name):
        if self.own is not None and name in self.own:
            return self.own[name]
        if (key := self._key(name)) is not None:
            return self.shared[key]
        return self.mine[name]

    def __setitem__(self, name, value):
        if (key := self._key(name)) is not None:
            self.shared[key] = value
        elif self.own is not None:
            self.own[name] = value
        else:
            self.mine[name] = value

    def __delitem__(self, name):
        if self.own is not None and name in self.own:
            del self.own[name]
        elif (key := self._key(name)) is not None:
            del self.shared[key]
        else:
            del self.mine[name]

    def _all(self) -> dict:
        used = {n: self.shared[k] for n, k in self.names.items() if k in self.shared}
        return {**self.mine, **used, **(self.own or {})}

    def __iter__(self):
        return iter(self._all())

    def __len__(self):
        return len(self._all())
