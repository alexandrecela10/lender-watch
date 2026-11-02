# Build decisions

Newest last. Product decisions live in `outputs/decisions/`.

| Date | Decision | Why | Not chosen |
|---|---|---|---|
| 2026-11-02 | Read SEC's monthly BDC data sets, not filing HTML | Holdings are already tagged, and each row keeps a filing link | Parsing each filing |
| 2026-11-02 | Treat SEC's "Initial fair value of Investment" column as fair value | Checked against the GCRED 30 June 2026 filing: KnowBe4 13,851 par, 10,873 fair value | Assuming from the label alone (the original mistake) |
| 2026-11-02 | Strip legal words only from the end of a name | The earlier cleaner turned "Point C" into "point", which matched "Basis Point" | Removing legal words anywhere |
| 2026-11-02 | Compare loan by loan, never lender averages | Blackstone holds KnowBe4 at 100.2 and 78.5; its average of 93.4 hid both | Lender-level averages |
| 2026-11-02 | Own Fellegi-Sunter in about 60 lines, not Splink | One side has only a name and a loose sector, and we have labels; Splink fits two rich tables without labels | Splink |
| 2026-11-02 | model2vec for embeddings | `onnxruntime`, and so `fastembed`, has no current build for this Intel Mac | fastembed, sentence-transformers |
| 2026-11-02 | Claude Opus 5.5 at low effort for the judge; server-side refusal fallback on live calls | Default model; the batch evaluation can't use the fallback, so a refusal there counts as "unsure" | A cheaper model: PM's call, not tested |
| 2026-11-02 | Answer key: two independent Claude labellers, blind to method, disagreements reviewed, then a person spot-checks | No person available yet; labels aren't ground truth until the spot check | Treating Claude's labels as human labels (the earlier wording was wrong) |
| 2026-11-02 | Flag on the size-weighted average, keep loan-level detail | The lowest-position rule flagged 11 companies whose debt averages 90% or more, such as Bullhorn on one $68k position | Lowest single position |
| 2026-11-02 | Exclude rows with cost below 80% of principal | Canadian loans read about 72% of par, and filings carry no currency tag | Parsing currency from text, which most rows don't state |
| 2026-11-02 | AI judge off by default | It sends names to Anthropic; an LP list may be under fund confidentiality terms | On by default, which needs 11% rather than 45% of names reviewed |
