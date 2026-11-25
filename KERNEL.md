# The kernel: a design

The design, reviewed and built (section 6, steps 1 to 4).

**The goal.** The interpreter keeps one tree, the **kernel**, with an entry for every
language, flag, modifier and statement. Libraries add entries, so the interpreter's own
words shrink to a small, fixed part. It replaces fixed methods like `self.share`.

## 1. The lines

| Line | Shape | Example |
|---|---|---|
| definition | `[modifiers] language[flags] pattern`, then its indented body | `internal def[written] repeat A0 times : A1` |
| entry | `KIND NAME`, then its indented fields (section 2) | `language html`, `modifier internal` |
| modifier on a line | `modifier rest` | `shared visits is 0` |
| statement | a whole line the reader knows | `use core`, `comment is #`, `indent 2` |
| expression | anything else | `say 2 + 3` |

A line's kind is decided from its start, in this order:

1. empty, or starting with the comment marker: nothing;
2. indented: a body, or a line belonging to the one above (unchanged);
3. a statement (`use`, `comment is`, `argument is`, `indent`, `error`, `` `…` ``);
4. an entry: `language`, `flag`, `modifier` or `statement`, then a name;
5. a modifier: it is taken off, applied, and the rest of the line is read by these rules;
6. a language word, directly followed by a space or `[`: a definition;
7. anything else: an expression.

**A language word starts a definition.** At the start of a line, `def`, `python`,
`html`, … always begin one. An expression can still use these words anywhere else. So
do the four kind words: at the start of a line, `language`, `flag`, `modifier` and
`statement` always declare an entry.

### A definition line

```
[modifiers]  language[flags]  pattern
internal     def[written]  repeat A0 times : A1
             python           say A0
             html             card A0
             def[regex]       (A0: \d+)% or (A0: \d+) percent
```

- **In front:** where it is visible (modifiers). **Right after the language:** how it
  works (flags). **Then, after at least one space:** the pattern, with no exceptions. A
  pattern can start with any word, or with `[`: `def python temperature A0` is a
  def-lang def whose pattern is `python temperature A0`, and `def [ A0 ] first` one
  whose pattern is `[ A0 ] first` (`[A0]` without spaces would be one fixed word).

### Flags

1. Flags are a `[` right after the language word, with no space: `def[…]`.
2. The pattern is separated from what is before it by at least one space; so a `[`
   after a space is the pattern's: `def [1, 2] doubled`.
3. Several flags: separated by commas, in any order: `def[written, regex]`.
4. A flag may have words of its own, written out: `def[cache 60 seconds]`, as the flag's
   `words` say. Never a variable: a flag must be known without running the program (the
   editor, `check`, reloading).
5. No flags: no brackets. `def[]` is an error.
6. An unknown flag is an error that names the flags there are. Every language takes every
   flag.

## 2. The tree

A Python body gets the kernel as `self`, and reads and changes the tree as `self[...]`:

```
kernel = {
  "language":    { NAME: entry },    # languages: how a body runs
  "flag":        { NAME: entry },    # how one definition works
  "modifier":    { NAME: entry },    # where something is visible
  "statement":   { NAME: entry },    # whole lines the reader knows
  "definitions": [definition, ...],  # in the order they were made: it decides reading
  "aliases":     { phrase: words },  # X means Y
  "files":       { PATH: {"comment": "//", "argument": "A", "indent": 4,
                          "variables": {name: value},
                          "names": {NAME: (FILE, NAME)}} },  # the shared ones it uses
  "shared":      { (FILE, NAME): value },
  "variables":   the running code's: its def call's own, its file's, its shared names
  "file":        the file running now
  "program":     the program's folder
  "answer":      the last question's answer
  "store":       { LIBRARY: {...} },  # a library's own state, made on first use
}
```

What the interpreter does stays a method: `self.run(text)`, `self.say(value)`, and for
a web server `self.own_variables(file)`, `self.changed_files()`, `self.reload(path)`.
Only `self["answer"]` is set; every other part is changed in place.

**An entry** is declared in a `.def` file, the same way in every kind: the kind and a
one-word name, then its fields one level in. Its help is the comment lines right above
it, like a def's description. A statement's words are a field (`words`), so its first
line can't be read as a sentence:

```
// Valid only in its own file.
modifier internal
    does in def
        set seen by to the file

// HTML: the body is the def's value, with A0, A1, ... filled in as escaped text.
// Example: greeting "<b>Sam</b>", with html greeting A0 whose body is <p>Hello A0</p>
//          → "<p>Hello &lt;b&gt;Sam&lt;/b&gt;</p>"
language html
    editor html
    does in python
        ...

// Lines starting with A0 are comments, from here to the end of the file.
statement comment
    words comment is A0
    does in def
        set comment marker to A0
```

- **The first line** is the kind and a one-word name: `language html`, `modifier
  internal`, `statement comment`. The name is the entry's key in the tree
  (`kernel["statement"]["comment"]`) and the title of its hover.

- **The fields:**

  | Field | Of | Is |
  |---|---|---|
  | `does in LANGUAGE[FLAGS]` | every kind | what the entry does, in that language (`def`, `python`, …), one level in; flags as on a definition line (`does in def[written]`) |
  | `words` | a statement | the words it matches, written like a pattern: `comment is A0` |
  | `editor` | a language | VS Code's language id, for coloring and formatting its bodies |
  | `words` | a flag | how it is written in the brackets, like a pattern: `cache A0 seconds`; without it, its name |
  | `replaces` | every kind | the file that declared the entry it replaces, as `use` names it: `replaces language/css` |

- **`does in LANGUAGE`** is what the entry does, in any language: `does in def`,
  `does in python`. The interpreter knows what an entry is from where it stands, and
  when it acts: a language when its definition runs, a flag when its definition is
  made (before its pattern is read), a modifier right after its definition is made or
  before the rest of its name's line runs, a statement when its line is read. Its
  `does` runs then, where it acts, and finds what it acts on in `self["entry"]`: the
  definition, the name, the value, the body, … (the guide's 5.1).
- **No flag or modifier is known to the kernel by name.** A definition has three
  hooks, with the kernel's defaults: `read_pattern` (readable patterns), `read_argument`
  (read as an expression, for its value) and `seen_by` (every file). An entry changes
  them; the core library's `kernel.def` gives the words for it, so entries are written
  in def, mostly with one word, `set A0 to A1`: `set arguments to as written` (written), `set pattern to regex` (regex),
  `set seen by to the file` (internal), `set name to shared` (shared), `set comment
  marker to A0`, `set body to upper-case`, …. Python stays in the kernel and in core's
  words.
- **The help** (the comment lines above) is what the editor shows on hover.
- **Coloring:** the editor colors an entry's parts so they read apart: the kind word
  (`language`, `flag`, `modifier`, `statement`) like `def`; the name as a declared
  name; the field names (`words`, `does in`, …) as keywords; a statement's
  `words` as a pattern (fixed words and `A0`, `A1`, …); and `does`'s body in its language. It also
  takes its keyword colors from the entries, so a library's new modifier or statement is
  colored like `shared` or `use` wherever it is used.

## 3. Where every item goes

| Today | Kind | Written | Kernel path | Lives in |
|---|---|---|---|---|
| `def X` | language | `def X` | `kernel["language"]["def"]` | the language library (`language/def.def`) |
| `def python X` | language | `python X` | `kernel["language"]["python"]` | the kernel (built in) |
| `def html X`, `css`, `javascript` | language | `html X` | `kernel["language"]["html"]` | the language library (`language html`) |
| `language html` | entry | `language html` with its fields | `kernel["language"]["html"]` | the language library (`language/html.def`) |
| `def as written X` | flag | `def[written] X` | `kernel["flag"]["written"]` | the flag library (`flag/written.def`) |
| `def python as written X` | flag | `python[written] X` | `kernel["flag"]["written"]` | the flag library (`flag/written.def`) |
| `def regex X` | flag | `def[regex] X` | `kernel["flag"]["regex"]` | the flag library (`flag/regex.def`) |
| `shared NAME …` | modifier | `shared NAME …` | `kernel["modifier"]["shared"]` | the modifier library (`modifier/shared.def`), used by core |
| (new) | modifier | `internal def …` | `kernel["modifier"]["internal"]` | the modifier library (`modifier/internal.def`), used by core |
| `use` | statement | as now | `kernel["statement"]["use"]` | the kernel (built in) |
| `comment is`, `argument is`, `indent`, `error`, `` `…` `` | statement | as now | `kernel["statement"][…]` | the statement library (`statement/comment.def`, …) |
| a language's `BODY`, `VAR`, `fill` | what it acts on | `self["entry"]["template"]`, `["values"]`, `["fill"]`, `["body"]` | | |
| `self.share`, `self.variables`, `self.store`, … | the tree | `kernel[…]` | | |

**Built in:** only the language `python` (the Python at the bottom: the def language
and core's words) and the statement `use` (it loads the libraries). Everything else is an entry of a library, one file each:
`language/`, `flag/`, `statement/`, `modifier/`; core uses them all first. The guide
covers only the interpreter: its listings declare the entries they use.

## 4. Decided (the suggested answers; change any)

1. **Keys are strings**, not an enum: a library can add an entry without a change to
   the kernel.
2. **The kinds are fixed** (`language`, `flag`, `modifier`, `statement`); what is in each
   kind is open.
3. **Modifiers stack**, in any order, each applied in turn: `internal shared …`.
4. **Flags are general**: every language takes every flag.
5. **Who may change an entry:** any file may add one. Replacing an existing entry needs
   an explicit replace, never a silent one, and the editor shows where it was replaced:
   the field `replaces FILE`, naming the file that declared it. Built-in entries can't
   be replaced.

## 5. What it changes

| Where | How much |
|---|---|
| **deflang** | the reader (line kinds, entries, `language[flags]`), the kernel tree, the Python API, `check`, the guide (chapters 2, 4, 5, 6 and the appendix) |
| **deflang-lib** | 48 `def python` → `python`; 21 `def python as written` → `python[written]`; 4 `def as written` → `def[written]`; 6 `def html`, 6 `def css`, 2 `def javascript` → `html`, `css`, `javascript`; the 3 `language` lines get their fields; one library per kind, one file per entry: `language/` (`html.def`, `css.def`, `javascript.def`) and `modifier/` (`shared.def`, `internal.def`, used by core) |
| **deflang-sample** | the same rewriting in the samples, and the tests |
| **deflang-editor** | reading the new line shapes, `[flags]` and entries; keyword colors from the entries; hover help from their comment lines |

The rewriting of `.def` files is mechanical: a script can do it, and every test,
sample and guide listing must give the same results before and after.

## 6. Steps

1. **This design**, reviewed.
2. **The new line shapes**: `language[flags] pattern`, entries (`language`, `flag`,
   `modifier`, `statement`), `internal def`, with the kernel tree behind them, and
   `shared` and `internal` as entries.
3. **The Python API** on the tree, in place of `self.share`, `self.variables`, ….
4. **`def` and the statements in libraries:** `def` declared in the language library (`language def`), and statements moved
   into libraries (`use` last: it loads the libraries).

## 7. Decided in review

- **"variable"** stays the word (no "state").
- **A pattern** is always separated by at least one space, so `[` right after the
  language is its flags, and a `[` after a space belongs to the pattern.
- **`language`** stays the word (no `lang`); `flag`, `modifier` and `statement` declare
  the other kinds the same way.
- **An entry's first line** is its kind and a one-word name; a statement's words are
  its `words` field. Brackets mean flags only.
- **Coloring** sets an entry's parts apart (section 2).
- **`does in LANGUAGE`**, required: `does` is open to any language. What it acts on
  is in `self["entry"]`, decided by where the entry stands; there is no `applies to`.
- **Entries in def**: a `does in def` is commands with no subject (`allow only in the
  file`), acting on what the entry acts on. Core's `kernel.def` holds their Python.
- **The fields** per kind are in section 2: `words` (statements and flags), `editor`,
  `replaces`. A flag is written by its `words`; there is no `takes`. A language has no
  `flags` field: every language takes every flag. `does in LANGUAGE[FLAGS]` says how
  the entry's own body gets its arguments.
- **The Python API** (step 3): what the interpreter has is the tree, `self["…"]`;
  what it does are methods. `self.share`, `self.alias`, `self.lookup`,
  `self.file_path` and `self.store(name)` are gone.
- **The flag `as written` is named `written`**, one word like every entry's name:
  `def[written] repeat A0 times : A1`. Its hover says what it means: the def gets its
  arguments as they are written, not their values.
