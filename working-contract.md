# Working Contract: catalyst-git

## Purpose

Provides repository integration for Git-related operations within the catalyst framework.

## Scope

- Repository inspection
- Git workflow support
- Plugin activation lifecycle integration
- Continuous local repository auditing

## Responsibilities

- Maintain a long-running sub-agent that continuously monitors the local Git
  repository for changes.
- Detect repository changes by inspecting `git status --porcelain` and by
  tracking content fingerprints with `git hash-object` for relevant files.
- For each detected change, spawn a short-lived audit sub-agent that invokes
  the framework's `/run-analysis` command to evaluate whether the change
  violates any rule, requirement, or framework constraint defined by the
  active catalyst framework.
- Record audit results in a root-level `audits/` folder, with one report per
  change or change set.
- When the audit identifies a severe or high-impact break, surface the finding
  in any available agent window or notification channel so it is visible to the
  operator immediately.

## Operational loop

1. Start a persistent monitoring sub-agent for the local repository.
2. Poll the repository state using `git status --porcelain` and compare it
   against the previous snapshot.
3. For each new or modified file, compute a content hash using `git hash-object`
   and store the value as part of the change fingerprint.
4. Spawn a focused audit sub-agent for each detected change set and invoke
   `/run-analysis` for that change set.
5. Write the audit result to `audits/` at the repository root.
6. If the audit outcome indicates a major break, post the alert in any available
   agent window.

## Constraints

- The monitoring loop must remain non-blocking and continue running while the
  framework is active.
- Audit results must be deterministic, concise, and based on the current rules
  and requirements loaded by the framework.
- The plugin must not modify repository content outside the audit output path
  unless explicitly requested by the framework.
