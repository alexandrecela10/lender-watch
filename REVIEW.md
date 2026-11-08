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

Write for a reader who does not read code. Plain words, one idea per sentence, about 20 words at most. No tables, no em dashes.

1. First line, in bold, says what to do: `**Fix 2 things before merging.**` or `**Nothing to fix before merging.**`
2. Then a numbered list of Important findings, most severe first. Each has:
   - One bold sentence: what is wrong, and what goes wrong for the product or its users because of it.
   - `Fix:` one sentence.
   - `Where:` file:line, the pass, and the spec line or plan step for compliance findings.
3. Then the nits, one short line each, inside `<details><summary>Small points (N)</summary>`.
4. Last line: anything you could not check, and why. Leave it out if there is nothing.

Before reporting a missing file, check the pull request's base branch. In a stack, a file in an earlier open pull request is not missing.
