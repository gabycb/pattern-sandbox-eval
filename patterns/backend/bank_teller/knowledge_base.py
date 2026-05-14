"""
Synthetic Banking Knowledge Base with Role-Based Access Control

Provides an in-memory knowledge base of banking policies, procedures, and data
organized by domain. Supports role-gated retrieval where managers have access
to additional sensitive information (financials, overrides, HR data).
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class UserRole(str, Enum):
    IC = "ic"
    MANAGER = "manager"


class Domain(str, Enum):
    ACCOUNTS = "accounts"
    WIRE_TRANSFERS = "wire_transfers"
    DISPUTES = "disputes"
    LENDING = "lending"
    COMPLIANCE = "compliance"
    FINANCIALS = "financials"
    HR = "hr"
    OVERRIDES = "overrides"


@dataclass
class KBArticle:
    id: str
    title: str
    domain: Domain
    content: str
    keywords: list[str] = field(default_factory=list)
    min_role: UserRole = UserRole.IC  # minimum role required to access


# ---------------------------------------------------------------------------
# Synthetic knowledge base articles
# ---------------------------------------------------------------------------

KNOWLEDGE_BASE: list[KBArticle] = [
    # --- ACCOUNTS (IC accessible) ---
    KBArticle(
        id="acct-001",
        title="Personal Checking Account Types",
        domain=Domain.ACCOUNTS,
        content=(
            "We offer three personal checking tiers: Basic (no minimum balance, $5/mo fee), "
            "Plus (min $1,500 balance, no fee, earns 0.01% APY), and Premium ($25,000 min, "
            "no fee, earns 0.05% APY, includes free cashier's checks and safe deposit box). "
            "All tiers include free online/mobile banking, bill pay, and Zelle."
        ),
        keywords=["checking", "account types", "basic", "plus", "premium", "balance", "fee"],
    ),
    KBArticle(
        id="acct-002",
        title="Business Account Opening Requirements",
        domain=Domain.ACCOUNTS,
        content=(
            "Business checking requires: EIN or SSN (sole prop), articles of incorporation "
            "or DBA filing, two forms of ID for all signers, initial deposit of $100+. "
            "Processing takes 1-3 business days. Beneficial ownership form required for "
            "entities with 25%+ ownership stake. CIP verification completed within 24hrs."
        ),
        keywords=["business", "account opening", "requirements", "EIN", "incorporation", "CIP"],
    ),
    KBArticle(
        id="acct-003",
        title="Account Closure Procedures",
        domain=Domain.ACCOUNTS,
        content=(
            "Account closure requires: zero balance, no pending transactions, no linked "
            "automatic payments. Customer must sign closure form in-branch or submit "
            "notarized letter. Joint accounts need all signers' consent. Remaining balance "
            "disbursed via cashier's check or transfer to another account. Allow 5 business "
            "days for finalization. Early closure fee of $25 if account < 90 days old."
        ),
        keywords=["closure", "close account", "early closure fee"],
    ),

    # --- WIRE TRANSFERS (IC accessible) ---
    KBArticle(
        id="wire-001",
        title="Domestic Wire Transfer Limits and Fees",
        domain=Domain.WIRE_TRANSFERS,
        content=(
            "Domestic wire limits: Personal accounts $10,000/day, Business accounts $50,000/day. "
            "Fees: $25 outgoing, $15 incoming. Same-day processing if submitted before 4 PM ET. "
            "Requires recipient's bank name, routing number, account number, and beneficiary name. "
            "Wires over $10,000 trigger CTR filing automatically."
        ),
        keywords=["wire transfer", "domestic", "limit", "fee", "CTR"],
    ),
    KBArticle(
        id="wire-002",
        title="International Wire Transfer Procedures",
        domain=Domain.WIRE_TRANSFERS,
        content=(
            "International wires require SWIFT/BIC code, IBAN (where applicable), intermediary "
            "bank details, and purpose of payment. Limits: $25,000/day personal, $100,000/day "
            "business. Fees: $45 outgoing, $20 incoming. Processing: 2-5 business days. "
            "OFAC screening applied to all international wires. Wires to sanctioned countries "
            "are blocked automatically."
        ),
        keywords=["international", "wire", "SWIFT", "IBAN", "OFAC", "sanctions"],
    ),

    # --- DISPUTES (IC accessible) ---
    KBArticle(
        id="disp-001",
        title="Debit Card Dispute Process",
        domain=Domain.DISPUTES,
        content=(
            "Customer must file dispute within 60 days of statement date. Provisional credit "
            "issued within 10 business days for amounts under $5,000. Investigation takes up "
            "to 45 calendar days (90 days for POS and international). Customer completes "
            "Dispute Affidavit form. Merchant has 30 days to respond to chargeback. "
            "If merchant doesn't respond, dispute is resolved in customer's favor."
        ),
        keywords=["dispute", "debit card", "chargeback", "provisional credit", "affidavit"],
    ),
    KBArticle(
        id="disp-002",
        title="ACH Unauthorized Transaction Disputes",
        domain=Domain.DISPUTES,
        content=(
            "Unauthorized ACH debits can be returned within 60 calendar days of settlement. "
            "Customer signs ACH Indemnity Declaration. For consumer accounts, Reg E applies: "
            "bank must investigate within 10 business days, provisional credit within 10 days. "
            "Business accounts follow NACHA rules: return within 2 business days of discovery, "
            "no provisional credit required. File SAR if fraud suspected."
        ),
        keywords=["ACH", "unauthorized", "Reg E", "NACHA", "SAR", "indemnity"],
    ),

    # --- LENDING (IC accessible) ---
    KBArticle(
        id="lend-001",
        title="Personal Loan Products Overview",
        domain=Domain.LENDING,
        content=(
            "Personal loan options: Unsecured ($2K-$50K, 7.99-18.99% APR, 12-60 months), "
            "Secured by CD/Savings ($1K-$250K, 3.99-8.99% APR), Home Equity Line ($25K-$500K, "
            "prime+0.5%). Minimum credit score 680 for unsecured, 620 for secured. "
            "Application requires: 2 years employment history, income verification, "
            "debt-to-income ratio under 43%."
        ),
        keywords=["personal loan", "unsecured", "secured", "HELOC", "credit score", "DTI"],
    ),
    KBArticle(
        id="lend-002",
        title="Mortgage Rate Lock Policy",
        domain=Domain.LENDING,
        content=(
            "Rate locks available for 30, 45, or 60 days. 30-day lock is free, 45-day is "
            "0.125 points, 60-day is 0.25 points. Float-down option available for 0.125 points "
            "if rates drop 0.25%+. Rate lock extension: $50/day after expiration. "
            "Lock is binding once signed. Re-lock after expiration requires new credit pull."
        ),
        keywords=["mortgage", "rate lock", "float-down", "points"],
    ),

    # --- COMPLIANCE (IC accessible) ---
    KBArticle(
        id="comp-001",
        title="BSA/AML Customer Due Diligence",
        domain=Domain.COMPLIANCE,
        content=(
            "All new accounts require CDD: verify identity (CIP), assess risk level, "
            "understand nature of business. Enhanced Due Diligence (EDD) required for: "
            "PEPs, high-risk countries, cash-intensive businesses, MSBs. "
            "Ongoing monitoring: transaction pattern analysis, periodic reviews (high-risk "
            "annually, medium every 2 years). SAR filing within 30 days of suspicious activity."
        ),
        keywords=["BSA", "AML", "CDD", "EDD", "PEP", "SAR", "CIP", "KYC"],
    ),
    KBArticle(
        id="comp-002",
        title="Large Cash Transaction Reporting",
        domain=Domain.COMPLIANCE,
        content=(
            "CTR (Currency Transaction Report) required for cash transactions over $10,000 "
            "in a single day (aggregate). Filed via FinCEN BSA E-Filing within 15 calendar days. "
            "Structuring (breaking transactions to avoid CTR) is illegal — report suspected "
            "structuring via SAR. Do NOT inform the customer about CTR or SAR filings. "
            "Exemptions available for established business customers (file DOEP)."
        ),
        keywords=["CTR", "cash", "structuring", "FinCEN", "DOEP", "$10,000"],
    ),

    # --- FINANCIALS (Manager only) ---
    KBArticle(
        id="fin-001",
        title="Branch Q1 2025 P&L Summary",
        domain=Domain.FINANCIALS,
        content=(
            "Q1 2025 Branch Performance: Total Revenue $2.3M (+8% YoY). Net Interest Income "
            "$1.6M, Fee Income $450K, Other Income $250K. Total Expenses $1.8M. Net Income "
            "$500K (margin 21.7%). Loan portfolio grew 12% to $45M. Deposit growth 6% to $78M. "
            "NIM at 3.45%, up 15bps. Cost-to-income ratio improved to 78.3% from 81.2%."
        ),
        keywords=["P&L", "revenue", "net income", "branch performance", "quarterly", "NIM"],
        min_role=UserRole.MANAGER,
    ),
    KBArticle(
        id="fin-002",
        title="Branch Fee Revenue Breakdown",
        domain=Domain.FINANCIALS,
        content=(
            "Fee Income Detail Q1 2025: NSF/OD fees $120K (down 15% — regulatory pressure), "
            "Wire fees $85K, ATM surcharge $45K, Account maintenance $95K, Safe deposit $35K, "
            "Loan origination $70K. Top fee contributor: Account maintenance (21%). "
            "Action items: grow non-interest income via wealth management referrals (target $50K/q)."
        ),
        keywords=["fee revenue", "NSF", "overdraft", "fee income", "breakdown"],
        min_role=UserRole.MANAGER,
    ),

    # --- HR (Manager only) ---
    KBArticle(
        id="hr-001",
        title="Branch Staffing and Headcount",
        domain=Domain.HR,
        content=(
            "Current headcount: 12 FTE (3 tellers, 2 personal bankers, 2 loan officers, "
            "1 ops manager, 1 assistant manager, 1 branch manager, 1 wealth advisor, 1 CSR). "
            "Open positions: 1 teller (posted 3/15), 1 personal banker (interviews in progress). "
            "Overtime budget: $8K/month remaining. Turnover rate: 18% (bank avg 22%)."
        ),
        keywords=["staffing", "headcount", "hiring", "turnover", "overtime"],
        min_role=UserRole.MANAGER,
    ),

    # --- OVERRIDES (Manager only) ---
    KBArticle(
        id="ovr-001",
        title="Manager Override Authority Limits",
        domain=Domain.OVERRIDES,
        content=(
            "Branch Manager override authority: Fee waiver up to $100/incident, $500/customer/year. "
            "Wire limit increase: up to 2x standard limit with verbal approval, documented in notes. "
            "Hold release: can release up to $5,000 of Reg CC hold for established customers "
            "(account age > 6 months, no NSF history in 12 months). "
            "Overdraft courtesy pay: authorize up to $1,000 for customers with 1+ year tenure. "
            "All overrides logged in Override Journal with reason code."
        ),
        keywords=["override", "fee waiver", "limit increase", "hold release", "authority"],
        min_role=UserRole.MANAGER,
    ),
    KBArticle(
        id="ovr-002",
        title="Exception Processing Guidelines",
        domain=Domain.OVERRIDES,
        content=(
            "Exceptions requiring Regional Manager approval: fee waivers > $100, "
            "wire limits > 2x standard, new account without full CIP documentation "
            "(24hr conditional approval max), overdraft courtesy > $1,000. "
            "All exceptions require completed Exception Request Form with: customer name, "
            "account number, exception type, business justification, risk assessment. "
            "Regional approval response SLA: 4 business hours."
        ),
        keywords=["exception", "regional approval", "escalation", "conditional"],
        min_role=UserRole.MANAGER,
    ),
]


def retrieve(query: str, role: UserRole = UserRole.IC, top_k: int = 3) -> list[KBArticle]:
    """
    Retrieve relevant KB articles for a query, filtered by user role.
    Uses simple keyword matching (production would use vector search).
    """
    query_lower = query.lower()
    query_words = set(query_lower.split())

    scored: list[tuple[float, KBArticle]] = []
    for article in KNOWLEDGE_BASE:
        # Role gate
        if article.min_role == UserRole.MANAGER and role == UserRole.IC:
            continue

        # Score by keyword overlap
        score = 0.0
        for kw in article.keywords:
            kw_lower = kw.lower()
            if kw_lower in query_lower:
                score += 2.0  # exact phrase match in query
            elif any(w in kw_lower for w in query_words):
                score += 1.0  # partial word match

        # Boost for title match
        title_lower = article.title.lower()
        if any(w in title_lower for w in query_words if len(w) > 3):
            score += 1.5

        # Boost for domain match
        domain_lower = article.domain.value.replace("_", " ")
        if any(w in domain_lower for w in query_words):
            score += 1.0

        if score > 0:
            scored.append((score, article))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [article for _, article in scored[:top_k]]


def format_context(articles: list[KBArticle]) -> str:
    """Format retrieved articles into a context string for agent prompts."""
    if not articles:
        return "No relevant knowledge base articles found."

    parts = []
    for i, article in enumerate(articles, 1):
        access = "🔒 Manager Only" if article.min_role == UserRole.MANAGER else "📖 All Staff"
        parts.append(
            f"[Article {i}] {article.title} ({access})\n"
            f"Domain: {article.domain.value}\n"
            f"{article.content}"
        )
    return "\n\n---\n\n".join(parts)


def get_domains_for_role(role: UserRole) -> list[Domain]:
    """Return accessible domains for a given role."""
    all_domains = list(Domain)
    if role == UserRole.IC:
        return [d for d in all_domains if d not in (Domain.FINANCIALS, Domain.HR, Domain.OVERRIDES)]
    return all_domains


def get_article_by_id(article_id: str) -> Optional[KBArticle]:
    """Look up a specific article by ID."""
    for article in KNOWLEDGE_BASE:
        if article.id == article_id:
            return article
    return None
