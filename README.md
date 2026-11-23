# The def-lang Guide

def-lang is a declarative, natural-language-like programming language. This guide
covers the language and its interpreter.

**Related repositories**

| Repository | Holds |
|---|---|
| [deflang-lib](https://github.com/Pedram-A-Keyvani/deflang-lib) | the libraries: `core` (values, questions, loops, lists, text, math), `html`, `css`, `javascript`, `web`; each with a README of its words |
| [deflang-sample](https://github.com/Pedram-A-Keyvani/deflang-sample) | sample programs (hello world to a website), and the tests of the interpreter and the libraries |
| [deflang-editor](https://github.com/Pedram-A-Keyvani/deflang-editor) | the VS Code extension: colors, hover, Ctrl+click, IntelliSense, errors as you type; it carries the interpreter |

**Contents**

1. [Getting Started](#1-getting-started)
2. [Lines and Statements](#2-lines-and-statements)
3. [Values](#3-values)
4. [Defs](#4-defs)
5. [Flags, Languages and Modifiers](#5-flags-languages-and-modifiers)
6. [Variables](#6-variables)
7. [How a Line Is Read](#7-how-a-line-is-read)
8. [Programs and Libraries](#8-programs-and-libraries)
9. [Errors and Checking](#9-errors-and-checking)
10. [Appendix](#10-appendix)

---

## 1. Getting Started

### 1.1 Installation

Needs Python 3.11 or newer; nothing else, and nothing to install.

Get the interpreter:

```console
git clone https://github.com/Pedram-A-Keyvani/deflang.git FOLDER/deflang
```

- `FOLDER` is any folder you choose, like `~/code`; it holds `deflang`.
- The folder keeps the name `deflang`.
- After `git pull`, the new interpreter runs at once: nothing to install again.

Let `def-lang` run it:

```console
alias def-lang='PYTHONPATH=FOLDER python3 -m deflang'
```

- `PYTHONPATH` is the same `FOLDER`: the one that holds `deflang`.
- Put this line in `~/.bashrc` to have `def-lang` in every terminal.

Where global libraries go (optional; [8.2](#82-libraries)):

```console
def-lang setup --global-folder GLOBAL
```

- `GLOBAL` is any folder you choose; without this step it is `~/.def-lang/libraries`.
- It is kept in `~/.def-lang/settings.toml`, for every later run.

### 1.2 Hello, World!

A program is a folder with a `main.def`. The interpreter knows no words like `say`:
a program makes its own with definitions.

<a id="listing-1-1"></a>
**Listing 1-1:** `hello/main.def`

```
python say A0
    self.say(A0)

say "Hello, world!"
```

Run it, from the folder that holds `hello`:

```console
def-lang run hello
```

It prints:

```console
Hello, world!
```

- `python say A0` makes the word `say`, with a body written in Python.
- `A0` is what stands after `say` on the line.

### 1.3 The Console

```console
def-lang
```

- Type lines, then `on` to run them.
- `clean` forgets the values; `off` quits.
- `run FOLDER` runs a program.

---

## 2. Lines and Statements

### 2.1 Kinds of Line

| Line | Is |
|---|---|
| empty | nothing |
| starts with the comment marker | a comment |
| a statement | run by the interpreter itself |
| an entry: `language`, `flag`, `modifier` or `statement`, then a name | declares one ([chapter 5](#5-flags-languages-and-modifiers)) |
| a definition: a language (`def`, `python`, …), then its pattern | makes one ([chapter 4](#4-defs)) |
| indented, right after a definition or an entry | its body, or its fields |
| indented, not a def body | runs only if the line it belongs to left `self["answer"]` `True` ([2.2](#22-indentation)) |
| anything else | an expression: read into a tree of defs, then run |

### 2.2 Indentation

`indent N` sets how many spaces make one **level**; each file starts with `indent 4`.
A tab is always one level. A width that isn't a whole number of levels is an error.

| An indented line… | Is |
|---|---|
| right after a definition line, or an entry | the body, or the entry's fields: it ends at the next line of level 0 |
| anywhere else | it belongs to the last line one level up, and runs only if that line ran and left `self["answer"]` `True` |

<a id="listing-2-1"></a>
**Listing 2-1**

```
python say A0
    self.say(A0)

python A0 > A1 ?
    self["answer"] = number(A0) > number(A1)

def greet A0
    say "hello"

    say A0

greet "sam"
5 > 3 ?
    say "yes"
1 > 3 ?
    say "no"
```

```console
hello
sam
yes
```

<a id="listing-2-2"></a>
**Listing 2-2**

```
python say A0
    self.say(A0)

python A0 > A1 ?
    self["answer"] = number(A0) > number(A1)

python otherwise ?
    self["answer"] = not self["answer"]

indent 2
5 > 3 ?
  say "a"
  5 > 10 ?
    say "b"
  say "c"
otherwise ?
  say "d"
```

```console
a
c
```

- A skipped line skips the lines below it.
- Before a line runs, `self["answer"]` is the answer of the last line on its own level:
  `otherwise ?` turns around `5 > 3 ?`, not `5 > 10 ?`.
- Each def call has its own levels; the answer it leaves still comes out.
- Empty lines and comment lines don't end a body. In a Python or other-language body,
  that language checks the indentation.
- Variables don't follow levels: they belong to the def call ([chapter 6](#6-variables)).

### 2.3 Statements

The statements the interpreter knows (a library can add more, [5.5](#55-statements-and-flags-of-your-own)):

| Statement | Does |
|---|---|
| `use NAME` | runs `NAME.def`, or a library, once ([chapter 8](#8-programs-and-libraries)) |
| `use NAMES from NAME` | the same, and this file gets `NAME`'s shared variables `NAMES` ([chapter 6](#6-variables)) |
| `use NAME as OTHER from FILE` | the same as `use NAME from FILE`, but this file calls it `OTHER` |
| `comment is X` | lines starting with `X` are comments |
| `argument is X` | arguments are written `X0`, `X1`, … |
| `indent N` | `N` spaces make one level ([2.2](#22-indentation)) |
| `error MESSAGE` | stops with `MESSAGE` |
| `` `LINE` `` | prints `LINE`, then runs it |

### 2.4 Comments

<a id="listing-2-3"></a>
**Listing 2-3**

```
python say A0
    self.say(A0)

comment is #
# a comment
say "done"
```

```console
done
```

- `//` is the marker until `comment is` sets another one.
- The marker lasts to the end of its file; each file starts with `//`.
- The comment lines right above a def are its description.

---

## 3. Values

| Value | Written |
|---|---|
| number | `5`, `-2`, `2.5` |
| text | `"hello"` |
| list | `[1, "a", [2]]` |
| nothing | a line or def with no value |

<a id="listing-3-1"></a>
**Listing 3-1**

```
python say A0
    self.say(A0)

python[written] A0 is A1
    self["variables"][A0] = self.run(A1)

python A0 + A1
    return number(A0) + number(A1)

x is 2 + 3
say x
```

```console
5
```

- Patterns never match inside text.
- A word that is no def, variable or value is an error: `unknown name`.
- Text next to values (`"x = " x`) is joined by a def, not by the language
  ([Listing 4-6](#listing-4-6)).

---

## 4. Defs

```
LANGUAGE[FLAGS] PATTERN
    BODY
```

- **The language** says what the body is written in: `def` is def-lang, `python` is
  Python, and others are declared ([5.3](#53-languages)).
- **The flags** come right after it, in brackets, and are optional
  ([chapter 5](#5-flags-languages-and-modifiers)).
- **The pattern** comes after a space; it can start with any word, or with `[`.

### 4.1 Patterns and Arguments

In `repeat A0 times : A1`:

- **fixed words:** `repeat`, `times`, `:`: they must appear as they are;
- **arguments:** `A0`, `A1`: whatever stands in their place.

Words need spaces between them; symbols don't (`2+3` matches `A0 + A1`).

**Naming:** a def that gives a value reads best as a thing (`A0 plus the rate`,
`total of A0 and A1`); a def that does something, as a command (`say A0`,
`count the visit`). Then a line reads as one sentence: `say 4 plus the rate`.
A def named as a thing only gives a value: it changes nothing, so it gives the same
answer every time.

<a id="listing-4-1"></a>
**Listing 4-1**

```
python say A0
    self.say(A0)

argument is X
python X0 times X1
    return number(X0) * number(X1)

say 2 times 3
```

```console
6
```

- `argument is X` writes the arguments `X0`, `X1`, … to the end of the file; each
  file starts with `A`.

### 4.2 def-lang Bodies

<a id="listing-4-2"></a>
**Listing 4-2**

```
python say A0
    self.say(A0)

python A0 + A1
    return number(A0) + number(A1)

def A0 doubled
    A0 + A0

say 4 doubled
```

```console
8
```

- The lines run with the arguments put in.
- The def's value is the value of the last line that has one.

### 4.3 Python Bodies

<a id="listing-4-3"></a>
**Listing 4-3**

```
python say A0
    self.say(A0)

python half of A0
    return number(A0) / 2

say half of 9
```

```console
4.5
```

- The body is a Python function; `return` gives the def's value.
- It gets `self` (the kernel, [Appendix D](#d-the-python-api)) and the arguments.

### 4.4 Several Patterns, One Body

<a id="listing-4-4"></a>
**Listing 4-4**

```
python say A0
    self.say(A0)

python A0 + A1
    return number(A0) + number(A1)

def A0 plus A1
def the sum of A0 and A1
    A0 + A1

say the sum of 2 and 3
```

```console
5
```

- Definition lines in a row share the body below them.
- Every line of the group has the same language and flags.

### 4.5 Restricted Arguments

<a id="listing-4-5"></a>
**Listing 4-5**

```
python say A0
    self.say(A0)

python A0 + A1
    return number(A0) + number(A1)

python[written] (A0: one|two|three)
    return ["one", "two", "three"].index(A0) + 1

say two + three
```

```console
5
```

- `(A0: REGEX)` matches only that regex.
- A def with no fixed words is a **word list**: it matches a whole value.

### 4.6 Text Arguments

`"A0"` in a pattern matches only a text.

<a id="listing-4-6"></a>
**Listing 4-6**

```
python say A0
    self.say(A0)

python[written] A0 is A1
    self["variables"][A0] = self.run(A1)

python A0 + A1
    return number(A0) + number(A1)

python A0 "A1" A2
python "A0" A1
python A0 "A1"
    return "".join(as_text(value) for value in a)

x is 2 + 3
say "x = " x
```

```console
x = 5
```

- The quotes of `"A0"` count as fixed words.
- This def joins text and values next to each other. Like any def, it binds by
  order ([chapter 7](#7-how-a-line-is-read)): made after `say` and `is` and before
  math, `say "x = " 2 + 3` says `x = 5`.

---

## 5. Flags, Languages and Modifiers

**Flags** are written in brackets right after the language, before the pattern:
`def[written] …`, several with commas: `python[written, regex] …`. They say how one
definition works. A flag is always written out, never a variable.

### 5.1 `written`

The def gets its arguments as they are written, not their values.

<a id="listing-5-1"></a>
**Listing 5-1**

```
python say A0
    self.say(A0)

python[written] twice : A0
    self.run(A0)
    self.run(A0)

twice : say "hi"
```

```console
hi
hi
```

Use it when the def needs the **words** of an argument:

- a name to store under (`A0 is A1` in [Listing 3-1](#listing-3-1));
- code to run later, many times, or maybe not at all ([Listing 5-1](#listing-5-1));
- a word itself ([Listing 4-5](#listing-4-5): without `written`, `two`'s value would be read
  with the same def again, and again).

### 5.2 `regex`

The pattern is a raw regex; ` or ` splits alternatives.

<a id="listing-5-2"></a>
**Listing 5-2**

```
python say A0
    self.say(A0)

python[regex] (A0: \d+)% or (A0: \d+) percent
    return number(A0) / 100

say 50 percent
```

```console
0.5
```

### 5.3 Languages

`language NAME` declares a language: an **entry**, with its fields one level in.
Definitions then start with `NAME`, and the Python under `does` runs their bodies.

<a id="listing-5-3"></a>
**Listing 5-3**

```
python say A0
    self.say(A0)

language upper
    does
        return fill(BODY, [as_text(value) for value in VAR]).upper()

upper greeting for A0
    hello A0, how are you?

say greeting for "sam"
```

```console
HELLO SAM, HOW ARE YOU?
```

- `does`'s Python gets `BODY` (the body text), `VAR` (the argument values) and
  `fill(BODY, values)` (puts values where `A0`, `A1`, … are).
- More fields: `editor` (VS Code's language id, for coloring and formatting its
  bodies) and `flags` (the flags it accepts, like `written, regex`; without it, none).
- `def` and `python` are built in; they accept every flag.
- What a language returns is `Code`: another language puts it in unescaped.
- An entry's help is the comment lines right above it, like a def's description.

### 5.4 Modifiers

A modifier is a word in front of a line that changes where something is seen. It is
an entry too, with `applies to`: `definition` or `name`.

<a id="listing-5-4"></a>
**Listing 5-4**

```
python say A0
    self.say(A0)

// Valid only in its own file.
modifier internal
    applies to definition
    does
        TARGET.internal = True

internal python A0 halved
    return number(A0) / 2

say 9 halved
```

```console
4.5
```

- `does` gets `TARGET`: the definition, or the name, it modifies.
- An `internal` def is seen only by its own file: its lines, and its other defs (also
  when another file calls them). Other files don't see it.
- A modifier that applies to a name, like `shared` ([6.3](#63-shared)), is followed by
  the rest of an ordinary line: `shared visits is 0`.
- Modifiers stack: `internal shared …` applies each in turn.

### 5.5 Statements and Flags of Your Own

<a id="listing-5-5"></a>
**Listing 5-5**

```
python say A0
    self.say(A0)

// Says hello.
statement greet
    words greet A0
    does
        self.say("hello " + a[0].strip())

greet Sam
```

```console
hello Sam
```

- A statement's `words` are written like a pattern; `does` gets them as `a[0]`,
  `a[1]`, …, as they are written.
- `flag NAME` declares a flag; `takes` says the kind of its value (`def[cache 60]`),
  and `does` gets `TARGET` (the definition) and `VALUE`.
- An entry is declared once. Another file replaces it only by saying so, with the
  field `replaces FILE`: the file that declared it, named the way `use` names it.
  From then on, the new entry is used, also by definitions made before it:

  ```
  language css
      replaces language/css
      editor css
      does
          ...
  ```

- A built-in entry (`def`, `python`, `written`, `regex`, the statements) can't be
  replaced.

---

## 6. Variables

From the smallest scope to the largest:

| Variable | Made by | Seen by |
|---|---|---|
| a def's own | setting it inside a def-lang def | that def call, until it ends |
| the file's | setting it outside any def | that file's lines and its defs |
| shared | `shared NAME` | the file that made it, and the files that say `use NAME from FILE` |

Variables don't follow indentation ([2.2](#22-indentation)). `shared` is a modifier
([5.4](#54-modifiers)): the core library declares it, and so does Listing 6-3.

### 6.1 A Def's Own

<a id="listing-6-1"></a>
**Listing 6-1**

```
python say A0
    self.say(A0)

python[written] A0 is A1
    self["variables"][A0] = self.run(A1)

python A0 + A1
    return number(A0) + number(A1)

def total of A0 and A1
    sum is A0 + A1
    sum

say total of 2 and 3
```

```console
5
```

- `sum` is the def call's own: it is gone when the call ends.
- Each call has its own: a def that calls itself doesn't share them.
- A `written` def has none: it runs the caller's words where they were written,
  with the caller's variables.

### 6.2 The File's

<a id="listing-6-2"></a>
**Listing 6-2**

```
python say A0
    self.say(A0)

python[written] A0 is A1
    self["variables"][A0] = self.run(A1)

python A0 + A1
    return number(A0) + number(A1)

rate is 2
def A0 plus the rate
    A0 + rate

say 4 plus the rate
```

```console
6
```

- A def sees the variables of the file it was made in, even when another file
  calls it.
- Other files don't see them.
- Setting a variable inside a def makes the def's own ([6.1](#61-a-defs-own)), and
  the file's stays as it was.

### 6.3 Shared

<a id="listing-6-3"></a>
**Listing 6-3:** `counter.def`

```
python[written] A0 is A1
    self["variables"][A0] = self.run(A1)

// One variable for the whole program.
modifier shared
    applies to name
    does
        here = self["file"]
        self["files"][here]["names"][TARGET] = (here, TARGET)

shared visits is 0
```

<a id="listing-6-4"></a>
**Listing 6-4:** `main.def`, next to `counter.def`

```
python say A0
    self.say(A0)

python[written] A0 is A1
    self["variables"][A0] = self.run(A1)

python A0 + A1
    return number(A0) + number(A1)

use visits from counter
visits is visits + 1
say visits
```

```console
1
```

- `shared visits` makes `visits` a shared variable of `counter.def`. The rest of the
  line runs as an ordinary line: `shared visits is 0` is `shared visits`, then
  `visits is 0` (with the `is` def).
- `use visits from counter` runs `counter.def` (once), and `visits` in this file is
  counter's: the same variable, not a copy. Its lines and defs change the shared one.
- Several names: `use visits, total from counter`.
- Only shared variables can be used: `use secret from counter` is an error.
- Without the `use` line, `visits` is this file's own: it has no value yet, so
  `visits + 1` is `unknown name 'visits'`.

<a id="listing-6-5"></a>
**Listing 6-5:** `main.def`, next to `counter.def`

```
python say A0
    self.say(A0)

python[written] A0 is A1
    self["variables"][A0] = self.run(A1)

python A0 + A1
    return number(A0) + number(A1)

use visits as total from counter

def count A0 visits
    visits is A0
    total is total + visits

def the total after A0 visits
    visits is A0
    total + visits

count 3 visits
say the total after 2 visits
say total
```

```console
5
3
```

- `as` gives counter's `visits` another name here, `total`, so the defs can use the
  name `visits` for their own.
- `count A0 visits` is a command: it changes `total`, which is counter's `visits`.
- `the total after A0 visits` is a thing: it gives `total + visits` and changes
  nothing, so `total` stays `3`.

---

## 7. How a Line Is Read

A line is read once into a tree, then run. When several defs match, the shape of the
line decides which one wraps the others.

<a id="listing-7-1"></a>
**Listing 7-1:** the defs the rules below use, made in this order

```
python say A0
    self.say(A0)

python A0 ?
    self["answer"] = bool(A0)

python[written] A0 is A1
    self["variables"][A0] = self.run(A1)

python[written] keep A0 is A1
    here, name = self["file"], A0.strip()
    self["files"][here]["names"][name] = (here, name)
    self["variables"][name] = self.run(A1)

python[written] A0 if A1 otherwise A2
    return self.run(A0) if self.run(A1) else self.run(A2)

python[written] repeat A0 times : A1
    for _ in range(number(self.run(A0))):
        self.run(A1)

python[written] all of A0 are A1
    return all(self.run(as_code(item) + " " + A1) for item in self.run(A0))

python A0 "A1" A2
python "A0" A1
python A0 "A1"
    return "".join(as_text(value) for value in a)

python A0 > A1
    return number(A0) > number(A1)

python A0 + A1
    return number(A0) + number(A1)

python count of A0
    return len(A0)
```

| # | Rule | Line | Read as |
|---|---|---|---|
| 1 | A match whose fixed words are all part of a longer match loses | `keep visits is 0` | `keep A0 is A1`, not `A0 is A1` |
| 2 | **Brackets:** a def whose fixed words surround another's wraps it | `"big" if 5 > 3 otherwise "small"` | `if … otherwise` wraps `>` |
| 3 | **Sentences:** a `written` def that starts the line with two or more fixed words wraps what follows them | `repeat 3 times: x is x + 1` | `repeat` wraps `is` |
| 4 | **Word lists:** a def with no fixed words that matches the whole text is one value | `two` ([Listing 4-5](#listing-4-5)) | the word list |
| 5 | **Order:** otherwise, the def made first wraps | `x is 2 + 3 > 4` | `x is ((2 + 3) > 4)` |
| 6 | **No value:** a reading with an argument that can't be a value (an unknown name) loses to the next one | `count of "abc"` | `count of A0`, not `count of` joined with `"abc"` |

- **Closing words (rule 3):** a closing word at the very end, like `?`, isn't part of
  the sentence; the order decides. `all of [1, 2] are > 0 ?` is read as `A0 ?`, because
  `A0 ?` was made first. A text at the very end is no closing word.
- **Phrases (rule 3):** a def that takes values isn't a sentence:
  `count of [1, 2] > 1` is `(count of [1, 2]) > 1`.
- **Order (rule 5):** in [Listing 7-1](#listing-7-1), `say`, `A0 ?` and `A0 is A1` are made before
  joined text, and joined text before `>` and `+`: so `say "x = " 2 + 3` says `x = 5`.

---

## 8. Programs and Libraries

### 8.1 Using Files

| Line | Runs |
|---|---|
| `use NAME` | `NAME.def`, or the library `NAME`'s `main.def` |
| `use NAME/FILE` | `NAME/FILE.def`, or the library `NAME`'s `FILE.def` |
| `use NAMES from NAME` | the same file, and gives this file its shared variables `NAMES` ([chapter 6](#6-variables)) |
| `use NAME as OTHER from FILE` | the same as `use NAME from FILE`, but this file calls it `OTHER` |

`use` looks for the file, in this order:

1. next to the file with the `use` line;
2. in the program's folder (the folder of the `main.def` that runs);
3. in the program's libraries ([8.2](#82-libraries));
4. for a file of a library: in the libraries its `libraries.toml` lists.

A file runs once; using it again does nothing. `as` is only for names: `use core as c`
is an error.

### 8.2 Libraries

A library is a folder of `.def` files with a `library.toml`:

| Key | Is |
|---|---|
| `name` | the library's name (required) |
| `version` | its version (required to install it globally) |

A program lists its libraries in its `libraries.toml`, one table each:

```toml
web    = { from = "https://example.com/libs.git#web", version = "0.1.0" }
core   = { from = "https://example.com/libs.git#core", version = "0.1.0", global = true }
shapes = { from = "my-libraries/shapes", link = true }
```

| Kind | Written | Lives in | In git |
|---|---|---|---|
| in the project | `from` a git `URL#FOLDER` | `libraries/NAME/`, a copy | no: `libraries/.gitignore` leaves it out |
| global | `from` a git `URL#FOLDER`, with `global = true` | `GLOBAL/NAME/VERSION/`, a copy shared by every program | no: it is outside the project |
| local | `from` a folder of the project, with `link = true` | that folder, used where it is | yes |

- `version` is written by `def-lang install`: the version in the library's `library.toml`.
  A local library has none: it is used as it is.
- Only a library from git can be global; only a folder of the project can be linked.
- `GLOBAL` is `~/.def-lang/libraries`; `def-lang setup --global-folder PATH` sets
  another, and `$DEFLANG_GLOBAL` sets one for a single run.
- A library may have a `libraries.toml` too, with `from` only. A relative `from` is a
  folder of the same source: in `web/libraries.toml`,
  `language = { from = "../language" }`. Those libraries are installed
  with it, the same way.

### 8.3 Installing

- `def-lang install URL#FOLDER`: copies the library in that folder of a git repo into
  `libraries/` (needs git).
- `def-lang install URL#FOLDER --global`: copies it into `GLOBAL/NAME/VERSION/`
  instead, if it isn't there yet.
- `def-lang install FOLDER --link`: a local library, a folder of the project; nothing
  is copied.
- `def-lang install`: installs everything in `libraries.toml` again; a version that changed
  is shown (`web: 0.1.0 → 0.2.0`) and written down.
- `def-lang setup --global-folder GLOBAL`: where global libraries go from now on.
- Each adds its line to `libraries.toml`, and installs the libraries the library's
  own `libraries.toml` lists.
- It works on the program in the current folder; `--into FOLDER` picks another.

---

## 9. Errors and Checking

An error stops the program with its message; in a used file it starts with
`FILE:LINE:`. All messages are listed in [Appendix E](#e-error-messages).

```console
def-lang check hello
```

`check` reads a program without running it:

- **runs:** the statements, the entries, the definitions and their modifiers, and
  the defs that change `self["aliases"]`;
- **only reads:** every other line, so nothing is asked, printed or started;
- **finds:** unknown names, files it can't find, a missing closing quote or `)`, an
  indented line with nothing to belong to, a Python syntax error in a body;
- **doesn't find:** errors that only happen while running, like `expected a number`.

Variable names come from the Python bodies: a `written` argument that a body
stores under (`self["variables"][A0]`) is a name.

- `--json` prints the result as JSON.
- `--text FILE` reads `FILE`'s text from stdin instead of the disk.

---

## 10. Appendix

### A. Statements

| Statement | Scope |
|---|---|
| `use NAME` | runs once per program |
| `use NAMES from NAME` | the names: to the end of the file |
| `use NAME as OTHER from FILE` | `OTHER`: to the end of the file |
| `comment is X` | to the end of the file; each file starts with `//` |
| `argument is X` | to the end of the file; each file starts with `A` |
| `indent N` | to the end of the file; each file starts with `4` |
| `error MESSAGE` | stops the program |
| `` `LINE` `` | that line |

### B. Flags

| Flag | Meaning |
|---|---|
| `written` | the def gets its arguments as they are written, not their values |
| `regex` | the pattern is a raw regex; ` or ` splits alternatives |

Written in brackets right after the language: `python[written, regex] …`.

### C. Entries

| Entry | Fields | Its `does` gets |
|---|---|---|
| `language NAME` | `does`, `editor`, `flags`, `replaces` | `BODY`, `VAR`, `fill` |
| `modifier NAME` | `does`, `applies to` (`definition` or `name`), `replaces` | `TARGET` |
| `flag NAME` | `does`, `takes`, `replaces` | `TARGET`, `VALUE` |
| `statement NAME` | `does`, `words`, `replaces` | `a`: its words |

Every `does` also gets `self`, the kernel ([Appendix D](#d-the-python-api)).

### D. The Python API

A Python body gets `self`, the kernel. What the interpreter has is its tree, read and
changed as `self[...]`; what it does are its methods.

| The tree | Is |
|---|---|
| `self["variables"]` | the variables of the running code: its def call's own, its file's, and the shared ones its file names: `self["variables"]["x"] = 5` |
| `self["answer"]` | whether the lines one level below run: they run if it is `True`; `None` makes them an error. The only part that is set: `self["answer"] = True` |
| `self["aliases"]` | `{phrase: words}`: `phrase` reads as `words`, longer phrases first |
| `self["store"][NAME]` | a library's own state: a dict, made on first use |
| `self["file"]` | the file running now |
| `self["program"]` | the program's folder: `self["program"] / "data.txt"` |
| `self["files"][FILE]` | a file's `"comment"`, `"argument"` and `"indent"` as read so far, its `"variables"`, and its `"names"`: the shared variables it uses, `{NAME: (FILE, NAME)}` |
| `self["shared"]` | the shared variables' values: `{(FILE, NAME): value}` |
| `self["definitions"]` | every definition, in the order made |
| `self["language"]`, `self["flag"]`, `self["modifier"]`, `self["statement"]` | the entries: `self["language"]["python"]` |

| Method | Does |
|---|---|
| `self.run(text)` | runs def-lang text and returns its value |
| `self.say(value)` | prints a value |
| `self.own_variables(file)` | in a `with` block, lines get variables of their own, on top of `file`'s (a web request) |
| `self.changed_files()`, `self.reload(path)` | the files saved since they were read; reads one again, in place of its old defs |

| Name | Is |
|---|---|
| the argument names | `A0`, `A1`, …: the argument's value, or its words if the def is `written` |
| `number(value)` | the value as a number, or an error |
| `parse_number(text)` | the text as a number, or `None` |
| `as_text(value)` | the value as text a person reads (what `self.say` prints) |
| `as_code(value)` | the value written as def-lang code, to put in text for `self.run` |
| `Code(text)` | marks text as code, so another language puts it in without escaping it |
| `DefException(message)` | raise it to stop with a def-lang error |

| Value | `as_text` | `as_code` |
|---|---|---|
| `5` | `5` | `5` |
| `"hi"` | `hi` | `"hi"` |
| `2.50` | `2.5` | `2.5` |
| nothing | (empty) | `None` |

### E. Error Messages

| Message | Cause |
|---|---|
| `unknown name 'x'` | no def, variable or value is `x` |
| `missing closing quote in: …` | a `"` with no closing `"` |
| `missing ')' in: …` | a restricted argument with no closing bracket |
| `invalid def pattern '…'` | a pattern that isn't a valid regex |
| `indented line with no line above it to belong to` | an indented line with no line one level up |
| `indented line, but the line above it gave no answer` | the line one level up left `self["answer"]` `None` |
| `indented N spaces, but indent is M` | a width that isn't a whole number of levels |
| `a group's definition lines must have the language and flags of its first line` | definition lines in a row, with different languages or flags |
| `unknown flag 'x'` | a flag that isn't declared |
| `NAME takes no flag 'x'` | a language that doesn't accept that flag (its `flags` field) |
| `KIND NAME has no field 'x'` | a field the kind doesn't have |
| `KIND NAME is there already (declared in FILE): to replace it, write replaces …` | an entry another file declared, declared again without `replaces` |
| `KIND NAME was declared in FILE, not in OTHER` | `replaces` names another file than the one that declared it |
| `KIND NAME replaces nothing` | `replaces` on an entry no other file declared before |
| `KIND NAME is built in: it can't be replaced` | an entry the interpreter has built in, declared again |
| ``language NAME has no `does` `` | a definition in a language without its Python |
| `NAME applies to a definition` (or `a name`) | a modifier in front of the wrong kind of line |
| `syntax error in body of 'def …'` | the Python body doesn't compile |
| `'…' never finishes (it keeps matching itself)` | a def whose value is read with the same def again |
| `in '…': ERROR` | a Python error in a body |
| `expected a number, got …` | `number(…)` of something that isn't a number |
| `cannot use 'x'` | no `x.def` and no library `x` |
| `x has no shared variable 'n'` | `use n from x`, but `x` doesn't say `shared n` |
| `` `as` is only for names `` | `as` after a file name, like `use core as c` |

### F. The Interpreter's Files

| File | Does |
|---|---|
| `__main__.py` | the command: console, run, check, install |
| `execute.py` | runs lines: statements, defs, `use`, variables, calls |
| `tree.py` | reads a line into a tree: which def wraps which |
| `definition.py` | a def: its patterns and its body |
| `values.py` | values, `Code`, `Variables` |
| `exception.py` | `DefException` |
| `check.py` | `def-lang check` |
| `libraries.py` | finding and installing libraries |
