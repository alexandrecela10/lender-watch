# Lender Watch

**One line:** see when lenders start doubting the companies you've invested in, with the public filing as proof.

**Description:**

Investors in private equity funds rarely hear about the companies they own between reports. But some of those companies' lenders must publish what each loan is worth. The catch is names: KnowBe4 sits with 10 funds under 9 different descriptions.

Lender Watch finds each company's loans in US regulator filings and returns your list with a flag per company and a link for each loan. Code matches clear names. You settle unclear ones, or turn on an AI. No AI produces a number.

On 291 companies from 6 private equity firms' websites, 144 have a usable value and 14 are flagged. KnowBe4's lenders went from about 89 to 78 cents per dollar owed in a quarter.

What I tested:
If the tool searches all lenders, you cover your whole list. It found 86% of known companies, against a 90% target.
If an AI reads unclear names, wrong matches drop out. Plain search gets 94.4% of loans right and this gets 100%, on answers an AI wrote that a person hasn't checked yet.
If you compare values across quarters, you see cuts before fund reports. Results arrive about 2 months after quarter end, against 2 to 4 for reports.

What I learned: every headline number started out wrong. Plain matching was 94% right, not 70%. An AI review panel cut flags from 31 to 14.

It reaches you from your workbook three ways: a formula, a question, or an offer when a lookup returns #N/A. Exabeam appears only as LogRhythm, so a lookup finds nothing. The Excel add-in is built but hasn't run in real Excel.

No investor has seen it yet. Next: two vendor demos and 6 interviews.

Built with Python, the Claude API, MCP and Streamlit, on public data only.

**Demo:** https://lender-watch.streamlit.app
**Case study:** https://alexandrecela10.github.io/projects/lender-watch/
**Code:** https://github.com/alexandrecela10/lender-watch
