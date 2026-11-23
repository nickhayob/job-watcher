"""The title rule: is a posting in my role (finance analyst)?

A title is in role when it
  1. names an analyst role (the word 'analyst'), and
  2. names a finance topic (financial, finance, FP&A, investment, credit,
     treasury, valuation, equity research, corporate development, budget,
     forecasting), and
  3. does not contain an excluded word (fraud, compliance, security and
     similar words that make it a different job).

The rule looks only at the title, ignores case, and applies to every row in
the history each time the history is built.
"""

import re

ANALYST = re.compile(r"\banalysts?\b", re.IGNORECASE)

FINANCE = re.compile(
    r"\bfinancial\b|\bfinance\b|\bfp\s*(?:&|&amp;|and)\s*a\b|\binvestments?\b|\bcredit\b"
    r"|\btreasury\b|\bvaluations?\b|\bequity research\b|\bcorporate development\b"
    r"|\bbudget(?:ing)?\b|\bforecasting\b",
    re.IGNORECASE,
)

EXCLUDE = re.compile(
    r"\bfraud\b|\bcrimes?\b|\baml\b|\bkyc\b|\bcompliance\b|\bsanctions?\b|\bcyber\b"
    r"|\bsecurity\b|\bsoftware\b|\bsystems? analyst\b|\bclinical\b|\bnurse\b|\bintelligence\b",
    re.IGNORECASE,
)


def in_role(title):
    """True when the title is a finance analyst role."""
    text = title or ""
    return bool(ANALYST.search(text) and FINANCE.search(text) and not EXCLUDE.search(text))
