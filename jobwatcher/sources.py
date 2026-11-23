"""The watch list: every employer job board the pipeline reads.

Each source is one employer board on one applicant tracking system (ATS).
All boards return JSON to a plain request with no login.

(Sixteen banks on Workday were tried first. Workday answered GitHub's servers
with HTTP 429 and made the daily run take half an hour, so those employers
were replaced with the boards below, which answer in seconds.)
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Source:
    name: str  # file-safe slug; used in raw file names and posting ids
    employer: str  # display name
    ats: str  # greenhouse | lever | ashby | smartrecruiters | oracle
    params: dict = field(default_factory=dict)


def _greenhouse(name, employer):
    return Source(name, employer, "greenhouse", {"token": name})


SOURCES = [
    # --- Greenhouse: fintech, payments and large tech employers ---
    _greenhouse("stripe", "Stripe"),
    _greenhouse("robinhood", "Robinhood"),
    _greenhouse("coinbase", "Coinbase"),
    _greenhouse("affirm", "Affirm"),
    _greenhouse("sofi", "SoFi"),
    _greenhouse("block", "Block"),
    _greenhouse("brex", "Brex"),
    _greenhouse("chime", "Chime"),
    _greenhouse("carta", "Carta"),
    _greenhouse("adyen", "Adyen"),
    _greenhouse("gusto", "Gusto"),
    _greenhouse("toast", "Toast"),
    _greenhouse("airbnb", "Airbnb"),
    _greenhouse("lyft", "Lyft"),
    _greenhouse("databricks", "Databricks"),
    _greenhouse("datadog", "Datadog"),
    _greenhouse("cloudflare", "Cloudflare"),
    _greenhouse("okta", "Okta"),
    _greenhouse("mongodb", "MongoDB"),
    _greenhouse("anthropic", "Anthropic"),
    _greenhouse("point72", "Point72"),
    _greenhouse("ripple", "Ripple"),
    _greenhouse("payoneer", "Payoneer"),
    _greenhouse("monzo", "Monzo"),
    _greenhouse("betterment", "Betterment"),
    _greenhouse("billcom", "Bill"),
    _greenhouse("lendingtree", "LendingTree"),
    _greenhouse("aqr", "AQR Capital Management"),
    _greenhouse("virtu", "Virtu Financial"),
    _greenhouse("dvtrading", "DV Trading"),
    _greenhouse("drweng", "DRW"),
    _greenhouse("akunacapital", "Akuna Capital"),
    _greenhouse("oportun", "Oportun"),
    _greenhouse("upgrade", "Upgrade"),
    _greenhouse("clearwater", "Clearwater Analytics"),
    # --- Lever ---
    Source("palantir", "Palantir", "lever", {"company": "palantir"}),
    Source("spotify", "Spotify", "lever", {"company": "spotify"}),
    Source("nium", "Nium", "lever", {"company": "nium"}),
    Source("wealthfront", "Wealthfront", "lever", {"company": "wealthfront"}),
    Source("crypto", "Crypto.com", "lever", {"company": "crypto"}),
    # --- Ashby ---
    Source("ramp", "Ramp", "ashby", {"board": "ramp"}),
    Source("plaid", "Plaid", "ashby", {"board": "plaid"}),
    Source("notion", "Notion", "ashby", {"board": "notion"}),
    Source("wealthsimple", "Wealthsimple", "ashby", {"board": "wealthsimple"}),
    Source("airwallex", "Airwallex", "ashby", {"board": "airwallex"}),
    Source("rho", "Rho", "ashby", {"board": "rho"}),
    # --- SmartRecruiters ---
    Source("experian", "Experian", "smartrecruiters", {"company": "Experian"}),
    Source("servicenow", "ServiceNow", "smartrecruiters", {"company": "ServiceNow"}),
    Source("equinox", "Equinox", "smartrecruiters", {"company": "Equinox"}),
    # --- Oracle Recruiting Cloud: a bank. The whole board is about 6,800 postings, over the
    # 5,000 limit, so it is read with the search term "analyst" (about 1,000 postings).
    Source(
        "jpmorgan", "JPMorgan Chase", "oracle",
        {"host": "jpmc.fa.oraclecloud.com", "site": "CX_1001", "search": "analyst"},
    ),
]

BY_NAME = {s.name: s for s in SOURCES}
