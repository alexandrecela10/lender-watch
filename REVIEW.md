# Review instructions

Review a change before it merges. Report findings; never edit, commit or approve. Alexandre approves.

## Passes

Run three passes and tag each finding with its pass:
- **Bugs:** logic errors, broken edge cases, regressions, a test that can't fail.
- **Data and security:** a company name, uploaded list, file path, key, prompt or reply reaching a log, a trace or any outside service; a new outside call that is on by default; a value shown without its filing link. Rules: `.claude/skills/data-handling/SKILL.md`, `.claude/skills/api-and-logging/SKILL.md`.
- **Compliance:** the change does what its spec (`specs/`) and plan (`plans/`) say, and nothing they rule out. Name the spec line or plan step for each finding.

## What Important means here

Important: breaks behaviour, leaks data, breaks a rule in `CLAUDE.md`, or departs from the spec without saying so. Everything else is a nit.

## Cap the nits

Report at most five nits; give the rest as a count.

## Do not report

Formatting and lint (`make lint` covers them), files under `data/` and `outputs/test-evidence/`, and test counts in `CLAUDE.md`.

## Report format

One table, most severe first: Pass | Important or nit | File:line | What is wrong | Why it matters. Then one line: the number of Important findings.
