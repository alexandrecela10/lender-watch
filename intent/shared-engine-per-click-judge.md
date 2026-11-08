# Intent: keep each person's AI judge choice to that person

Author: Alexandre Cela, writing as the person who runs and maintains the engine. Status: draft, awaiting correction by the author.
Source: no opportunity analysis. This follows row 12 of `specs/instrumentation.md`, logged as found, not fixed.
Evidence: the repo's code and one throwaway reproduction on 8 November 2026, not committed. It drove the real app as separate sessions on public names, with a stand-in for the AI judge, no key and network blocked. No name reached Anthropic. No LP analyst has been interviewed. The pain is inferred.

## Problem

- In the version of the review app that runs on your own computer, every open session shares one setting for the AI judge. Each click on "Check lender filings" overwrites it for everyone.
- So someone who leaves the box unticked can still have company names sent to Anthropic, if another session ticked it. The box says nothing leaves the computer when it's off.
- That matters most for a list under fund confidentiality terms, where an analyst leaves the judge off on purpose.
- The reverse also happens: someone who ticks the box can get no judge at all, with no warning on screen.
- One case, from the reproduction: a person ran a 35-name list with the box off, and a second session ran with the box on partway through. The first person's run made 52 judge sends covering 11 of their 12 unclear names, against 0 when run alone.

## Proposed outcome

- A person ticks or leaves the box, then checks their list. They get a result where the judge saw their names only if they ticked it.
- That holds for the whole run, and for the re-check that follows when they answer a "Same company" question. What another session does at any moment has no effect.
- The run record states what that person chose and how many sends their run made, and the two agree.

What should change:
- Sends for a person with the box off, when another session ticks it during their run: 52 in the reproduction, 11 of 12 unclear names. Target: 0.
- Sends caused by a box-off person answering one question, after another session's box-on run has finished: 8 in the reproduction. This needs no overlap in time. Target: 0.
- Sends for a box-on person when another session clicks with the box off during their run: 0 of the 64 made when run alone. Target: 64 of 64.
- Run records marked judge off that made sends: 1 in the reproduction. Target: 0.
- How often two sessions are open with a key present in real use: unobserved. The run records on Alexandre's computer hold 5 runs since 7 November, none from the app, so there's no sign it has happened and no proof it hasn't.
- Cost of unwanted sends: unobserved. The stand-in judge charges nothing.
- Effect on match answers: unobserved. The stand-in judge always replied "unsure".

What must not get worse:
- The AI judge stays off by default.
- The hosted public demo keeps making no AI calls. It has no box and always runs with the judge off, so this fault doesn't reach it.
- A person's saved answer still beats every automated answer.
- Precision 1.000 and recall 0.936 on the answer key, as measured on 2 November.
- Filings load once, not per click. First visit today takes about a minute, per the app's own loading message. Time per click: unobserved.

## Affected users and systems

Users: Alexandre now, with two tabs open on his own computer. Later, an LP analyst running the app locally, and anyone sharing one running copy on a team server. Visitors to the hosted demo aren't affected.
Systems: the review app in `app/review.py`, the engine in `erm/api.py`, the run records from `erm/telemetry.py`, the app tests in `tests/test_app.py`, and the Anthropic API. The command line and the tool server set the judge once at start, so they aren't part of this fault.

## Constraints

- Nothing goes to a third party unless the person who owns that list turned the judge on.
- Public data only in tests and fixtures. A test of this uses a stand-in judge and sends nothing.
- All labels are Claude's. Any matching score here measures agreement with Claude's labels, not truth checked by a person.
- Every fact keeps its filing link and row, and no uncited value is shown.
- Keys stay in `.env`, never printed, logged or committed.
- This intent covers the judge choice only. Other state shared between local sessions, such as saved answers, is out of scope.

## Open questions

- Does anyone need to share one running copy of the app? Unobserved. If nobody does, the two-tab case on one computer is the whole exposure, and a warning might do. If a team shares one, it has to be fixed before they use it.
- Should saved answers also be kept per person on a shared copy? Today they're shared, on purpose or by accident. If a team shares one copy, this needs its own intent.
- If a person changes the box after their run but before answering a question, which choice applies? The last click on "Check lender filings", or the box as it stands? The safer reading is that an unticked box always means no send.
- Has a name already been sent this way? Unobserved before 7 November, when run records began.
