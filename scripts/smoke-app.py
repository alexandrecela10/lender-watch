"""Runs inside a container: checks the review app answers for a known company.

Types two names into the app and clicks the button, as tests/test_app.py does.
Exits non-zero if KnowBe4 is not flagged or an unknown name is not reported as not found.
"""

import os
import sys

from streamlit.testing.v1 import AppTest

at = AppTest.from_file("/app/app/review.py", default_timeout=300).run()
at.text_area[0].input("KnowBe4\nNot A Real Company Xyzzy").run()
next(b for b in at.button if b.label == "Check lender filings").click().run()
if at.exception:
    sys.exit(f"FAIL: the app raised {at.exception[0].value}")

table = next(d.value for d in at.dataframe if "Flag" in d.value.columns)
table = table.set_index("Company")
flag = table.loc["KnowBe4", "Flag"]
unknown = table.loc["Not A Real Company Xyzzy", "What lenders show"]
print(f"image commit: {os.environ.get('ERM_BUILD_COMMIT')}")
print(f"KnowBe4: {flag}")
print(f"Not A Real Company Xyzzy: {unknown}")
sys.exit(0 if flag == "Flagged" and unknown == "No public lender found" else 1)
