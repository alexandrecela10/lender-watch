# Intent: the engine, usable inside real Excel and real Claude

Author: Alexandre Cela, writing as the analyst who uses it and the person who runs it. Status: approved 2026-11-20. Alexandre accepted Claude's recommendations on the open questions; see "Decisions".
Source: no opportunity analysis. This follows `outputs/prototypes/analyst-desk/analyst-desk.md` and two independent reviews of it on 11 November 2026.
Evidence: the repo's code, its measured results on public filings, and one small test of Claude's tool choice. Nothing has run inside real Excel or real Claude. No LP or GP analyst has been interviewed. The pain is inferred.

## Problem

- An analyst can use the engine today only by running it from a terminal on their own computer. The Excel formula and the Claude connector are built, but neither has run inside real Excel or real Claude.
- The hosted connector accepts anyone who has its address. It holds the public sample only, and it loses every saved answer when it restarts.
- One product carries five names, and Claude's instructions point at two tools the hosted connector doesn't offer. An analyst can't recognise it, and Claude can be sent to a tool that isn't there.
- The quarter is fixed inside the code. Nobody can ask "as of 31 March", or show next quarter what the tool said this quarter.
- One case: Exabeam appears in filings only as LogRhythm. In the stand-in workbook the analyst sees LogRhythm's loans at 86.2% of the amount owed. In real Excel that result has been seen 0 times (`outputs/prototypes/analyst-desk/analyst-desk.md`).

## Proposed outcome

- **Excel.** I type one formula over my list of company names. I get one row per company: the name lenders use, their value as a share of the amount owed, the change in a quarter, the date of the data, and a filing link. Names the tool isn't sure about stay blank and ask me to confirm.
- **Claude.** I ask about the same list in plain words. Claude calls the same tool and shows the same numbers.
- **One tool, one name.** I see one tool under one product name in both places. Confirming a match is the only other action.
- **My answers stay.** When I confirm a match, it's saved under my sign-in and never asked again.

What should change:
- Recorded runs of the formula inside real Excel: 0 today. Target: at least 1, with the failed-lookup offer shown.
- Recorded runs of Claude calling the connector: 0 today. Target: at least 1 in Claude and 1 in Claude in Excel.
- Same list, Excel against Claude, same numbers: unobserved. Target: 5 of 5 names on the public sample.
- Same list and same date run twice, identical output: unobserved. Target: identical, with the data's date on every row.
- Connector calls answered without a sign-in: all of them today. Target: 0.
- Saved answers that survive a restart of the hosted connector: 0 today. Target: all.
- Product names an analyst meets: 5 today. Target: 1.
- Tools an analyst meets: 7 on the local server and 4 on the hosted one today. Target: 1, plus confirm.
- Tools named in Claude's instructions that the hosted connector lacks: 2 today. Target: 0.
- Claude picks the right tool from the analyst's words: 15 of 15 on 5 prompts today. Target: unobserved on a larger set that includes requests where the tool must stay silent.
- Time to first answer for 50 names: unobserved. Target: measured.
- Analysts who have used it: 0. Target: not set here. A pilot is a separate decision.

What must not get worse:
- Precision 1.000 and recall 0.936 on the answer key.
- Values shown without a filing link: 0.
- The AI judge stays off by default. The hosted public demo keeps making no AI calls.
- An unclear match never shows a number.
- A person's saved answer still beats every automated answer.
- Company names in logs or traces: 0.
- `make test`, `make lint` and `make evals` stay green.

## Affected users and systems

Users: Alexandre now, in real Excel and real Claude. Next, one invited pilot analyst. Later, a client's admin who installs it for a team.
Systems: the engine and its saved answers, the two tool servers, the Excel add-in, Claude's skill for it, the Docker image and deploy scripts, the run records, Microsoft Excel and Claude as hosts.

## Constraints

- Public data only. The hosted version serves public filings. A list under fund confidentiality terms stays on the analyst's computer until a version runs inside the client's own systems.
- Every value keeps its filing link and row.
- All match labels are Claude's. Any score measures agreement with those labels.
- Keys and sign-in secrets stay in `.env`, never printed, logged or committed.
- Agents can't start or change prod. A person approves each change.
- Ask before any public push, merge or publish.
- The engine stays independent of the lender data, so another source can plug in.
- New: every row a tool returns carries the data's date. New: nobody reads or changes another person's saved answers.

## Decisions

Recommended by Claude and accepted by Alexandre on 20 November 2026.

| Question | Decision | Why |
|---|---|---|
| What "production" means this round | One hosted HTTPS address, with sign-in, that an invited analyst can reach from Excel and from Claude. The same container image must also run on a private machine with no change but its settings. | Fastest way to get a real person using it. Building the image to run anywhere keeps the private, confidential route open without building it now. |
| Which lists the hosted version may take | Public or non-confidential lists only, such as companies named on sponsor websites. The sign-in screen and the docs say so. | The list reaches the host, and through Claude it reaches Anthropic. A confidential list needs the private route, which is a later step. |
| Where it's hosted | A small container host with a persistent disk and HTTPS included. The spec picks the provider and cites its price. Alexandre creates the account and pays. | Saved answers must survive a restart. Cost is unobserved until the spec checks it. |
| Sign-in | One sign-in that both Claude's connector and the Excel add-in accept. The spec checks what Claude's custom connectors support today and picks the simplest option that works for both. | Two sign-in systems would double the work and the risk. |
| Microsoft 365 admin rights | Not needed this round. One person adds the add-in by hand. Installing it for a group moves to the next step. | Group install matters for a team, not for proving it works. |
| Saved answers | Kept per person. Each answer records who gave it. Sharing across a team is a later decision. | Nobody can change another person's answer by mistake. A team setting can be added on top. |
| Which quarters | At least the two latest quarters, chosen by date. Every row says which quarter it uses. | Enough to prove "as of" works and that a repeat run gives the same output. |
| Tools | The hosted connector offers one tool to get lender numbers for a list, and one to confirm a match. The local version keeps one extra tool that reads a file on the analyst's computer. | One thing to find. Reading local files only makes sense locally. |
| Matching two of the analyst's own lists, no lender data | Out of scope. | A GP would want it, but nobody has asked yet. |

## Open questions

- **Who is the first pilot analyst?** Alexandre names one by the end of the build. Without one, this round proves it works, not that anyone wants it.
- **Name: settled.** "Lender Watch" for the product, chosen 11 November 2026. The engine's name stays internal.
- **Hosting cost per month:** unobserved until the spec picks a provider.
