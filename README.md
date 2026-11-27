# The def-lang Guide

def-lang is a declarative, natural-language-like programming language. This guide
covers its interpreter: how it reads lines, and what it gives the Python you write.

The interpreter knows two words of its own: `python`, to make a definition in Python,
and `use`, to run another file or a library. Everything else is declared, the way
[chapter 5](#5-entries-languages-flags-modifiers-and-statements) shows: the def-lang
language `def`, the flags `written` and `regex`, `comment is`, `shared`, … are entries
of the libraries in deflang-lib, each described in its README.

**Related repositories**

| Repository | Holds |
|---|---|
| [deflang-lib](https://github.com/Pedram-A-Keyvani/deflang-lib) | the libraries, each with one job and a README of its words: `core` (a bundle of the everyday words: values, questions, loops, lists, text, math, ...), `language` (`def`, `html`, `css`, `javascript`), `flag`, `statement`, `modifier`, `entry`, `files`, `settings`, and for the web `http`, `server`, `website`, `api`, `template`, `spa` |
| [deflang-sample](https://github.com/Pedram-A-Keyvani/deflang-sample) | sample programs (hello world to a website), and the tests of the interpreter and the libraries |
| [deflang-editor](https://github.com/Pedram-A-Keyvani/deflang-editor) | the VS Code extension: colors, hover, Ctrl+click, IntelliSense, errors as you type; it finds or installs the interpreter |

**Contents**

1. [Getting Started](#1-getting-started)
2. [Lines](#2-lines)
3. [Values](#3-values)
4. [Definitions](#4-definitions)
5. [Entries: Languages, Flags, Modifiers and Statements](#5-entries-languages-flags-modifiers-and-statements)
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
- A program usually starts with `use core`: the core library gives `say`, `is`, `def`
  and many more words ([8.2](#82-libraries)). This guide's listings make their own
  instead, to show how they work.

### 1.3 The Console

```console
def-lang
```

- Type lines, then `on` to run them.
- `clean` forgets the values; `off` quits.
- `run FOLDER` runs a program.

---

## 2. Lines

### 2.1 Kinds of Line

| Line | Is |
|---|---|
| empty | nothing |
| starts with the comment marker, `//` | a comment ([2.3](#23-comments)) |
| a statement: `use`, or one a library declares, like `comment is #` | a whole line the reader knows ([5.5](#55-statements), [8.1](#81-using-files)) |
| an entry: `language`, `flag`, `modifier` or `statement`, then a name | declares one ([chapter 5](#5-entries-languages-flags-modifiers-and-statements)) |
| a modifier, then the rest of a line | the rest, changed by the modifier ([5.4](#54-modifiers)) |
| a definition: a language (`python`, or a declared one), then its pattern | makes one ([chapter 4](#4-definitions)) |
| indented, right after a definition or an entry | its body, or its fields |
| indented, anywhere else | runs only if the line it belongs to left `self["answer"]` `True` ([2.2](#22-indentation)) |
| anything else | an expression: read into a tree of definitions, then run ([chapter 7](#7-how-a-line-is-read)) |

### 2.2 Indentation

Four spaces make one **level**; a tab is always one level. A width that isn't a whole
number of levels is an error. (The statement library's `indent N` sets another width
for a file.)

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

python otherwise ?
    self["answer"] = not self["answer"]

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
- The lines a definition runs ([Listing 5-2](#listing-5-2)) have levels of their own;
  the answer they leave still comes out.
- Empty lines and comment lines don't end a body. A body's language reads its
  indentation when the definition runs.
- Variables don't follow levels ([chapter 6](#6-variables)).

### 2.3 Comments

Lines starting with `//` are comments. (The statement library's `comment is X` sets
another marker for a file; each file starts with `//`.)

<a id="listing-2-2"></a>
**Listing 2-2**

```
python say A0
    self.say(A0)

// Says it twice.
python twice A0
    self.say(A0)
    self.say(A0)

// a comment
twice "done"
```

```console
done
done
```

- The comment lines right above a definition or an entry are its description: the
  editor shows them on hover.

---

## 3. Values

| Value | Written |
|---|---|
| number | `5`, `-2`, `2.5` |
| text | `"hello"` |
| list | `[1, "a", [2]]` |
| nothing | a line or definition with no value |

<a id="listing-3-1"></a>
**Listing 3-1**

```
python say A0
    self.say(A0)

python A0 + A1
    return number(A0) + number(A1)

say 2 + 3
say "two"
```

```console
5
two
```

- Patterns never match inside text.
- A word that is no definition, variable or value is an error: `unknown name`.
- Text next to values (`"x = " 5`) is joined by a definition, not by the language
  ([Listing 4-5](#listing-4-5)).

---

## 4. Definitions

```
LANGUAGE[FLAGS] PATTERN
    BODY
```

- **The language** says what the body is written in: `python` is built in; others are
  declared ([5.2](#52-languages)), like the def-lang language `def`, or `html`.
- **The flags** come right after it, in brackets, and are optional
  ([5.3](#53-flags)).
- **The pattern** comes after a space; it can start with any word, or with `[`.

This chapter's definitions are in Python; in another language they work the same way,
with a body in that language.

### 4.1 Patterns and Arguments

In `repeat A0 times : A1`:

- **fixed words:** `repeat`, `times`, `:`: they must appear as they are;
- **arguments:** `A0`, `A1`: whatever stands in their place.

Words need spaces between them; symbols don't (`2+3` matches `A0 + A1`). In a pattern,
write a space around a symbol too: `[ A0 ] first`, not `[A0] first`; only right after
an argument, a symbol may follow without one: `A0 and A1, as A2`.

**Naming:** a definition that gives a value reads best as a thing (`A0 plus the rate`,
`total of A0 and A1`); one that does something, as a command (`say A0`,
`count the visit`). Then a line reads as one sentence: `say 4 plus the rate`.
A definition named as a thing only gives a value: it changes nothing, so it gives the
same answer every time.

<a id="listing-4-1"></a>
**Listing 4-1**

```
python say A0
    self.say(A0)

python A0 times A1
    return number(A0) * number(A1)

say 2 times 3
```

```console
6
```

- The arguments are `A0`, `A1`, …. (The statement library's `argument is X` makes
  them `X0`, `X1`, … for a file.)

### 4.2 Python Bodies

<a id="listing-4-2"></a>
**Listing 4-2**

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

- The body is a Python function; `return` gives the definition's value.
- It gets `self`, the kernel ([Appendix C](#c-the-python-api)), and the arguments by
  their names: their values, or their words for a `written` definition
  ([5.3](#53-flags)).

### 4.3 Several Patterns, One Body

<a id="listing-4-3"></a>
**Listing 4-3**

```
python say A0
    self.say(A0)

python A0 plus A1
python the sum of A0 and A1
    return number(A0) + number(A1)

say the sum of 2 and 3
say 2 plus 3
```

```console
5
5
```

- Definition lines in a row share the body below them.
- Every line of the group has the same language and flags.

### 4.4 Restricted Arguments

<a id="listing-4-4"></a>
**Listing 4-4**

```
python say A0
    self.say(A0)

python (A0: \d+) dozen
    return number(A0) * 12

say 2 dozen
```

```console
24
```

- `(A0: REGEX)` matches only that regex: `say many dozen` is no match.
- A definition with no fixed words is a **word list**: it matches a whole value
  ([chapter 7](#7-how-a-line-is-read)).

### 4.5 Text Arguments

`"A0"` in a pattern matches only a text.

<a id="listing-4-5"></a>
**Listing 4-5**

```
python say A0
    self.say(A0)

python A0 "A1" A2
python "A0" A1
python A0 "A1"
    return "".join(as_text(value) for value in a)

python A0 + A1
    return number(A0) + number(A1)

say "x = " 2 + 3
```

```console
x = 5
```

- The quotes of `"A0"` count as fixed words.
- This definition joins text and values next to each other. Like any definition, it
  binds by order ([chapter 7](#7-how-a-line-is-read)): made after `say` and before
  `+`, `say "x = " 2 + 3` says `x = 5`.

---

## 5. Entries: Languages, Flags, Modifiers and Statements

Besides definitions, a file can declare **entries**: a language for bodies, a flag for
definitions, a modifier for lines, or a statement. The libraries declare theirs the
same way: `def`, `written`, `shared` and `comment is` are entries of deflang-lib
([5.7](#57-the-libraries-entries)).

### 5.1 Writing an Entry

```
// Its help: what it is.
KIND NAME
    FIELD VALUE
    does in LANGUAGE[FLAGS]
        BODY
```

- **`KIND`** is `language`, `flag`, `modifier` or `statement`; **`NAME`** is one word.
- **The fields** are one level in, one on each line.
- **`does in LANGUAGE`** says the language of its body, which is one level deeper:
  `does in python` (built in), `does in def`, or any declared language. Flags may
  follow, as on a definition line: `does in def[written]` gets its arguments' words.
- **The help** is the comment lines right above it, like a definition's description.
- An entry is the same for the whole program, from where it is declared on.

| Field | Of | Says |
|---|---|---|
| `does in LANGUAGE[FLAGS]` | every kind | what it does, in that language, with those flags |
| `editor` | a language | VS Code's language id for its bodies (`html`), for coloring and formatting them |
| `words` | a statement | the words of its line, written like a pattern: `comment is A0` |
| `words` | a flag | how it is written in the brackets, like a pattern: `cache A0 seconds` for `[cache 60 seconds]`. Without it, the flag is its name: `[written]` |
| `replaces` | every kind | the file whose entry of the same kind and name it replaces ([5.6](#56-replacing-an-entry)) |

**When it acts, and on what.** The interpreter knows what an entry is from where its
name stands, and when it acts. Its `does` runs then, where it acts (in the variables of
that line), and finds what it acts on in `self["entry"]`:

| Kind | Stands | Acts | On |
|---|---|---|---|
| language | at the start of a definition line | when the definition runs | `"definition"`, `"template"`, `"values"`, `"fill"`, `"body"` |
| flag | in brackets after the language | when the definition is made, before its pattern is read | `"definition"`; and its words, `A0`, `A1`, … (`a[0]`, … in Python) |
| modifier | in front of a line | in front of a definition: right after it is made; in front of a name: before the rest of the line runs | `"definition"`, or `"name"` |
| statement | a whole line, by its `words` | when the line is read | its words: `A0`, `A1`, … (`a[0]`, `a[1]`, … in Python) |

A statement's or a flag's words come to `does in def` as text, like `"#"`; with
`does in def[written]`, as the words themselves, like `#`. Python gets them as text.

| `self["entry"][…]` | Of | Is |
|---|---|---|
| `"kind"` | every kind | `"language"`, `"flag"`, `"modifier"` or `"statement"` |
| `"definition"` | a language, a flag, a modifier | the definition it acts on |
| `"template"` | a language | the definition's body, without its common indentation; the places of its arguments are marked in it |
| `"values"` | a language | the arguments, in order: their values, or their words for a definition that keeps them |
| `"fill"` | a language | `fill(template, values)`: the template with each place filled in with its value, as text |
| `"body"` | a language | the template filled in with the values as text; the definition's value when `does` ends, unless `does` gives back another |
| `"as written"` | a language | `True` when the definition keeps its arguments' words |
| `"in place"` | a language | `True` when the definition is an entry's `does`: it runs where the entry acts |
| `"name"` | a modifier | the name after it, as text |
| `"scope"` | a statement | a list, empty at first: the files (or a library's folder, all its files) whose phrases are read first, for the rest of its `does` and for the lines under it ([chapter 7](#7-how-a-line-is-read)); `self.scope_of(NAME)` gives one |

**A definition** has `source` (its pattern), `language`, `flags`
(`{"written": [], "cache": ["60"]}`: each flag, and its words), `file`, and `indent` and `comment` (those of its file
where it was written: its body's lines are read with them). And three **hooks**: the
kernel calls them, and an entry may change them:

| Hook | The kernel calls it | Its default |
|---|---|---|
| `read_pattern(text, argument)` | when the definition line is read: its pattern's text, as a list of regexes | readable patterns: words, `A0`, `(A0: …)`, `"A0"` |
| `read_argument(text, read)` | when a line that uses it is read: an argument's text, as what the body gets | `read(text)`: read as an expression, run for its value; a text it gives back stays words |
| `seen_by(file)` | when a line is read: whether a line of that file may use it | `True` |

**What `does` gives back.** A language's: the definition's value (or else `"body"`).
A statement's: nothing, or a value; then the line is like an expression, with that
value. A flag's and a modifier's: nothing.

**In def.** The `entry` library gives the words to write entries in def,
like `set arguments to as written`: then most entries need no Python. A modifier that
needs a real capability declares a cycle hook instead
([5.7](#57-the-libraries-entries)). deflang-lib's
[Writing Languages, Flags, Modifiers and Statements](https://github.com/Pedram-A-Keyvani/deflang-lib/blob/main/ENTRIES.md) says what each word
means, with an example of each kind. This guide's listings use only what the
interpreter has, so they say it in Python.

### 5.2 Languages

A language runs the bodies of its definitions: its `does` gets the body and the
arguments, and gives the definition's value.

<a id="listing-5-1"></a>
**Listing 5-1**

```
python say A0
    self.say(A0)

// Its body, in capitals.
language upper
    does in python
        return self["entry"]["body"].upper()

upper greeting for A0
    hello A0, how are you?

say greeting for "sam"
```

```console
HELLO SAM, HOW ARE YOU?
```

- What a language gives is its definition's value. Text that is code in another
  language, like HTML, is given as `Code(text)`: an HTML body puts it in as it is,
  not escaped.

def-lang bodies are a language too. This is how the language library declares `def`:

<a id="listing-5-2"></a>
**Listing 5-2**

```
python say A0
    self.say(A0)

python A0 + A1
    return number(A0) + number(A1)

// def-lang: the body's lines run one by one, with A0, A1, ... put in.
language def
    does in python
        ENTRY = self["entry"]
        TEXTS = ENTRY["values"] if ENTRY["as written"] else [as_code(value) for value in ENTRY["values"]]
        LINES = ENTRY["fill"](ENTRY["template"], TEXTS)
        if ENTRY["as written"] or ENTRY["in place"]:
            ENTRY["body"] = self.run_lines(LINES, ENTRY["definition"])
        else:
            with self.own_variables(ENTRY["definition"].file):
                ENTRY["body"] = self.run_lines(LINES, ENTRY["definition"])

def A0 doubled
    A0 + A0

say 4 doubled
```

```console
8
```

- The values go in as code: `as_code(value)` writes a value the way def-lang reads it
  back (a text with its quotes). A definition that keeps its arguments' words gets
  the words as they were written. (The language library's `def` goes further: a value
  that isn't a number, true or false comes in by its name, a variable of the call
  named `A0`, `A1`, …, so a text never joins the words around it.)
- `self.run_lines(text, definition)` runs lines the way a file's lines run, with the
  indent and comment marker the definition was written with: each line on its level,
  comments skipped. It gives the value of the last line that has one.
- `self.own_variables(file, hooks=())` gives the lines variables of their own, on top of the
  file's ([chapter 6](#6-variables)). A definition that keeps its arguments' words,
  or an entry's `does` (`"in place"`), runs where it acts, with the variables there.
- Every language takes every flag: `def[written] …`, `css[written] …`.

### 5.3 Flags

A flag is written in brackets right after the language: `python[written] …`; several
with commas: `python[written, regex] …`. It is always written out, never a variable.
Its `does` runs when a definition is made, before its pattern is read: it can change
how the definition is read through its hooks.

<a id="listing-5-3"></a>
**Listing 5-3**

```
python say A0
    self.say(A0)

// The definition gets its arguments as they are written, not their values.
flag written
    does in python
        self["entry"]["definition"].read_argument = lambda text, read: text

python[written] twice : A0
    self.run(A0)
    self.run(A0)

twice : say "hi"
```

```console
hi
hi
```

- `read_argument` gives back the text itself: the body gets the words.
- Use `written` when a definition needs the **words** of an argument: a name to store
  under (`A0 is A1`, [chapter 6](#6-variables)); code to run later, many times, or
  maybe not at all ([Listing 5-3](#listing-5-3)); a word itself (a word list,
  [Listing 7-1](#listing-7-1)).

<a id="listing-5-4"></a>
**Listing 5-4**

```
python say A0
    self.say(A0)

// The pattern is a raw regex: ` or ` splits alternatives; (A0: ...) is an argument.
flag regex
    does in python
        import re

        def read(text, name):
            restricted = re.compile(r"\(" + re.escape(name) + r"(\d+):\s*")
            argument = re.compile(re.escape(name) + r"(\d+)")
            alternatives = []
            for one in text.split(" or "):
                one = restricted.sub(lambda m: "(?P<a" + m.group(1) + ">", one.strip())
                alternatives.append(argument.sub(lambda m: "(?P<a" + m.group(1) + r">[\s\S]+)", one))
            return alternatives

        self["entry"]["definition"].read_pattern = read

// Says what a definition is made for.
flag note
    words note A0
    does in python
        self.say(self["entry"]["definition"].source + ": " + a[0])

python[regex, note for percentages] (A0: \d+)% or (A0: \d+) percent
    return number(A0) / 100

say 50 percent
```

```console
(A0: \d+)% or (A0: \d+) percent: for percentages
0.5
```

- `read_pattern` gives the regexes the pattern is read as.
- A flag with `words` is written by them: `[note for percentages]`. Its `does` gets
  the words in their places: `a[0]` is `for percentages`.
- A flag is declared before a definition uses it: else `unknown flag`. Every language
  takes every flag.

### 5.4 Modifiers

A modifier is a word in front of a line that changes where something is seen.

<a id="listing-5-5"></a>
**Listing 5-5**

```
python say A0
    self.say(A0)

// Valid only in its own file.
modifier internal
    hook define end in python
        DEFINITION = self["cycle"]["definition"]
        DEFINITION.visibility = "file"
        DEFINITION.seen_by = lambda file: file == DEFINITION.file

internal python A0 halved
    return number(A0) / 2

say 9 halved
```

```console
4.5
```

- In front of a definition, a `define` hook runs around making it: the `end` phase sees
  it in `self["cycle"]["definition"]`.
- `seen_by` says which files see it: an `internal` definition is seen only by its own
  file, its lines and its other definitions (also when another file calls them).
- In front of a **name**, a `define` hook sees that name in `self["entry"]["name"]`,
  and the rest of the line runs as an ordinary line: `shared visits is 0` names
  `"visits"` as shared, then runs `visits is 0` ([6.2](#62-shared)).
- Modifiers stack: `internal shared …` applies each in turn.

### 5.5 Statements

A statement is a whole line the reader knows. Its `words` are matched before anything
else on a line (after `use`), so they never read as part of an expression.

<a id="listing-5-6"></a>
**Listing 5-6**

```
python say A0
    self.say(A0)

// Says hello.
statement greet
    words greet A0
    does in python
        self.say("hello " + a[0].strip())

// Lines starting with A0 are comments, from here to the end of the file.
statement comment
    words comment is A0
    does in python
        self["files"][self["file"]]["comment"] = a[0].strip()

comment is #
# not run
greet Sam
```

```console
hello Sam
```

- `does` gets the words in the places of `A0`, `A1`, …, as they are written.
- `self["files"][self["file"]]` is the file's place in the kernel. The interpreter
  reads the file's lines with its `"comment"`, `"argument"` and `"indent"`, line by
  line, so a statement can change them.
- A statement whose `does` gives a value is like an expression line: the statement
  library's `` `LINE` `` prints `LINE`, then gives its value.

### 5.6 Replacing an Entry

An entry is declared once. Another file replaces it only by saying so, with the field
`replaces FILE`: the file that declared it, named the way `use` names it. From then on,
the new entry is used, also by definitions made before it:

```
language css
    replaces language/css
    editor css
    does in python
        ...
```

- Without `replaces`, declaring an entry another file declared is an error.
- The interpreter's own entries, `python` and `use`, can't be replaced.

### 5.7 The Libraries' Entries

deflang-lib declares these, one file each; `use core` uses them all. The flags and
statements are written in def, with the words of the `entry` library; modifiers use
cycle hooks when they need a capability of their own:

```
flag written
    does in def
        set arguments to as written

modifier internal
    hook define end in python
        DEFINITION = self["cycle"]["definition"]
        DEFINITION.visibility = "file"
        DEFINITION.seen_by = lambda file: file == DEFINITION.file

statement comment
    words comment is A0
    does in def[written]
        set comment marker to A0
```

| Entry | File | Is |
|---|---|---|
| `language def` | `language/def.def` | def-lang bodies ([Listing 5-2](#listing-5-2)) |
| `language html`, `css`, `javascript` | `language/html.def`, … | bodies in those languages |
| `flag written`, `regex` | `flag/written.def`, `flag/regex.def` | [Listing 5-3](#listing-5-3), [Listing 5-4](#listing-5-4) |
| `statement comment`, `argument`, `indent`, `error`, `echo` | `statement/comment.def`, … | `comment is X`, `argument is X`, `indent N`, `error MESSAGE`, `` `LINE` `` |
| `statement scope`, `scoped` | `statement/scope.def` | `in the scope of FILES` with the lines under it, and `in the scope of FILES, LINE` ([chapter 7](#7-how-a-line-is-read)) |
| `modifier shared`, `internal` | `modifier/shared.def`, … | [6.2](#62-shared), [Listing 5-5](#listing-5-5) |

[Writing Languages, Flags, Modifiers and Statements](https://github.com/Pedram-A-Keyvani/deflang-lib/blob/main/ENTRIES.md) explains these words,
one by one.

---

## 6. Variables

From the smallest scope to the largest:

| Variable | Made by | Seen by |
|---|---|---|
| a call's own | setting it in lines that run with `self.own_variables`, like a def-lang definition's | those lines, until they end |
| the file's | setting it in a file's lines, outside any definition | that file's lines and its definitions |
| shared | a modifier that names it in its file's `"names"`, like `shared NAME` | the file that made it, and the files that say `use NAME from FILE` |

A Python body reads and sets them as `self["variables"]`: the variables of the code
that runs it. Variables don't follow indentation ([2.2](#22-indentation)).

### 6.1 A Call's Own, and the File's

<a id="listing-6-1"></a>
**Listing 6-1**

```
python say A0
    self.say(A0)

flag written
    does in python
        self["entry"]["definition"].read_argument = lambda text, read: text

python[written] A0 is A1
    self["variables"][A0] = self.run(A1)

python A0 + A1
    return number(A0) + number(A1)

language def
    does in python
        ENTRY = self["entry"]
        TEXTS = ENTRY["values"] if ENTRY["as written"] else [as_code(value) for value in ENTRY["values"]]
        LINES = ENTRY["fill"](ENTRY["template"], TEXTS)
        if ENTRY["as written"] or ENTRY["in place"]:
            ENTRY["body"] = self.run_lines(LINES, ENTRY["definition"])
        else:
            with self.own_variables(ENTRY["definition"].file):
                ENTRY["body"] = self.run_lines(LINES, ENTRY["definition"])

rate is 2
def A0 plus the rate
    sum is A0 + rate
    sum

say 4 plus the rate
say rate
```

```console
6
2
```

- `rate` is the file's: the file's lines and its definitions see it, even when another
  file calls them. Other files don't.
- `sum` is the call's own: `self.own_variables` gives it, and it is gone when the call
  ends. Each call has its own: a definition that calls itself doesn't share them.
- Setting a variable inside the call makes the call's own; the file's stays as it was.
- A `written` definition has none of its own: it runs the caller's words where they
  were written, with the caller's variables.

### 6.2 Shared

<a id="listing-6-2"></a>
**Listing 6-2:** `counter.def`

```
flag written
    does in python
        self["entry"]["definition"].read_argument = lambda text, read: text

python[written] A0 is A1
    self["variables"][A0] = self.run(A1)

// One variable for the whole program.
modifier shared
    hook define start in python
        HERE, NAME = self["file"], self["entry"]["name"]
        self["files"][HERE]["names"][NAME] = (HERE, NAME)

shared visits is 0
```

<a id="listing-6-3"></a>
**Listing 6-3:** `main.def`, next to `counter.def`

```
python say A0
    self.say(A0)

use visits from counter

python A0 + A1
    return number(A0) + number(A1)

visits is visits + 1
say visits
```

```console
1
```

- `shared visits` names `visits` in `counter.def`'s `"names"`: it is a shared variable
  of that file. The rest of the line runs as an ordinary line: `visits is 0`.
- `use visits from counter` runs `counter.def` (once), and `visits` in this file is
  counter's: the same variable, not a copy. Its lines and definitions change the
  shared one.
- `counter.def`'s entries and definitions, like `is`, are the program's from then on.
  The `use` line comes before `+`: a definition made first wraps
  ([chapter 7](#7-how-a-line-is-read)), so `visits is visits + 1` is
  `visits is (visits + 1)`.
- Several names: `use visits, total from counter`.
- Only shared variables can be used: `use secret from counter` is an error.
- Without the `use` line, `visits` is this file's own: it has no value yet, so
  `visits + 1` is `unknown name 'visits'`.

<a id="listing-6-4"></a>
**Listing 6-4:** `main.def`, next to `counter.def`

```
python say A0
    self.say(A0)

use visits as total from counter

python A0 + A1
    return number(A0) + number(A1)

visits is 2
total is total + 5
say total
say visits
```

```console
5
2
```

- `as` gives counter's `visits` another name here, `total`, so this file can use the
  name `visits` for its own.

---

## 7. How a Line Is Read

A line is read once into a tree, then run. When several definitions match, the shape
of the line decides which one wraps the others.

<a id="listing-7-1"></a>
**Listing 7-1:** the definitions the rules below use, made in this order

```
python say A0
    self.say(A0)

flag written
    does in python
        self["entry"]["definition"].read_argument = lambda text, read: text

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

python[written] (A0: one|two|three)
    return ["one", "two", "three"].index(A0) + 1
```

| # | Rule | Line | Read as |
|---|---|---|---|
| 1 | A match whose fixed words are all part of a longer match loses | `keep visits is 0` | `keep A0 is A1`, not `A0 is A1` |
| 2 | **Brackets:** a definition whose fixed words surround another's wraps it | `"big" if 5 > 3 otherwise "small"` | `if … otherwise` wraps `>` |
| 3 | **Sentences:** a `written` definition that starts the line with two or more fixed words wraps what follows them | `repeat 3 times: x is x + 1` | `repeat` wraps `is` |
| 4 | **Scope:** the same phrase from several files, the same fixed words in the same places: the one in the line's scope; with none, an error | `in the scope of web/http, listen on 80` | web/http's `listen on A0` |
| 5 | **Word lists:** a definition with no fixed words that matches the whole text is one value | `two + three` | `(two) + (three)`: 5 |
| 6 | **Order:** otherwise, the definition made first wraps | `x is 2 + 3 > 4` | `x is ((2 + 3) > 4)` |
| 7 | **No value:** a reading with an argument that can't be a value (an unknown name) loses to the next one | `count of "abc"` | `count of A0`, not `count of` joined with `"abc"` |

- **Closing words (rule 3):** a closing word at the very end, like `?`, isn't part of
  the sentence; the order decides. `all of [1, 2] are > 0 ?` is read as `A0 ?`, because
  `A0 ?` was made first. A text at the very end is no closing word.
- **Phrases (rule 3):** a definition that takes values isn't a sentence:
  `count of [1, 2] > 1` is `(count of [1, 2]) > 1`.
- **Scope (rule 4):** a statement's `does` puts files in its `self["entry"]["scope"]`
  ([5.1](#51-writing-an-entry)); they are the scope of the rest of its `does` and of the
  lines under it. The statement library's are `in the scope of web/http`, with the lines
  under it, and `in the scope of web/http, LINE`. A scope is a file, named the way `use`
  names it, and used if it isn't yet; or a library, all its files: `in the scope of core`.
  A definition's own lines are in its own scope, not in its caller's; a `written`
  definition's run in the caller's. With no scope, `listen on 80` is an error when two
  files have `listen on A0`: the interpreter doesn't guess.
- **Word lists (rule 5):** the word list is `written`: it needs the word itself. Without
  `written`, `two`'s value would be read with the same definition again, and again.
- **Order (rule 6):** in [Listing 7-1](#listing-7-1), `say`, `A0 ?` and `A0 is A1` are
  made before joined text, and joined text before `>` and `+`: so `say "x = " 2 + 3`
  says `x = 5`.

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
`FILE:LINE:`. All messages are listed in [Appendix D](#d-error-messages).

```console
def-lang check hello
```

`check` reads a program without running it:

- **runs:** the statements, the entries, the definitions and their modifiers, and
  the definitions that change `self["aliases"]`;
- **only reads:** every other line, so nothing is asked, printed or started;
- **finds:** unknown names, files it can't find, a missing closing quote or `)`, an
  indented line with nothing to belong to, a Python syntax error in a body;
- **doesn't find:** errors that only happen while running, like `expected a number`.

While it reads, `self["mode"]` is `"checking"`. An entry's `does` still runs, since
it decides how lines are read; it can leave out what only running should do (the
statement library's `error` doesn't stop).
Variable names come from the Python bodies: a `written` argument that a body stores
under (`self["variables"][A0]`) is a name. A def-lang body's lines are read too.

- `--json` prints the result as JSON.
- `--text FILE` reads `FILE`'s text from stdin instead of the disk.

---

## 10. Appendix

### A. Statements

The interpreter's statement is `use`:

| Statement | Scope |
|---|---|
| `use NAME` | runs once per program |
| `use NAMES from NAME` | the names: to the end of the file |
| `use NAME as OTHER from FILE` | `OTHER`: to the end of the file |

The statement library declares the others: `comment is X`, `argument is X` and
`indent N` (each to the end of the file; each file starts with `//`, `A` and `4`),
`error MESSAGE`, `` `LINE` ``, and `in the scope of FILES` (the lines under it, or
the rest of its line after a comma).

### B. Entries

| Entry | Fields | Its `does` acts on (`self["entry"]`) | It gives |
|---|---|---|---|
| `language NAME` | `does in LANGUAGE`, `editor`, `replaces` | `"definition"`, `"template"`, `"values"`, `"fill"`, `"body"`, `"as written"`, `"in place"` | the definition's value, or else `"body"` |
| `flag NAME` | `does in LANGUAGE`, `words`, `replaces` | `"definition"`; its words: `A0`, `A1`, … | nothing |
| `modifier NAME` | `does in LANGUAGE`, `replaces` | `"definition"`, or `"name"` | nothing |
| `statement NAME` | `does in LANGUAGE`, `words`, `replaces` | its words: `A0`, `A1`, … (`a` in Python) | nothing, or the line's value |

Every `does` also gets `self`, the kernel ([Appendix C](#c-the-python-api)), and runs
where its entry acts; `does in LANGUAGE[FLAGS]` may have flags. Built in are `python`
and `use`. Every language takes every flag.

### C. The Python API

A Python body gets `self`, the kernel. What the interpreter has is its tree, read and
changed as `self[...]`; what it does are its methods.

| The tree | Is |
|---|---|
| `self["variables"]` | the variables of the running code: its call's own, its file's, and the shared ones its file names: `self["variables"]["x"] = 5` |
| `self["answer"]` | whether the lines one level below run: they run if it is `True`; `None` makes them an error. The only part that is set: `self["answer"] = True` |
| `self["aliases"]` | `{phrase: words}`: `phrase` reads as `words`, longer phrases first |
| `self["store"][NAME]` | a library's own state: a dict, made on first use |
| `self["file"]` | the file running now |
| `self["program"]` | the program's folder: `self["program"] / "data.txt"` |
| `self["files"][FILE]` | a file's `"comment"`, `"argument"` and `"indent"` as read so far, its `"variables"`, and its `"names"`: the shared variables it uses, `{NAME: (FILE, NAME)}` |
| `self["shared"]` | the shared variables' values: `{(FILE, NAME): value}` |
| `self["definitions"]` | every definition, in the order made |
| `self["language"]`, `self["flag"]`, `self["modifier"]`, `self["statement"]` | the entries: `self["language"]["python"]` |
| `self["mode"]` | `"running"`; `"checking"` while `def-lang check` reads; `"reloading"` while a changed file is read again (only what defines runs) |
| `self["entry"]` | what the entry whose `does` runs acts on ([5.1](#51-writing-an-entry)); `None` outside one |

| Method | Does |
|---|---|
| `self.run(text)` | runs a line of def-lang and gives its value |
| `self.run_lines(text, definition)` | runs lines the way a file's lines run, with the indent and comment marker `definition` was written with (or 4 and `//`): each line on its level, comments skipped; gives the value of the last line that has one. Without `definition`, they are the program's lines |
| `self.say(value)` | prints a value |
| `self.own_variables(file, hooks=())` | in a `with` block, lines get variables of their own, on top of `file`'s (a def-lang call, a web request); `hooks` are a definition's scope hooks, usually supplied by the engine |
| `self.changed_files()`, `self.reload(path)` | the files saved since they were read; reads one again, in place of its old definitions |
| `self.scope_of(name)` | for a statement's `self["entry"]["scope"]`: the file `use NAME` names, used if it isn't yet; for a library's name, its folder (its `main.def` used, if it has one) |

| Name | Is |
|---|---|
| the argument names | `A0`, `A1`, …: the argument's value, or its words if the definition is `written` |
| `number(value)` | the value as a number, or an error |
| `parse_number(text)` | the text as a number, or `None` |
| `as_text(value)` | the value as text a person reads (what `self.say` prints) |
| `as_code(value)` | the value written as def-lang code, to put in text for `self.run` |
| `Code(text)` | marks text as code, so another language puts it in without escaping it |
| `Line(text, file)` | a line kept to run later, where it was written: its text, and `line.file` (a definition whose arguments are kept, like the flag `later`'s) |
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
| `indented line, but the line above it gave no answer` | the line one level up left `self["answer"]` `None` |
| `indented N spaces, but indent is M` | a width that isn't a whole number of levels |
| `a group's definition lines must have the language and flags of its first line` | definition lines in a row, with different languages or flags |
| `unknown flag 'x'` | a flag that isn't declared |
| ``flag X is written `WORDS`, not `…` `` | a flag written otherwise than its `words` |
| `KIND NAME has no field 'x'` | a field the kind doesn't have |
| `KIND NAME is there already (declared in FILE): to replace it, write replaces …` | an entry another file declared, declared again without `replaces` |
| `KIND NAME was declared in FILE, not in OTHER` | `replaces` names another file than the one that declared it |
| `KIND NAME replaces nothing` | `replaces` on an entry no other file declared before |
| `KIND NAME is built in: it can't be replaced` | `python` or `use`, declared again |
| ``language NAME has no `does` `` | a definition in a language without its `does` |
| `` `does` says the language of its body `` | `does` without `in LANGUAGE` |
| `does in X: there is no language X yet` | `does in` a language that isn't declared (yet) |
| `syntax error in body of 'def …'` | the Python body doesn't compile |
| `'…' never finishes (it keeps matching itself)` | a def whose value is read with the same def again |
| `in '…': ERROR` | a Python error in a body |
| `expected a number, got …` | `number(…)` of something that isn't a number |
| `cannot use 'x'` | no `x.def` and no library `x` |
| `x has no shared variable 'n'` | `use n from x`, but `x` doesn't say `shared n` |
| `` `as` is only for names `` | `as` after a file name, like `use core as c` |
| ``'…' is a phrase of FILE and of OTHER: say which, like `in the scope of FILE, …` `` | two files define the same phrase, and the line is in the scope of neither, or of both |

### E. The Interpreter's Files

| File | Does |
|---|---|
| `__main__.py` | the command: console, run, check, install |
| `execute.py` | reads lines: statements, entries, modifiers, definitions, `use`, variables, calls |
| `kernel.py` | the kernel: the kinds of entry, their fields, the tree's keys |
| `tree.py` | reads a line into a tree: which definition wraps which |
| `definition.py` | a definition: its patterns and its body |
| `values.py` | values, `Code`, `Variables` |
| `check.py` | `def-lang check` |
| `libraries.py` | libraries: finding and installing them |
