# Programmable kernel and cycle hooks

## Status and decisions

Design and implementation, 2026-11-26. All six cycles are implemented. Hook bodies
are entries' `hook CYCLE PHASE in LANGUAGE` fields. `self["cycle"]` is in the kernel,
and hook bodies are `Definition` objects, so they travel in compiled builds. Declaring
an entry never installs behavior by itself: its hooks become active only when the entry
is written in front of the line they act on, or on a definition that uses the entry.

Decisions already made:

- Private engine fields are allowed **only in Python bodies of entry declarations** —
  `modifier`, `statement`, `flag`, and `language`. Bodies of ordinary `python ...`
  definitions do not get private access. That is the primitive layer, not every def.
- A new modifier/flag should be able to add both **behavior hooks** and **new
  `self[...]` data keys**, not merely choose an existing option.
- The first hook cycles are: definition call, file/import read, line classification,
  and variable/scope lifetime.
- `self["cycle"]["file"]` and `self["cycle"]["owner"]` are different fields and both
  stay: `file` is what the cycle is about; `owner` is which declaration supplied the
  running hook. `self["entry"]` cannot substitute for `owner`.
- No private engine fields are exposed as new API in this design. `say` stays as
  `python say A0 / self.say(A0)`.
- Hook state is namespaced by an engine-supplied owner identity in `file/name` form,
  for example `local_time/timed`. A duplicate entry name from another file is an error
  unless that file declares `replaces FILE`.
- IntelliSense for `self["cycle"]["state"]["started"]` comes from two sources: the
  kernel schema for `cycle` and `state`, and a scan of the modifier's own body for the
  key inside `state`. No new declaration field is needed.
- This document comes before implementation.

## Goal

Make the kernel a small, documented platform that developers can extend from `.def`
libraries:

1. **Fewer reserved names.** Words such as `say`, `run`, `later`, and `scope` should
   be library definitions, not special cases in Python.
2. **Real capabilities.** A modifier/flag/statement should be able to register new
   behavior at defined points in the interpreter's lifecycle.
3. **One state tree.** Everything a body can see is in `self[...]` or a documented
   method. The shape of that tree, when each key exists, and what can change it are
   written down.
4. **Cycles with injection points.** Each major operation has a start, end, and error
   phase; library code can inject before/after behavior without forking the engine.

## Non-goals

- Rewriting the parser or evaluator in a second implementation.
- Removing all Python from the project. The engine still owns parsing, matching,
  definition dispatch, and hook execution.
- Making every current word changeable immediately. This design creates the path;
  migration happens in phases.
- Changing compiled-run architecture. Hooks must fit the existing snapshot/artifact
  model.

## Current model

### Reserved syntax

Hard-coded in `execute.py`:

- `use`, plus `from` and `as` inside `use A as B from C`.
- `language`, `flag`, `modifier`, `statement`.
- Entry fields: `does in`, `words`, `editor`, `reading`, `replaces`.
- `python` as the only built-in language.
- `A0`, `A1`, … as the default argument prefix; changeable with `argument is X`.

Defined in `deflang-lib`, so replaceable:

- languages: `def`, `html`, `css`, `javascript`
- flags: `written`, `regex`, `later`
- modifiers: `shared`, `internal`, `verbatim`
- statements: `comment`, `argument`, `indent`, `error`, `echo`, `scope`, `scoped`

### `self[...]` keys

Current keys:

| Key | Kind | Current programmability |
|---|---|---|
| `language`, `flag`, `modifier`, `statement` | entry registries | add entries by declaration |
| `aliases` | mutable data | alias lines mutate it |
| `files`, `shared`, `store` | mutable data | directly programmable |
| `definitions` | mutable list | definitions append/reload in place |
| `variables` | context view | directly mutable in a body |
| `file`, `program`, `mode`, `entry` | context views | read-only in practice |
| `answer` | control value | the only directly settable key |

The problem is not that these keys are fixed; it is that there is no general way to
**add a new kind of behavior** through them.

### Engine methods

Public methods on `Execute` that behave like primitives:

| Method | Current library word |
|---|---|
| `say(value)` | `say A0` |
| `run(line)` | used by `set`, `if`, loops, checks |
| `run_lines(text)` | `run A0` |
| `changed_files()`, `reload(path)` | `read the changed files again` |
| `scope_of(name)` | `set scope to A0` |
| `own_variables(file)` | `later`, web server |
| `display_values(names)` | def body runner |
| `call(definition, args, text)` | every def call |
| `in_scope(file)`, `apply_aliases(text)` | parser/evaluator internals |
| `keys()`, `clean()` | engine introspection/reset |

### Python-body globals

Python bodies get fixed helper names:

`self`, `a`, `A0`, `A1`, …, `number`, `parse_number`, `as_code`, `as_text`, `Code`,
`Line`, `DefException`, and Python builtins.

These are the low-level surface. They are not language keywords, but they are part of
the primitive API.

## Problem

### Presets are not capabilities

`modifier shared` used to say:

```def
modifier shared
    does in def
        set name to shared
```

That was a preset over an option the kernel already understood, and `shared` was a
reserved word in `set`. It now declares a `define` hook instead, so the capability is
visible at the line that applies it and no new `set` word is needed. A modifier can say
what should happen when a definition is created, called, reads arguments, finishes, or
fails.

### Missing lifecycle injection

The interpreter already has natural cycles: reading a file, reading a line, creating
a definition, calling a definition, running a body, entering a scope. They are implicit
in Python control flow. Library code cannot subscribe to their start/end, cannot see a
stable cycle state, and cannot register behavior without editing `execute.py`.

### Private primitives

`self._output` is private, and the decision is not to expose it. Printing stays behind
the public method:

```def
python say A0
    self.say(A0)
```

The boundary: private engine fields may be used inside the bodies of **entry
declarations** (`modifier`, `statement`, `flag`, `language`) when a primitive is needed,
but no private field is promoted to documented API by this design. Ordinary
definitions use public methods. Nothing in the `say` path needs private access.

## Design principles

1. **Kernel owns state and cycles; libraries own names.** The kernel keeps the tree,
   the parser, the evaluator, and the hook dispatcher. Words and features live in
   `.def` files.
2. **Data keys are programmable; methods are primitives.** `self["files"]` is data.
   `self.run(...)` is an action. A library can add data keys; moving actions into a
   library means wrapping a thin primitive.
3. **Every cycle has three phases:** `start`, `end`, `error`. Hooks in `start` run
   before the operation, `end` after success, `error` on failure. Cleanup is always
   handled by the engine.
4. **Hooks are Definitions.** They are written in def-lang or Python, stored like any
   other definition, and included in the compiled language snapshot. No closures in
   artifacts.
5. **No private API is exposed.** Only the bodies of `modifier`, `statement`, `flag`,
   and `language` entries may touch private engine fields, and only when a new
   primitive truly needs one. Those fields are internal, not documented API;
   ordinary definitions use public methods such as `self.say`.
6. **Additive and versioned.** Adding a hook field or a `self[...]` key must not
   change the meaning of existing libraries.

## Proposed kernel structure

### Data keys

Add one new public key:

- `self["cycle"]`: read-only state for the cycle currently running.

There is deliberately no global hook registry. A hook lives on the entry that declared
it, or on the definition it was applied to, so activation is visible at the line that
causes it. Keep existing keys. Document for each key:

- when it exists,
- who may write it,
- whether it is per-file, per-line, per-call, or global,
- whether it survives into the compiled artifact.

Allow libraries to add namespaced data under `self["store"]`, for example:

```python
self["store"]["timed"]["calls"] += 1
```

`store` is the safe place for new `self[...]` keys without changing the kernel.

### Cycle keys

`self["cycle"]` is a read-only view:

```python
{
    "id": 17,             # unique id of this cycle instance
    "name": "call",       # file | line | define | call | body | scope
    "phase": "start",     # start | body | end | error
    "text": "double 21",  # the source being acted on, when there is one
    "definition": None,   # for call/define/body cycles
    "file": None,         # the file whose cycle this is: what it is about
    "owner": None,        # the declaration whose hook is running, e.g. "local_time/timed"
    "state": {},          # defaultdict(dict): scratch space, one dict per owner
    "error": None,        # set in the error phase
    "depth": 2,           # nesting of this cycle name; entry `does` calls don't count
}
```

`state` is mutable; every other field is read-only. This gives hooks a place to pass
values from `start` to `end` without writing globals.

`file` and `owner` are not the same thing and neither replaces the other:

- `file` answers *which source file this cycle is about*: the file being imported, or
  the file where the called definition was made. It is used by errors, scopes, and
  compiled replay.
- `owner` answers *which declaration supplied the hook now running*. It is derived
  from the entry's file and name, for example `local_time/timed`, and is supplied by
  the engine rather than written by the library author.

`self["entry"]` cannot stand in for `owner`: it is the entry whose `does` body is
running. A modifier's `call` hook runs around the *target definition's* body, so
`self["entry"]` points at that context, not at the modifier. The exception is a
modifier in front of a name: its `define` hook runs with `self["entry"]["name"]` set to
that name, so `shared` can register it without a reserved word.

### Where hooks live

There is no global registry. A `Hook` record has a `cycle`, a `phase`, its `definition`
(the Python/def body to run) and the engine-supplied `owner`. Hooks live in two places:

- `entry.hooks`: what the entry declared. Declaring it changes nothing else.
- `Definition.hooks`: what was applied to a definition. These hooks are versioned with
  the language snapshot and the compiled artifact.

Order is the order in which the hooks were applied. There is no `enabled` flag: a hook
is simply not applied, or it is replaced with the entry.

### Entry hooks

Every entry kind can declare hooks with a repeatable field:

```def
hook CYCLE PHASE in LANGUAGE
    ...body...
```

Only the word `hook` is new. `CYCLE` and `PHASE` are fixed strings; `in LANGUAGE` keeps
the existing `does in LANGUAGE` shape.

A modifier only acts when it is written in front of a line:

```def
watched use part          # `file` hooks wrap this import
watched say 21            # `line` hooks wrap this line
watched def double A0     # `define` hook wraps its creation; the rest live on the def
    A0 * 2
```

For a definition line, the `define` hooks run around its creation; `call`, `body`,
`line` and `scope` hooks are stored on the new `Definition` and run when it runs (its
body's lines and its `own_variables` included). Flags and languages work the same way:
writing `[marked]` or `python` on a definition applies that entry's hooks to it.
A statement's own hooks act on its `does`, which it declares right next to them.

### IntelliSense for cycle state

`self["cycle"]["state"]["started"]` has two kinds of key:

- `cycle` and `state` are kernel-owned. The editor knows them from the documented cycle
  schema, the same way it already knows entry fields such as `words` and `reading`.
- `started` is arbitrary. It is written and read inside one modifier's own body, so the
  editor can collect the keys used under `["state"]` in that body and offer or mark
  them locally.

No new declaration field is needed for scratch keys. Adding one would be another
reserved word, which works against the goal of having as few as possible. Namespacing
by owner is the guard against collision, not a schema requirement:
`self["cycle"]["state"][timed]["started"]`, where `timed` is a body-local variable
holding `self["cycle"]["owner"]`.

### Duplicate names and collisions

Two declarations with the same name from different files clobber each other if the
second one is allowed to overwrite the first. The kernel already has `replaces FILE`
for an explicit takeover. Rule: a duplicate name from another file is a read-time
error unless the new declaration says `replaces FILE`; then only the replacing entry
contributes hooks, so old and new hooks never mix.

A literal owner name is not a safe namespace on its own — two same-named modifiers
would both use `"timed"`. That is why `owner` is engine-supplied from the entry's
identity, and why a duplicate without `replaces` is an error.

Example with a collision attempt:

```def
// time.def
modifier timed
    hook call start in python
        timed = self["cycle"]["owner"]
        self["cycle"]["state"][timed]["started"] = "now"
    hook call end in python
        timed = self["cycle"]["owner"]
        self.say("timed saw " + self["cycle"]["state"][timed]["started"])
```

```def
// local_time.def
use time
modifier timed                          // error: duplicates time/timed
    hook call start in python
        timed = self["cycle"]["owner"]
        self["cycle"]["state"][timed]["started"] = "local now"
    hook call end in python
        timed = self["cycle"]["owner"]
        self.say("local timed saw " + self["cycle"]["state"][timed]["started"])

timed def work A0
    A0 * 2
```

Reading stops at the second `modifier timed`; `work` is never defined. Adding
`replaces time` makes the local entry the winner: `say work 21` then prints
`local timed saw local now` and `42`. The exact current behaviour of duplicate names
must be verified in `_import` before this rule is enforced; the `replaces` field
suggests takeover was meant to be explicit.

## Cycles

Each cycle is implemented as one context manager in `Execute`, around existing code:

```python
with self.cycle("call", text=text, definition=definition, arguments=arguments):
    ...
```

The context manager:

1. pushes a new `self["cycle"]`,
2. runs `start` hooks,
3. yields to the engine,
4. runs `end` hooks on success or `error` hooks on failure,
5. pops the cycle state.

### Where the cycles appear

A cycle starts only when something is listening. With no hooks it is a plain `yield`,
so the hot paths pay almost nothing for cycles they do not use.

```def
watched use file/io            ← FILE/IMPORT read, because of the prefix

python double A0               ← no cycle: no hook was applied to this line
    A0 * 2

timed def triple A0            ← DEFINITION CREATION from timed's define hook;
                                  its other hooks go on this definition
    double 21                  ← LINE, then DEFINITION CALL, then BODY

set x to 21                    ← no line cycle unless the line is prefixed

traced say triple x            ← LINE, then CALL, BODY and the def's SCOPE
```

A `call` hook fires for definitions the modifier was written on, not for every
definition. A `define` hook fires only for the definition line it prefixes. A `line`
hook fires on the prefixed line and on lines inside a definition it was applied to;
declarations and comments are not line cycles. A hook's own lines never start another
cycle, which is why the re-entrancy guard matters.

### File/import cycle

Wraps the actual read of a used file (`_import` / `_read`, also `reload`).

State: `file` (the path), `text` (the name written at `use`), `place` (its place in
`self["files"]`).

Uses: module setup, teardown, per-file data, tracing which library introduced a word.
A compiled build has already read its files, so this cycle fires when the file is read,
not again when recorded lines are replayed.

### Line/read cycle

Wraps a statement's `does` and an expression's evaluation, as each runs. Statements
that only build the language while `check` or `compile` reads do not start it.

State: `text`, `level`, `file`, `kind` (`statement` or `expression`).

Uses: tracing and alternate behavior for lines that run. A def body's lines run through
the same path, so they are line cycles too. Hooks must not re-trigger themselves; see
Behaviour rules.

### Definition creation cycle

Wraps `_define`.

State: `pattern`, `language`, `flags`, `file`, and `definition` from its `end` phase on.

Uses: modifiers that register metadata or attach hooks to the new definition. A build
runs these hooks while reading, so what they change is already in the artifact.

### Definition call cycle

Wraps `call`, around `_call`.

State: `definition`, `arguments`, `text`.

Uses: logging, timing, caching, memoization, argument validation, wrapping return
values.

### Body cycle

Wraps the body run inside a definition call, for Python and for other languages.

State: `definition`, `text`, `body`, `file`, `variables`.

Uses: tracing and wrapping a body without wrapping the whole call. Its hooks attach to
the definition, like `call` hooks.

### Variable/scope cycle

Wraps a statement's scope and `own_variables` (the variables a def-lang body gets).

State: `text`, `file`, `variables`, and `scope` for a statement's list of files.

Uses: request-local state, transaction-like setup, temporary bindings, scope-aware
debugging. Its hooks come from a modifier on the statement line, or from a definition
whose body gets `own_variables`.

### Error and cleanup phases

`error` hooks run only when the engine operation raises. `end` hooks do not run on
error. The engine always restores variables, answers, entries, and scopes in its
`finally` block.

## Syntax sketch

### Declaring a hook

```def
modifier timed
    hook call start in python
        timed = self["cycle"]["owner"]
        self["cycle"]["state"][timed]["started"] = time.perf_counter()
    hook call end in python
        timed = self["cycle"]["owner"]
        TOOK = time.perf_counter() - self["cycle"]["state"][timed]["started"]
        self.say(self["cycle"]["text"] + " took " + as_text(TOOK))
```

Use it as a normal modifier:

```def
timed def slow A0
    A0 + A0
```

`timed` is a body-local variable holding the engine-supplied owner identity. The
editor can mark it as local to that body; `self["cycle"]` and `self["cycle"]["owner"]`
come from the kernel schema.

### Attaching a modifier capability

The modifier declares two hook Definitions. Applying `timed` to a def copies those
hooks onto that definition. `shared` and `internal` use `define` hooks for the same
reason: a modifier owns its behavior, and the kernel has no reserved `set` word for
what it does.

### More state examples

Two modifiers, same key name, attached to one definition:

```def
modifier timed
    hook call start in python
        timed = self["cycle"]["owner"]
        self["cycle"]["state"][timed]["started"] = "now"
    hook call end in python
        timed = self["cycle"]["owner"]
        self.say("timed saw " + self["cycle"]["state"][timed]["started"])

modifier counted
    hook call start in python
        counted = self["cycle"]["owner"]
        self["cycle"]["state"][counted]["started"] = "now"
    hook call end in python
        counted = self["cycle"]["owner"]
        self.say("counted saw " + self["cycle"]["state"][counted]["started"])

timed counted def work A0
    A0 * 2

say work 21
```

Both `started` keys survive; the output is `timed saw now`, `counted saw now`, then
`42`.

Start writes, error reads — same owner, different phase:

```def
modifier guarded
    hook call start in python
        guarded = self["cycle"]["owner"]
        self["cycle"]["state"][guarded]["began"] = self["cycle"]["depth"]
    hook call error in python
        guarded = self["cycle"]["owner"]
        E = self["cycle"]["error"]
        self.say("failed at depth " + as_text(self["cycle"]["state"][guarded]["began"])
                 + ": " + as_text(E))
```

Nested calls — each invocation gets its own state:

```def
modifier traced
    hook call start in python
        traced = self["cycle"]["owner"]
        D = self["cycle"]["depth"]
        self["cycle"]["state"][traced]["enter"] = D
        self.say("enter " + self["cycle"]["text"] + " at " + as_text(D))
    hook call end in python
        traced = self["cycle"]["owner"]
        self.say("leave " + self["cycle"]["text"] + " from "
                 + as_text(self["cycle"]["state"][traced]["enter"]))

traced def twice A0
    A0 + A0

traced def four_times A0
    twice twice A0

say four_times 1
```

The `enter`/`leave` pairs nest (`four_times` → `twice twice` → `twice`) and never
overwrite each other.

Different cycles have separate state; use `store` to cross them:

```def
modifier logged
    hook line start in python
        logged = self["cycle"]["owner"]
        self["cycle"]["state"][logged]["line"] = self["cycle"]["text"]
    hook line end in python
        logged = self["cycle"]["owner"]
        self.say("read " + self["cycle"]["state"][logged]["line"])

    hook call start in python
        // ["line"] belongs to a line cycle; a call cycle cannot see it
        self["store"]["logged"]["last_call"] = self["cycle"]["text"]
```

### Reading cycle state

```def
python show the cycle
    self.say(self["cycle"]["name"] + " / " + self["cycle"]["phase"])
```

Inside a hook, `self["cycle"]` tells the hook what is happening. Outside a hook, it is
the innermost active cycle, or `None`.

## Behaviour rules

### Ordering

- `start` hooks run in the order they were applied: line hooks first, then the
  definition's own hooks.
- `end` and `error` hooks run in reverse apply order.
- Nested cycles run their own hooks; a nested `call` does not replace the outer
  `file` cycle state, it nests inside it.
- The same hook can run more than once if its definition is called more than once.
- With no applied hook, a cycle is skipped: hot paths check only the hooks passed for
  that line and the definition's own hooks before paying for the context manager.

### Nesting

Hooks are body lines too. While running hooks, the engine sets an internal
`_in_hook` counter, so a hook that runs def-lang lines or calls another def starts no
new cycle. That prevents a hook from recursing into itself. A def called by a hook is
otherwise run normally; it just has no hooks of its own during that call.

### Failure

- A hook error is a language error and stops the operation.
- Error hooks receive the original error in `self["cycle"]["error"]`.
- Hooks cannot suppress an error in the first design; that can be added later as a
  separate capability.

### Snapshots and compiled builds

Hooks are `Definition` objects, so they are already covered by the language snapshot
work. They are stored in `entry.hooks` and `Definition.hooks`, both of which travel in
a compiled build. Loading a build restores every hook body's modes and rebuilds its
Python function lazily. No Python lambda or closure is stored in an artifact. A runtime
line is recorded with its modifier prefix, so the hooks applied at that line are applied
again on replay. `call`, `body`, `line` and `scope` hooks run on replayed runtime lines;
`file` and `define` hooks already ran while the build was made. Alias lines a library
ran then are in the artifact's aliases, so they are no longer replayed as runtime lines.

## Migration plan

### Thin primitives

Keep a small set of public engine methods, but make them thin and documented:

- output: `self.say` (backed internally by `self._output` / `print`)
- parsing and line execution: `self.run`
- body block execution: `self.run_lines`
- definition dispatch: `self.call`
- variable context: `self.own_variables`
- hook dispatch: `self.cycle`

`self._file_times` and `self._import_files` stay internal; library code reaches file
state through `self[...]` keys, not private fields.

### Library words

Move names into `.def` libraries:

- `say` → keep `python say A0` using `self.say(A0)`; no private access needed.
- `run` → library word using `self.run_lines`.
- `read the changed files again` → already library-based; keep it.
- `later` → already library-based; keep it.
- `in the scope of` → already library-based; keep it.

The goal is not to eliminate these actions, only to eliminate their special status as
built-in words where possible.

### Example: `say`

```def
// console/main.def
python say A0
    self.say(A0)
```

Resolved: no private fields are exposed, so `self.say` stays as the primitive behind
the language word. `say` remains a normal library definition, not an entry or a
special case in Python.

### Example: a real modifier

A first integration test should be a `modifier traced`:

```def
modifier traced
    hook call start in python
        traced = self["cycle"]["owner"]
        self["cycle"]["state"][traced]["depth"] = self["cycle"]["depth"]
        self.say("call " + self["cycle"]["text"])
    hook call end in python
        self.say("done " + self["cycle"]["text"])

traced def double A0
    A0 * 2
```

Expected output around a call: `call double 21`, then `done double 21`, then `42`.
This proves that a modifier adds behavior rather than selecting an existing option.

## Verification

1. `tests/test_hooks.py` covers all six cycles, order, nesting, error phase, owner
   namespacing, `replaces`, and the re-entrancy guard.
2. Differential tests compare interpreted and compiled hook output for `call`, `body`
   and `scope`; `file` and `define` hooks run when the build is made, so their timing
   is deliberately different at replay.
3. `tests/parse_corpus.py`: the existing 2,257 lines still match the baseline.
4. The full sample suite passes (226 tests).
5. Benchmarks: with no hooks, cycles are skipped and the interpreter is faster than
   the pre-hook baseline; the compiled-run speedup is unchanged.

## Open questions

- Is `hook` the right single new field word, or should hooks reuse `does` with a
  `when`/`on` phrase?
- Should definition-local hooks be copied when a modifier is applied, or referenced
  so later edits to the modifier affect existing definitions?
- Should `end` also run on error, in addition to `error` hooks?
- Should hooks be able to change arguments before the body, or only observe them?
- Which private fields, if any, will entry bodies need as new capabilities are added?
  None are exposed by this design.
- Resolved: `say` stays on `self.say`; `owner` is `file/name`.
