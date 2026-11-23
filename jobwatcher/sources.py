"""The watch list: every employer job board the pipeline reads.

Each source is one employer board on one applicant tracking system (ATS).
All boards return JSON to a plain request with no login.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Source:
    name: str  # file-safe slug; used in raw file names and posting ids
    employer: str  # display name
    ats: str  # workday | greenhouse | lever | ashby | smartrecruiters
    params: dict = field(default_factory=dict)


def _workday(name, employer, host, site, search=""):
    return Source(
        name,
        employer,
        "workday",
        {"host": host, "tenant": host.split(".")[0], "site": site, "search": search},
    )


def _greenhouse(name, employer, token):
    return Source(name, employer, "greenhouse", {"token": token})


SOURCES = [
    # --- Workday: banks, payments and asset managers ---
    _workday("capitalone", "Capital One", "capitalone.wd12.myworkdayjobs.com", "Capital_One"),
    _workday("wellsfargo", "Wells Fargo", "wf.wd1.myworkdayjobs.com", "WellsFargoJobs"),
    _workday("mastercard", "Mastercard", "mastercard.wd1.myworkdayjobs.com", "CorporateCareers"),
    _workday("blackrock", "BlackRock", "blackrock.wd1.myworkdayjobs.com", "BlackRock_Professional"),
    _workday("paypal", "PayPal", "paypal.wd1.myworkdayjobs.com", "jobs"),
    _workday("truist", "Truist", "truist.wd1.myworkdayjobs.com", "Careers"),
    _workday("usbank", "U.S. Bank", "usbank.wd1.myworkdayjobs.com", "US_Bank_Careers"),
    _workday("pnc", "PNC", "pnc.wd5.myworkdayjobs.com", "External"),
    _workday("regions", "Regions Bank", "regions.wd5.myworkdayjobs.com", "Regions_Careers"),
    _workday("fifththird", "Fifth Third Bank", "fifththird.wd5.myworkdayjobs.com", "53careers"),
    _workday("statestreet", "State Street", "statestreet.wd1.myworkdayjobs.com", "Global"),
    _workday("northerntrust", "Northern Trust", "ntrs.wd1.myworkdayjobs.com", "northerntrust"),
    _workday("vanguard", "Vanguard", "vanguard.wd5.myworkdayjobs.com", "vanguard_external"),
    _workday("fidelity", "Fidelity Investments", "fmr.wd1.myworkdayjobs.com", "FidelityCareers"),
    _workday("visa", "Visa", "visa.wd5.myworkdayjobs.com", "Visa"),
    _workday("aig", "AIG", "aig.wd1.myworkdayjobs.com", "aig"),
    # --- Greenhouse: fintech ---
    _greenhouse("stripe", "Stripe", "stripe"),
    _greenhouse("robinhood", "Robinhood", "robinhood"),
    _greenhouse("coinbase", "Coinbase", "coinbase"),
    _greenhouse("affirm", "Affirm", "affirm"),
    _greenhouse("sofi", "SoFi", "sofi"),
    _greenhouse("block", "Block", "block"),
    # --- Lever ---
    Source("palantir", "Palantir", "lever", {"company": "palantir"}),
    Source("spotify", "Spotify", "lever", {"company": "spotify"}),
    # --- Ashby ---
    Source("ramp", "Ramp", "ashby", {"board": "ramp"}),
    Source("plaid", "Plaid", "ashby", {"board": "plaid"}),
    # --- SmartRecruiters ---
    Source("experian", "Experian", "smartrecruiters", {"company": "Experian"}),
    Source("servicenow", "ServiceNow", "smartrecruiters", {"company": "ServiceNow"}),
]

BY_NAME = {s.name: s for s in SOURCES}
