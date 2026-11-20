# Goals: specs/engine-in-excel-and-claude.md

Passing bar: all 9 criteria true.

1. Every target in the intent's "What should change" maps to a row in "Problems this solves" or to an item under "Not tackled".
2. Each problem row has one success metric with a target.
3. Every concern names who raised it, the decision and why.
4. The sign-in section matches Claude's connector docs as read on 2026-11-20: OAuth with automatic registration or a published identity, PKCE, a 401 pointing at protected resource metadata, and Claude's callback address.
5. Every acceptance check is binary and names who runs it: `make test` or Alexandre.
6. Every value returned to a user carries a filing link and row, a quarter, a data version and a rule version.
7. No step lets an agent deploy to the host.
8. The document contains 0 em dashes.
9. The tool-choice eval has must-call and must-not-call cases, a pass target for each, and a stated limit as an API stand-in.
