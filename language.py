"""The compiled language: a versioned snapshot of what defines the words.

Everything that can change how a line is read goes through `Language`: the
definitions, the aliases and the order they were made in. The snapshot is
rebuilt when its version changes, and all parse caches live on it, so an edit
cannot leave a stale cache behind (see KERNEL.md).

`ObservedList` and `ObservedDict` are the two containers the kernel exposes
for definitions and aliases; their mutations bump the version.
"""
import re
from collections import OrderedDict
from typing import Callable, Iterable, List, Optional

CACHE_LIMIT = 4096

# Fixed words of a readable pattern are plain regex groups: `(is)`, `(upper\-case)`.
# Groups like `(?P<a0>...)`, `(?:...)` and lookarounds are arguments or syntax, not words.
_PLAIN_GROUP = re.compile(r"\((?!\?)([^()]*)\)")


def _literal_words(pattern: re.Pattern) -> frozenset:
    """Words a pattern cannot match without, for its prebuilt index."""
    words = set()
    for raw in _PLAIN_GROUP.findall(pattern.pattern):
        word = re.sub(r"\\(.)", r"\1", raw)
        if word and all(char.isalnum() or char in "_-" for char in word):
            words.add(word)
    return frozenset(words)


class ObservedList(list):
    """A list that tells `Language` when its contents change."""

    def __init__(self, iterable: Iterable = (), *, on_change: Optional[Callable] = None):
        super().__init__(iterable)
        self._on_change = on_change or (lambda: None)

    def append(self, item):
        super().append(item)
        self._on_change()

    def extend(self, items):
        super().extend(items)
        self._on_change()

    def insert(self, index, item):
        super().insert(index, item)
        self._on_change()

    def __setitem__(self, index, value):
        super().__setitem__(index, value)
        self._on_change()

    def __delitem__(self, index):
        super().__delitem__(index)
        self._on_change()

    def __iadd__(self, items):
        self.extend(items)
        return self

    def __imul__(self, count):
        super().__imul__(count)
        self._on_change()
        return self

    def pop(self, index=-1):
        item = super().pop(index)
        self._on_change()
        return item

    def remove(self, item):
        super().remove(item)
        self._on_change()

    def clear(self):
        super().clear()
        self._on_change()

    def sort(self, *, key=None, reverse=False):
        super().sort(key=key, reverse=reverse)
        self._on_change()

    def reverse(self):
        super().reverse()
        self._on_change()


class ObservedDict(dict):
    """A dict that tells `Language` when its contents change."""

    def __init__(self, *args, on_change: Optional[Callable] = None, **kwargs):
        super().__init__(*args, **kwargs)
        self._on_change = on_change or (lambda: None)

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        self._on_change()

    def __delitem__(self, key):
        super().__delitem__(key)
        self._on_change()

    def __ior__(self, other):
        self.update(other)
        return self

    def clear(self):
        super().clear()
        self._on_change()

    def pop(self, key, *default):
        item = super().pop(key, *default)
        self._on_change()
        return item

    def popitem(self):
        item = super().popitem()
        self._on_change()
        return item

    def setdefault(self, key, default=None):
        if key not in self:
            self._on_change()
        return super().setdefault(key, default)

    def update(self, *args, **kwargs):
        super().update(*args, **kwargs)
        self._on_change()


class Language:
    """One version of the language, with its derived data and parse cache."""

    def __init__(self):
        self.version = 0
        self._snapshot_at = -1
        self._definitions: tuple = ()
        self._aliases: tuple = ()
        self._cache: "OrderedDict[tuple, object]" = OrderedDict()
        # per compiled pattern: the words it needs, its definition and its place in it
        self._required: tuple = ()
        self._owner: tuple = ()
        self._pattern: tuple = ()
        self._word_index: dict = {}
        self._unindexed: tuple = ()  # patterns with no safe fixed words: always candidates

    def changed(self):
        """A definition or an alias changed: make a new snapshot on next parse."""
        self.version += 1
        self._cache.clear()

    @property
    def definitions(self) -> tuple:
        return self._definitions

    def refresh(self, definitions: List, aliases: dict):
        """Rebuild the immutable parts when the version changed; return the defs."""
        if self._snapshot_at != self.version:
            self._definitions = tuple(definitions)
            compiled = []
            for phrase, words in aliases.items():
                phrase = " ".join(str(phrase).split())
                pattern = re.compile(r"(?<!\S)" + r"\s+".join(map(re.escape, phrase.split())) + r"(?!\S)")
                compiled.append((len(phrase), pattern, str(words).strip()))
            compiled.sort(key=lambda item: -item[0])
            self._aliases = tuple(compiled)
            self._index_patterns()
            self._snapshot_at = self.version
        return self._definitions

    def _index_patterns(self):
        """An inverted index of fixed words, so a line only tries the patterns that
        could match it. The regexes still decide: the index only removes work."""
        required, owners, places, index, unindexed = [], [], [], {}, []
        for definition_index, definition in enumerate(self._definitions):
            for pattern_index, pattern in enumerate(definition.patterns):
                id = len(required)
                owners.append(definition_index)
                places.append(pattern_index)
                # a raw regex may hide its fixed words in syntax we can't read safely
                words = frozenset() if "regex" in definition.flags else _literal_words(pattern)
                required.append(words)
                if words:
                    for word in words:
                        index.setdefault(word, []).append(id)
                else:
                    unindexed.append(id)
        self._required = tuple(required)
        self._owner = tuple(owners)
        self._pattern = tuple(places)
        self._word_index = index
        self._unindexed = tuple(unindexed)

    def candidate_patterns(self, text: str) -> dict:
        """{definition index: its pattern indexes that could match `text`}.

        A fixed word is looked for as a substring, not a whole token: symbols such
        as the `-` of `A0 - A1` sit inside `----`, and the regex must decide.
        Missing a pattern would change the language; an extra one only costs a
        fullmatch that fails.
        """
        ids = set(self._unindexed)
        for word, patterns in self._word_index.items():
            if word in text:
                ids.update(patterns)
        found = {}
        for id in sorted(ids):
            if all(word in text for word in self._required[id]):
                found.setdefault(self._owner[id], []).append(self._pattern[id])
        return found

    def apply_aliases(self, text: str, acting: bool) -> str:
        """`X means Y`, longer phrases first, as in Execute.apply_aliases()."""
        if acting:
            return text
        for _, pattern, words in self._aliases:
            text = pattern.sub(lambda _: words, text)
        return text

    def parse(self, parser, text: str, environment: tuple):
        """Parse `text` once for each (language version, runtime environment)."""
        self.refresh(parser.engine.definitions, parser.engine.kernel["aliases"])
        key = (text, environment)
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        node = parser._parse_uncached(text)
        self._cache[key] = node
        if len(self._cache) > CACHE_LIMIT:
            self._cache.popitem(last=False)
        return node
