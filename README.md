# catalyst-git

Repository plugin for Git-based workflows.

## Continuous auditing architecture

The plugin's continuous-auditing responsibility (see `working-contract.md`)
is implemented as an event-driven pipeline, not a manual polling loop:

```
┌─────────────────────────────────────────────────────────────────┐
│ service.py                                                        │
│   loop every N seconds:                                           │
│     git status --porcelain  →  git hash-object per file            │
│     write FULL snapshot  →  <output_file> (JSON)                  │
│     diff vs previous cycle's snapshot (in-memory)                 │
│     if anything differs → print ONE json line to stdout:          │
│        {"entered": {...}, "updated": {...}, "cleared": [...]}     │
│     (silent when nothing changed)                                 │
└───────────────────────────┬───────────────────────────────────────┘
                            │ stdout line = one event
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ Host monitor (e.g. Claude Code's Monitor tool, run persistently)   │
│   runs service.py directly as its command                          │
│   delivers each stdout line as a discrete notification             │
│   the operator never polls — events arrive on their own schedule   │
└───────────────────────────┬───────────────────────────────────────┘
                            │ notification: diff JSON
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ Orchestrating agent                                                │
│   is this diff self-caused (its own edit/commit moments ago)?      │
│     yes → skip, no audit needed                                    │
│     no  → spawn a short-lived audit sub-agent                      │
└───────────────────────────┬───────────────────────────────────────┘
                            │ self-contained prompt: raw diff +
                            │ "read working-contract.md for your mandate"
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ Audit sub-agent (fresh context, no memory of prior conversation)   │
│   reads this plugin's working-contract.md for its mandate          │
│   investigates the actual paths: git log/diff, catalog pins,       │
│   plugin structure checks, etc. — determines real impact           │
│   writes one report → audits/<UTC-timestamp>-<slug>.md             │
│   returns a short summary to the orchestrating agent when done     │
└─────────────────────────────────────────────────────────────────┘
```

Two file categories matter here:

- **Ephemeral**: the snapshot file `service.py` writes every cycle is just
  its own before/after cache, rebuilt from `git status` on every run.
  Deleting it does nothing — the next cycle regenerates it — and it's not
  meant to live in any repository.
- **Durable**: everything under the root-level `audits/` folder is the
  plugin's actual audit trail — one markdown report per real change-set
  investigated, meant to persist and be committed alongside the project.

The key design choice is the **self-caused-event filter**: the same agent
that edits framework files also receives the change notifications, so it
recognizes its own commits and only spends a sub-agent's budget on changes
it didn't just make itself — otherwise every edit would trigger a redundant
audit of itself.
