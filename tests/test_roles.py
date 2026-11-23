"""The title rule."""

import pytest

from jobwatcher.roles import in_role


@pytest.mark.parametrize(
    "title",
    [
        "Financial Analyst",
        "Senior Financial Analyst, FP&A",
        "FP&A Analyst",
        "Analyst, FP&A",
        "Finance Analyst II",
        "Investment Analyst",
        "Credit Analyst - Commercial Banking",
        "Treasury Analyst",
        "Equity Research Analyst",
        "Corporate Development Analyst",
        "Valuation Analyst",
        "Budget Analyst",
        "financial analysts (summer intern)",
    ],
)
def test_in_role(title):
    assert in_role(title)


@pytest.mark.parametrize(
    "title",
    [
        "Software Engineer",
        "Data Analyst",  # analyst, but no finance topic
        "Business Analyst",
        "Financial Advisor",  # finance topic, but not an analyst
        "FP&A Manager",  # finance topic, but not an analyst
        "Fraud Analyst",
        "Financial Crimes Analyst",
        "Compliance Analyst, Finance",
        "Cyber Security Analyst - Financial Services",
        "Financial Systems Analyst",
        "Analyst",
        "",
        None,
    ],
)
def test_not_in_role(title):
    assert not in_role(title)


def test_whole_words_only():
    # 'credit' inside another word is not a finance topic, and 'analysts' still counts
    assert not in_role("Accredited Analyst")
    assert in_role("Credit Analysts")
