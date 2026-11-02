# Lender Watch

**One line:** see when lenders start doubting the companies you've invested in, with the public filing as proof.

**Description:**

Private equity funds own companies, and investors in those funds rarely hear about them between reports. But some of those companies' lenders must publish what each loan is worth today. The catch is names: one company, KnowBe4, sits with 10 funds under 9 different descriptions.

Lender Watch takes a list of company names, finds each company's loans in US regulator filings, and returns the list with a flag per company and a link for each loan. Code matches the clear names. You settle the unclear ones, or turn on an AI. No AI produces a number.

On 291 companies from 6 private equity firms' websites, 144 have a usable value and 14 are flagged. KnowBe4's lenders went from about 89 to 78 cents per dollar owed in a quarter.

What I tested:
If the tool searches all lenders, you cover your whole list. It found 86% of known companies, against a 90% target.
If an AI reads unclear names, wrong matches drop out. Plain search gets 94.4% of loans right and this gets 100%, on answers an AI wrote that a person hasn't checked yet.
If you compare values across quarters, you see cuts before fund reports. As built, results arrive about 2 months after quarter end, against 2 to 4 months for reports.

What I learned: every headline number started out wrong, and checking real rows fixed it. Plain matching was 94% right, not 70%. Half the rows were old. Canadian loans looked marked down because of a currency mix-up. An AI review panel cut flags from 31 to 14, and my value estimate from $540k to $14k to $240k a year, all assumed.

No investor has seen it yet, so nobody has confirmed they want it. Next: two vendor demos and 6 interviews.

Built with Python, the Claude API and Streamlit, using public data only.

**Demo:** https://lender-watch.streamlit.app
**Case study:** https://alexandrecela10.github.io/projects/lender-watch/
**Code:** https://github.com/alexandrecela10/lender-watch
