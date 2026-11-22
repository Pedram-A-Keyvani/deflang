# The def-lang Guide

def-lang is a declarative, natural-language-like programming language. This guide
covers the language and its interpreter.

**Contents**

1. [Getting Started](#1-getting-started)
2. [Lines and Statements](#2-lines-and-statements)
3. [Values](#3-values)
4. [Defs](#4-defs)
5. [Flags](#5-flags)
6. [Variables](#6-variables)
7. [How a Line Is Read](#7-how-a-line-is-read)
8. [Programs and Libraries](#8-programs-and-libraries)
9. [Errors and Checking](#9-errors-and-checking)
10. [Appendix](#10-appendix)

---

## 1. Getting Started

### 1.1 Installation

Needs Python 3.11 or newer; nothing else.

```console
$ pip install .
```

This gives the `def-lang` command. Without installing, use `python -m deflang` from
the folder that holds this one.

### 1.2 Hello, World!

A program is a folder with a `main.def`. The interpreter knows no words like `say`:
a program makes its own with `def`.

<a id="listing-1-1"></a>
**Listing 1-1:** `hello/main.def`

```
def python say A0
    self.say(A0)

say "Hello, world!"
```

```console
$ def-lang run hello
Hello, world!
```

- `def python say A0` makes the word `say`, with a body written in Python.
- `A0` is what stands after `say` on the line.

### 1.3 The Console

```console
$ def-lang
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
| indented, right after a `def` | the def's body |
| indented, not a def body | runs only if the line it belongs to left `self.answer` `True` ([2.2](#22-indentation)) |
| anything else | an expression: read into a tree of defs, then run |

### 2.2 Indentation

`indent N` sets how many spaces make one **level**; each file starts with `indent 4`.
A tab is always one level. A width that isn't a whole number of levels is an error.

| An indented line… | Is |
|---|---|
| right after a `def` or `language` line | the body: it ends at the next line of level 0 |
| anywhere else | it belongs to the last line one level up, and runs only if that line ran and left `self.answer` `True` |

<a id="listing-2-1"></a>
**Listing 2-1**

```
def python say A0
    self.say(A0)

def python A0 > A1 ?
    self.answer = number(A0) > number(A1)

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
def python say A0
    self.say(A0)

def python A0 > A1 ?
    self.answer = number(A0) > number(A1)

def python otherwise ?
    self.answer = not self.answer

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
- Before a line runs, `self.answer` is the answer of the last line on its own level:
  `otherwise ?` turns around `5 > 3 ?`, not `5 > 10 ?`.
- Each def call has its own levels; the answer it leaves still comes out.
- Empty lines and comment lines don't end a body. In a Python or other-language body,
  that language checks the indentation.
- Variables don't follow levels: they belong to the def call ([chapter 6](#6-variables)).

### 2.3 Statements

The interpreter's only words:

| Statement | Does |
|---|---|
| `def [FLAGS] PATTERN` | makes a def ([chapter 4](#4-defs)) |
| `use NAME` | runs `NAME.def`, or a library, once ([chapter 8](#8-programs-and-libraries)) |
| `use NAMES from NAME` | the same, and this file gets `NAME`'s shared variables `NAMES` ([chapter 6](#6-variables)) |
| `use NAME as OTHER from FILE` | the same as `use NAME from FILE`, but this file calls it `OTHER` |
| `comment is X` | lines starting with `X` are comments |
| `argument is X` | arguments are written `X0`, `X1`, … |
| `indent N` | `N` spaces make one level ([2.2](#22-indentation)) |
| `shared NAME` | in this file, `NAME` is the shared variable; the rest of the line runs as usual ([chapter 6](#6-variables)) |
| `language NAME` | makes a language ([chapter 5](#5-flags)) |
| `error MESSAGE` | stops with `MESSAGE` |
| `` `LINE` `` | prints `LINE`, then runs it |

### 2.4 Comments

<a id="listing-2-3"></a>
**Listing 2-3**

```
def python say A0
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
def python say A0
    self.say(A0)

def python as written A0 is A1
    self.variables[A0] = self.run(A1)

def python A0 + A1
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
def PATTERN
    BODY
```

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
def python say A0
    self.say(A0)

argument is X
def python X0 times X1
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
def python say A0
    self.say(A0)

def python A0 + A1
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
def python say A0
    self.say(A0)

def python half of A0
    return number(A0) / 2

say half of 9
```

```console
4.5
```

- The body is a Python function; `return` gives the def's value.
- It gets `self` (the interpreter) and the arguments ([Appendix C](#c-the-python-api)).

### 4.4 Several Patterns, One Body

<a id="listing-4-4"></a>
**Listing 4-4**

```
def python say A0
    self.say(A0)

def python A0 + A1
    return number(A0) + number(A1)

def A0 plus A1
def the sum of A0 and A1
    A0 + A1

say the sum of 2 and 3
```

```console
5
```

- `def` lines in a row share the body below them.
- Flags go on the first line; every line of the group has the same flags.

### 4.5 Restricted Arguments

<a id="listing-4-5"></a>
**Listing 4-5**

```
def python say A0
    self.say(A0)

def python A0 + A1
    return number(A0) + number(A1)

def python as written (A0: one|two|three)
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
def python say A0
    self.say(A0)

def python as written A0 is A1
    self.variables[A0] = self.run(A1)

def python A0 + A1
    return number(A0) + number(A1)

def python A0 "A1" A2
def python "A0" A1
def python A0 "A1"
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

## 5. Flags

Written right after `def`, before the pattern.

### 5.1 `as written`

The def gets its arguments as they are written, not their values.

<a id="listing-5-1"></a>
**Listing 5-1**

```
def python say A0
    self.say(A0)

def python as written twice : A0
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
- a word itself ([Listing 4-5](#listing-4-5): without `as written`, `two`'s value would be read
  with the same def again, and again).

### 5.2 `regex`

The pattern is a raw regex; ` or ` splits alternatives.

<a id="listing-5-2"></a>
**Listing 5-2**

```
def python say A0
    self.say(A0)

def python regex (A0: \d+)% or (A0: \d+) percent
    return number(A0) / 100

say 50 percent
```

```console
0.5
```

### 5.3 Languages

`language NAME` makes `NAME` a flag. The Python below it runs the bodies of those
defs.

<a id="listing-5-3"></a>
**Listing 5-3**

```
def python say A0
    self.say(A0)

language upper
    return fill(BODY, [as_text(value) for value in VAR]).upper()

def upper greeting for A0
    hello A0, how are you?

say greeting for "sam"
```

```console
HELLO SAM, HOW ARE YOU?
```

- The Python gets `BODY` (the body text), `VAR` (the argument values) and
  `fill(BODY, values)` (puts values where `A0`, `A1`, … are).
- `python` is built in.
- What a language returns is `Code`: another language puts it in unescaped.

---

## 6. Variables

From the smallest scope to the largest:

| Variable | Made by | Seen by |
|---|---|---|
| a def's own | setting it inside a def-lang def | that def call, until it ends |
| the file's | setting it outside any def | that file's lines and its defs |
| shared | `shared NAME` | the file that made it, and the files that say `use NAME from FILE` |

Variables don't follow indentation ([2.2](#22-indentation)).

### 6.1 A Def's Own

<a id="listing-6-1"></a>
**Listing 6-1**

```
def python say A0
    self.say(A0)

def python as written A0 is A1
    self.variables[A0] = self.run(A1)

def python A0 + A1
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
- An `as written` def has none: it runs the caller's words where they were written,
  with the caller's variables.

### 6.2 The File's

<a id="listing-6-2"></a>
**Listing 6-2**

```
def python say A0
    self.say(A0)

def python as written A0 is A1
    self.variables[A0] = self.run(A1)

def python A0 + A1
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
def python as written A0 is A1
    self.variables[A0] = self.run(A1)

shared visits is 0
```

<a id="listing-6-4"></a>
**Listing 6-4:** `main.def`, next to `counter.def`

```
def python say A0
    self.say(A0)

def python as written A0 is A1
    self.variables[A0] = self.run(A1)

def python A0 + A1
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
def python say A0
    self.say(A0)

def python as written A0 is A1
    self.variables[A0] = self.run(A1)

def python A0 + A1
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
def python say A0
    self.say(A0)

def python A0 ?
    self.answer = bool(A0)

def python as written A0 is A1
    self.variables[A0] = self.run(A1)

def python as written keep A0 is A1
    self.share(A0.strip())
    self.variables[A0.strip()] = self.run(A1)

def python as written A0 if A1 otherwise A2
    return self.run(A0) if self.run(A1) else self.run(A2)

def python as written repeat A0 times : A1
    for _ in range(number(self.run(A0))):
        self.run(A1)

def python as written all of A0 are A1
    return all(self.run(as_code(item) + " " + A1) for item in self.run(A0))

def python A0 "A1" A2
def python "A0" A1
def python A0 "A1"
    return "".join(as_text(value) for value in a)

def python A0 > A1
    return number(A0) > number(A1)

def python A0 + A1
    return number(A0) + number(A1)

def python count of A0
    return len(A0)
```

| # | Rule | Line | Read as |
|---|---|---|---|
| 1 | A match whose fixed words are all part of a longer match loses | `keep visits is 0` | `keep A0 is A1`, not `A0 is A1` |
| 2 | **Brackets:** a def whose fixed words surround another's wraps it | `"big" if 5 > 3 otherwise "small"` | `if … otherwise` wraps `>` |
| 3 | **Sentences:** an `as written` def that starts the line with two or more fixed words wraps what follows them | `repeat 3 times: x is x + 1` | `repeat` wraps `is` |
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
3. in the program's libraries;
4. for a file of a library: in the libraries next to that library.

A file runs once; using it again does nothing. `as` is only for names: `use core as c`
is an error.

### 8.2 Libraries

A library is a folder of `.def` files with a `library.toml`:

| Key | Is |
|---|---|
| `name` | the library's name (required) |
| `needs` | the names of the libraries it uses, installed with it |

A program's libraries are:

- **`libraries/NAME/`**: an installed copy;
- **`libraries.toml`**: each library and where it comes from:
  `NAME = "SOURCE"`, or `NAME = { from = "FOLDER", link = true }` for a linked one.

### 8.3 Installing

```console
$ def-lang install FOLDER
$ def-lang install URL#FOLDER
$ def-lang install FOLDER --link
$ def-lang install
```

- `FOLDER`: copies the library into `libraries/`, and adds it to `libraries.toml`.
- `URL#FOLDER`: the library in that folder of a git repo (needs git).
- `--link`: no copy; `libraries.toml` points to the folder.
- no source: installs everything in `libraries.toml` again.
- The libraries in `needs` are taken from next to the one being installed.
- It works on the program in the current folder; `--into FOLDER` picks another.

---

## 9. Errors and Checking

An error stops the program with its message; in a used file it starts with
`FILE:LINE:`. All messages are listed in [Appendix D](#d-error-messages).

```console
$ def-lang check hello
```

`check` reads a program without running it:

- **runs:** `use`, `def`, `language`, `comment is`, `argument is`, and the defs
  that call `self.alias`;
- **only reads:** every other line, so nothing is asked, printed or started;
- **finds:** unknown names, files it can't find, a missing closing quote or `)`, an
  indented line with nothing to belong to, a Python syntax error in a body;
- **doesn't find:** errors that only happen while running, like `expected a number`.

Variable names come from the Python bodies: an `as written` argument that a body
stores under (`self.variables[A0]`, `self.share(A0, …)`) is a name.

- `--json` prints the result as JSON.
- `--text FILE` reads `FILE`'s text from stdin instead of the disk.

---

## 10. Appendix

### A. Statements

| Statement | Scope |
|---|---|
| `def [FLAGS] PATTERN` | from here on, every file |
| `use NAME` | runs once per program |
| `use NAMES from NAME` | the names: to the end of the file |
| `use NAME as OTHER from FILE` | `OTHER`: to the end of the file |
| `comment is X` | to the end of the file; each file starts with `//` |
| `argument is X` | to the end of the file; each file starts with `A` |
| `indent N` | to the end of the file; each file starts with `4` |
| `shared NAME` | to the end of the file |
| `language NAME` | from here on, every file |
| `error MESSAGE` | stops the program |
| `` `LINE` `` | that line |

### B. Flags

| Flag | Meaning |
|---|---|
| `as written` | the def gets its arguments as they are written, not their values |
| `python`, or a `language` name | the body is written in that language |
| `regex` | the pattern is a raw regex; ` or ` splits alternatives |

### C. The Python API

| Name | Is |
|---|---|
| the argument names | `A0`, `A1`, …: the argument's value, or its words if the def is `as written` |
| `self.run(text)` | runs def-lang text and returns its value |
| `self.say(value)` | prints a value |
| `self.variables` | the variables of the running code: `self.variables["x"] = 5` |
| `self.share(name)` | what `shared NAME` does |
| `self.answer` | whether the lines one level below run: they run if it is `True`; `None` makes them an error |
| `self.alias(phrase, words)` | from now on, `phrase` reads as `words` (longer phrases first) |
| `self.lookup(name)` | a variable's value, or an `unknown name` error |
| `self.file_path(name)` | a file's path, relative to the program's folder |
| `self.store(name)` | a dict for a library's own state: the same dict for the same name |
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

### D. Error Messages

| Message | Cause |
|---|---|
| `unknown name 'x'` | no def, variable or value is `x` |
| `missing closing quote in: …` | a `"` with no closing `"` |
| `missing ')' in: …` | a restricted argument with no closing bracket |
| `invalid def pattern '…'` | a pattern that isn't a valid regex |
| `indented line with no line above it to belong to` | an indented line with no line one level up |
| `indented line, but the line above it gave no answer` | the line one level up left `self.answer` `None` |
| `indented N spaces, but indent is M` | a width that isn't a whole number of levels |
| `a def group's lines must have the flags of its first line` | stacked `def` lines with different flags |
| `syntax error in body of 'def …'` | the Python body doesn't compile |
| `language NAME has no body` | `language NAME` with no indented Python below it |
| `'…' never finishes (it keeps matching itself)` | a def whose value is read with the same def again |
| `in '…': ERROR` | a Python error in a body |
| `expected a number, got …` | `number(…)` of something that isn't a number |
| `cannot use 'x'` | no `x.def` and no library `x` |
| `x has no shared variable 'n'` | `use n from x`, but `x` doesn't say `shared n` |
| `` `as` is only for names `` | `as` after a file name, like `use core as c` |

### E. The Interpreter's Files

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
