# Programmable kernel and cycle hooks

## Status and decisions

Draft design, 2026-11-26. The `call` cycle is implemented; the other cycles are still
design. Hook bodies are entries' `hook CYCLE PHASE in LANGUAGE` fields. `self["cycle"]`
and the global `self["hooks"]` registry are in the kernel, and hook bodies are
`Definition` objects, so they travel in compiled builds.

Decisions already made:

- Private engine fields are allowed **only in Python bodies of entry declarations** —
  `modifier`, `statement`, `flag`, and `language`. Bodies of ordinary `python ...`
  definitions do not get private access. That is the primitive layer, not every def.
- A new modifier/flag should be able to add both **behavior hooks** and **new
  `self[...]` data keys**, not merely choose an existing option.
- The first hook cycles are: definition call, file/import read, line classification,
  and variable/scope lifetime.
- `self["cycle"]["file"]` and `self["cycle"]["owner"]` are different fields and both
  stay: `file` is what the cycle is about; `owner` is which declaration installed the
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

`modifier shared` currently says:

```def
modifier shared
    does in def
        set name to shared
```

That is a preset over an option the kernel already understands. It does not teach the
language anything new. A real modifier capability would be able to say what should
happen when a definition is created, called, reads arguments, finishes, or fails.

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

Add two new public keys:

- `self["cycle"]`: read-only state for the cycle currently running.
- `self["hooks"]`: the hook registry.

Keep existing keys. Document for each key:

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
- `owner` answers *which declaration installed the hook now running*. It is derived
  from the entry's file and name, for example `local_time/timed`, and is supplied by
  the engine rather than written by the library author.

`self["entry"]` cannot stand in for `owner`: it is the entry whose `does` body is
running. A modifier's `call` hook runs around the *target definition's* body, so
`self["entry"]` points at that context, not at the modifier.

### Hook registry

`self["hooks"]` is a registry of hooks:

```python
kernel["hooks"] = {
    "global": {
        "call": {"start": [], "end": [], "error": []},
        "file": {"start": [], "end": [], "error": []},
        # ...
    },
    "definitions": [],  # hooks attached to particular definitions
}
```

A hook record has:

- `cycle`: `file`, `line`, `define`, `call`, `body`, or `scope`
- `phase`: `start`, `end`, or `error`
- `definition`: the Python/def body to run
- `owner`: the entry or definition that installed it
- `order`: install order
- `enabled`: bool

Definition-local hooks belong to `Definition.hooks`, so they are versioned with the
language snapshot and the compiled artifact.

### Entry hooks

Every entry kind can declare hooks with a new repeatable field:

```def
hook CYCLE PHASE in LANGUAGE
    ...body...
```

Only the word `hook` is new. `CYCLE` and `PHASE` are fixed strings from the registry;
`in LANGUAGE` keeps the existing `does in LANGUAGE` shape.

A modifier's hooks attach to the definition it modifies. A flag's hooks attach
similarly. A statement's hooks are active while its line runs. A language's hooks
attach to definitions written in that language.

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

Several lines trigger two cycles: first classification, then the operation the line
starts.

```def
use file/io                    ← line classification, then FILE/IMPORT read
use flag/written               ← line classification, then FILE/IMPORT read

// a note                      ← line classification (comment)

python double A0               ← line classification, then DEFINITION CREATION
    A0 * 2                     ← line classification (body line)

modifier traced                ← line classification (entry declaration)
    does in python             ← line classification (entry field)
        ...                    ← line classification (hook body, read at setup)

statement shout                ← line classification (entry declaration)
    words shout A0             ← line classification; runs while reading
    does in def
        say A0

traced def triple A0           ← line classification, then DEFINITION CREATION
    double 21                  ← DEFINITION CALL (nested inside triple's body)
    A0 + A0 + A0

set x to 21                    ← line classification (statement/expression)

say triple x                   ← line classification, then DEFINITION CALL

set scope to file/io           ← line classification, then VARIABLE/SCOPE
    triple x                   ← call cycle again, inside that file's variables

in the scope of file/io        ← line classification, then VARIABLE/SCOPE
    say triple x
```

A `call` hook fires at `double 21` and `say triple x`, not at the definition lines. A
`define` hook fires at `python double A0` and `traced def triple A0`. A `line` hook
fires at every line, including the hooks' own bodies — which is why the re-entrancy
guard matters.

### File/import cycle

Wraps `_import` / `_read`.

State: `file`, `text`, `place`.

Uses: module setup, teardown, per-file data, tracing which library introduced a word.

### Line/read cycle

Wraps `_run_at` / `_line`.

State: `text`, `level`, `file`, `kind` (`statement`, `entry`, `definition`, `modifier`,
`expression`, `comment`, `empty`).

Uses: tracing, alternate readers, read-time validation. Hooks must not re-trigger
themselves; see Behaviour rules.

### Definition creation cycle

Wraps `_define`.

State: `pattern`, `language`, `flags`, `file`.

Uses: modifiers that rewrite patterns, register metadata, or attach hooks to the new
definition.

### Definition call cycle

Wraps `call`.

State: `definition`, `arguments`, `text`.

Uses: logging, timing, caching, memoization, argument validation, wrapping return
values. This is the first cycle to implement because it has the clearest boundary.

### Variable/scope cycle

Wraps `run_lines` and `own_variables`.

State: `definition`, `text`, `file`, `variables`.

Uses: request-local state, transaction-like setup, temporary bindings, scope-aware
debugging.

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

The modifier declaration installs two hook Definitions. Applying `timed` to a def
copies those hooks onto that definition. `shared` stays as it is — a preset modifier —
but it is no longer the only kind of modifier possible.

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

- `start` hooks run in install order, global hooks before definition-local hooks.
- `end` and `error` hooks run in reverse install order.
- Nested cycles run their own hooks; a nested `call` does not replace the outer
  `file` cycle state, it nests inside it.
- The same hook can run more than once if its definition is called more than once.

### Nesting

Hooks are body lines too. While running hooks, the engine sets an internal
`_in_hook` counter, so a hook that runs def-lang lines or calls another def does not
invoke call hooks again. That prevents a hook from recursing into itself. A def called
by a hook is otherwise run normally; it just has no hooks of its own during that call.

### Failure

- A hook error is a language error and stops the operation.
- Error hooks receive the original error in `self["cycle"]["error"]`.
- Hooks cannot suppress an error in the first design; that can be added later as a
  separate capability.

### Snapshots and compiled builds

Hooks are `Definition` objects, so they are already covered by the language snapshot
work. `Definition` gains a `hooks` tuple/list. Compiled artifacts pickle the hooks,
restore their hook modes, and rebuild parsed/cached bodies lazily. No Python lambda or
closure may be stored in an artifact.

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

1. Unit tests for hook order, nesting, error phase, and re-entrancy guard.
2. Differential tests: interpreted vs compiled runs produce the same hook output.
3. Corpus test: existing 2,257 lines remain unchanged unless syntax is intentionally
   added.
4. A sample-library test using `traced` and one data-key modifier.
5. Benchmarks: hook dispatch must be cheap when no hooks are registered; call cycles
   should not regress the compiled-run speedup.

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
