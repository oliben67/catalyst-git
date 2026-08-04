# catalyst-git

Repository plugin for Git-based workflows.

## Continuous auditing architecture

The plugin's continuous-auditing responsibility (see `working-contract.md`)
is implemented as an event-driven pipeline, not a manual polling loop.

**`service.py`'s `repo_path` argument must always be the deployed project's
own root directory** — the project this plugin was activated within,
resolved at activation time. Never point it at the catalyst framework's own
repository and never at this plugin's own installation directory under
`plugins/<type>/catalyst-git/`; either mistake monitors the wrong project
entirely and produces audits with no relevance to the deployment.

```mermaid
flowchart TD
    A["<b>service.py</b><br/>loop every N seconds:<br/>git status --porcelain → git hash-object per file<br/>write full snapshot to output_file (JSON)<br/>diff vs previous cycle's snapshot in memory<br/>if anything differs: print one JSON line to stdout<br/>{entered, updated, cleared}<br/>(silent when nothing changed)"]
    A -->|"stdout line = one event"| B["<b>Host monitor</b><br/>e.g. Claude Code's Monitor tool, run persistently<br/>runs service.py directly as its command<br/>delivers each stdout line as a discrete notification<br/>the operator never polls"]
    B -->|"notification: diff JSON"| C{"<b>Orchestrating agent</b><br/>is this diff self-caused?<br/>(its own edit/commit moments ago)"}
    C -->|"yes"| D["Skip — no audit needed"]
    C -->|"no"| E["Spawn a short-lived audit sub-agent"]
    E -->|"self-contained prompt:<br/>raw diff + 'read working-contract.md<br/>for your mandate'"| F["<b>Audit sub-agent</b><br/>fresh context, no memory of prior conversation<br/>reads this plugin's working-contract.md for its mandate<br/>investigates the actual paths: git log/diff,<br/>catalog pins, plugin structure checks, etc."]
    F -->|"writes report"| G["audits/{utc-timestamp}-{slug}.md"]
    F -->|"returns short summary"| C
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
