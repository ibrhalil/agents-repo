# Notice Board

This board coordinates agents that may work concurrently in the same repository.

It exists for two reasons:

1. Prevent duplicate executions of the same task.
2. Protect unfinished file changes owned by other agents.

This file contains only **currently active work**.

Completed work must not remain here.

---

## Rules

Every agent MUST read this board before starting work.

### 1. Duplicate task protection

Before starting a task, check whether another active agent is already performing the same task.

This is especially important for recurring or cron-triggered tasks.

Example:

- cron interval: 15 minutes
- current execution duration: 20 minutes
- next execution starts while the previous one is still active

The new agent MUST NOT start the same task again.

Instead, it should terminate without making changes because the task is already being handled.

The same rule applies even if the agents were started by different mechanisms.

A task should be considered the same when its purpose and intended result are effectively the same.

When available, use a stable `task_key` to make this explicit.

Example:

```yaml
task_key: nightly-wiki-review
```

Two active entries with the same `task_key` are not allowed.

---

### 2. Register before working

Before making repository changes, add your own entry under `Active Work`.

Example:

```yaml
### agent-01

task_key: nightly-wiki-review
task: Review inbox notes and update the wiki
source: cron
started_at: 2026-09-28T23:00:00+03:00

working_files: []
```

The entry means:

> This task is currently running.

Even if `working_files` is still empty, another agent must not start the same task.

---

### 3. Track only files you actually changed

`working_files` represents files that currently contain unfinished changes belonging to the agent.

Do NOT add:

- files you only read,
- files you inspected,
- files you may edit later.

Add a file when you actually begin changing it.

Example:

```yaml
working_files:
  - wiki/java-agents.md
  - scripts/wiki_review.py
```

If your changes to a file are completely reverted, remove it from the list.

---

### 4. Protect unfinished work

Before modifying a file, check all other active entries.

If the file exists in another agent's `working_files`, do not modify it.

Another agent's `working_files` must also never be:

- staged,
- committed,
- reverted,
- reset,
- deleted,
- cleaned,
- reformatted,
- overwritten.

---

### 5. Commit safety

An agent performing commits must read this board immediately before staging files.

Files listed in another agent's `working_files` are unfinished work and must not be included.

While other agents have active unfinished work, do not use:

```bash
git add .
```

or:

```bash
git add -A
```

Stage only the files that belong to the completed task.

Before committing, verify:

```bash
git diff --cached --name-only
```

If another agent's file was staged accidentally:

```bash
git restore --staged -- path/to/file
```

Do not alter the working-tree contents.

---

### 6. Finish cleanly

When an agent finishes its task, it must remove its entire entry from this board.

Do not leave completed tasks behind.

Do not remove or edit another agent's entry.

If an agent intentionally stops or abandons a task, it should also remove its entry after ensuring its unfinished changes are handled appropriately.

---

### 7. Old entries

Do not assume an entry is stale only because it has been running longer than expected.

Long-running tasks are valid.

Never take over, delete, reset, or overwrite another agent's work based only on elapsed time.

An apparently abandoned entry requires explicit verification before it can be cleaned up.

---

# Active Work

<!--

Example:

### agent-01

task_key: nightly-wiki-review
task: Review inbox notes and update the wiki
source: cron
started_at: 2026-09-28T23:00:00+03:00

working_files:
  - wiki/example.md

-->

_No active work._
