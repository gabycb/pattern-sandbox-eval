"""
Evaluation Dataset for Bank Teller Knowledge Retrieval

50 test cases across 5 categories:
- Simple policy lookups (15)
- Role-gated queries (10)
- Multi-domain queries (10)
- Compliance-sensitive (10)
- Edge cases (5)

Each case includes: query, user_role, expected_domain, ground_truth, complexity
"""

from dataclasses import dataclass
from bank_teller.knowledge_base import UserRole, Domain


@dataclass
class EvalCase:
    id: str
    query: str
    user_role: UserRole
    expected_domain: str  # expected specialist/domain
    ground_truth: str     # key facts the answer should contain
    complexity: str       # simple | moderate | complex
    category: str         # simple_lookup | role_gated | multi_domain | compliance | edge_case


EVAL_DATASET: list[EvalCase] = [
    # =========================================================================
    # SIMPLE POLICY LOOKUPS (15 cases)
    # =========================================================================
    EvalCase(
        id="simple-01",
        query="What's the daily wire transfer limit for personal accounts?",
        user_role=UserRole.IC,
        expected_domain="policy",
        ground_truth="Personal accounts have a $10,000/day domestic wire limit. Fee is $25 outgoing.",
        complexity="simple",
        category="simple_lookup",
    ),
    EvalCase(
        id="simple-02",
        query="How much does it cost to send a domestic wire?",
        user_role=UserRole.IC,
        expected_domain="policy",
        ground_truth="Domestic wire fee is $25 outgoing, $15 incoming.",
        complexity="simple",
        category="simple_lookup",
    ),
    EvalCase(
        id="simple-03",
        query="What are the checking account tiers we offer?",
        user_role=UserRole.IC,
        expected_domain="policy",
        ground_truth="Three tiers: Basic ($5/mo fee), Plus ($1,500 min, no fee), Premium ($25,000 min, no fee).",
        complexity="simple",
        category="simple_lookup",
    ),
    EvalCase(
        id="simple-04",
        query="What documents do I need to open a business checking account?",
        user_role=UserRole.IC,
        expected_domain="policy",
        ground_truth="EIN or SSN, articles of incorporation or DBA, two forms of ID, $100+ initial deposit, beneficial ownership form.",
        complexity="simple",
        category="simple_lookup",
    ),
    EvalCase(
        id="simple-05",
        query="How long does it take to process an international wire?",
        user_role=UserRole.IC,
        expected_domain="policy",
        ground_truth="International wires take 2-5 business days to process.",
        complexity="simple",
        category="simple_lookup",
    ),
    EvalCase(
        id="simple-06",
        query="What's the minimum credit score for an unsecured personal loan?",
        user_role=UserRole.IC,
        expected_domain="lending",
        ground_truth="Minimum credit score is 680 for unsecured personal loans.",
        complexity="simple",
        category="simple_lookup",
    ),
    EvalCase(
        id="simple-07",
        query="What is the rate lock policy for mortgages?",
        user_role=UserRole.IC,
        expected_domain="lending",
        ground_truth="30-day lock is free, 45-day is 0.125 points, 60-day is 0.25 points. Float-down available for 0.125 points.",
        complexity="simple",
        category="simple_lookup",
    ),
    EvalCase(
        id="simple-08",
        query="Is there an early closure fee for checking accounts?",
        user_role=UserRole.IC,
        expected_domain="policy",
        ground_truth="Yes, $25 early closure fee if account is less than 90 days old.",
        complexity="simple",
        category="simple_lookup",
    ),
    EvalCase(
        id="simple-09",
        query="How do I close a joint checking account?",
        user_role=UserRole.IC,
        expected_domain="policy",
        ground_truth="Joint accounts need all signers' consent. Customer must sign closure form in-branch or submit notarized letter.",
        complexity="simple",
        category="simple_lookup",
    ),
    EvalCase(
        id="simple-10",
        query="What's the APR range for unsecured personal loans?",
        user_role=UserRole.IC,
        expected_domain="lending",
        ground_truth="Unsecured personal loans: 7.99-18.99% APR, $2K-$50K, 12-60 months.",
        complexity="simple",
        category="simple_lookup",
    ),
    EvalCase(
        id="simple-11",
        query="How long does a customer have to file a debit card dispute?",
        user_role=UserRole.IC,
        expected_domain="policy",
        ground_truth="Customer must file dispute within 60 days of statement date.",
        complexity="simple",
        category="simple_lookup",
    ),
    EvalCase(
        id="simple-12",
        query="When is provisional credit issued for disputes?",
        user_role=UserRole.IC,
        expected_domain="policy",
        ground_truth="Provisional credit issued within 10 business days for amounts under $5,000.",
        complexity="simple",
        category="simple_lookup",
    ),
    EvalCase(
        id="simple-13",
        query="What do I need for an international wire — SWIFT code or routing number?",
        user_role=UserRole.IC,
        expected_domain="policy",
        ground_truth="International wires require SWIFT/BIC code, IBAN where applicable, intermediary bank details.",
        complexity="simple",
        category="simple_lookup",
    ),
    EvalCase(
        id="simple-14",
        query="What's the maximum HELOC amount?",
        user_role=UserRole.IC,
        expected_domain="lending",
        ground_truth="Home Equity Line: $25K-$500K, prime+0.5%.",
        complexity="simple",
        category="simple_lookup",
    ),
    EvalCase(
        id="simple-15",
        query="What's the incoming wire fee?",
        user_role=UserRole.IC,
        expected_domain="policy",
        ground_truth="Incoming domestic wire fee is $15. International incoming is $20.",
        complexity="simple",
        category="simple_lookup",
    ),

    # =========================================================================
    # ROLE-GATED QUERIES (10 cases)
    # =========================================================================
    EvalCase(
        id="role-01",
        query="What was our branch revenue last quarter?",
        user_role=UserRole.MANAGER,
        expected_domain="manager_insights",
        ground_truth="Q1 2025 Total Revenue $2.3M (+8% YoY). Net Income $500K, margin 21.7%.",
        complexity="moderate",
        category="role_gated",
    ),
    EvalCase(
        id="role-02",
        query="Show me the branch P&L",
        user_role=UserRole.IC,
        expected_domain="manager_insights",
        ground_truth="ACCESS DENIED — P&L data is manager-only. IC should be blocked.",
        complexity="simple",
        category="role_gated",
    ),
    EvalCase(
        id="role-03",
        query="How many open positions do we have right now?",
        user_role=UserRole.MANAGER,
        expected_domain="manager_insights",
        ground_truth="2 open positions: 1 teller (posted 3/15), 1 personal banker (interviews in progress).",
        complexity="simple",
        category="role_gated",
    ),
    EvalCase(
        id="role-04",
        query="What's our current headcount?",
        user_role=UserRole.IC,
        expected_domain="manager_insights",
        ground_truth="ACCESS DENIED — staffing data is manager-only.",
        complexity="simple",
        category="role_gated",
    ),
    EvalCase(
        id="role-05",
        query="What's my override authority for fee waivers?",
        user_role=UserRole.MANAGER,
        expected_domain="manager_insights",
        ground_truth="Fee waiver up to $100/incident, $500/customer/year. All overrides logged in Override Journal.",
        complexity="moderate",
        category="role_gated",
    ),
    EvalCase(
        id="role-06",
        query="Can I override a hold on a customer's check?",
        user_role=UserRole.MANAGER,
        expected_domain="manager_insights",
        ground_truth="Can release up to $5,000 of Reg CC hold for established customers (6+ months, no NSF in 12 months).",
        complexity="moderate",
        category="role_gated",
    ),
    EvalCase(
        id="role-07",
        query="Can I waive this customer's wire transfer fee?",
        user_role=UserRole.IC,
        expected_domain="manager_insights",
        ground_truth="ACCESS DENIED — override authority is manager-only. IC should escalate to manager.",
        complexity="moderate",
        category="role_gated",
    ),
    EvalCase(
        id="role-08",
        query="What's our net interest margin?",
        user_role=UserRole.MANAGER,
        expected_domain="manager_insights",
        ground_truth="NIM at 3.45%, up 15bps.",
        complexity="simple",
        category="role_gated",
    ),
    EvalCase(
        id="role-09",
        query="What are the top fee revenue categories?",
        user_role=UserRole.MANAGER,
        expected_domain="manager_insights",
        ground_truth="Top categories: Account maintenance $95K (21%), NSF/OD $120K, Wire fees $85K.",
        complexity="moderate",
        category="role_gated",
    ),
    EvalCase(
        id="role-10",
        query="What's our overtime budget remaining?",
        user_role=UserRole.IC,
        expected_domain="manager_insights",
        ground_truth="ACCESS DENIED — budget data is manager-only.",
        complexity="simple",
        category="role_gated",
    ),

    # =========================================================================
    # MULTI-DOMAIN QUERIES (10 cases)
    # =========================================================================
    EvalCase(
        id="multi-01",
        query="A customer wants to dispute a charge and also open a CD — what are the processes?",
        user_role=UserRole.IC,
        expected_domain="policy",
        ground_truth="Dispute: file within 60 days, provisional credit in 10 days. CD: (general account opening procedures apply).",
        complexity="complex",
        category="multi_domain",
    ),
    EvalCase(
        id="multi-02",
        query="Customer is asking about personal loan rates and also wants to send a large wire transfer",
        user_role=UserRole.IC,
        expected_domain="policy",
        ground_truth="Personal loan: 7.99-18.99% APR. Wire: $10K/day personal limit, $25 fee, CTR if over $10K cash.",
        complexity="complex",
        category="multi_domain",
    ),
    EvalCase(
        id="multi-03",
        query="New business customer wants to open an account and set up wire transfers — what do they need?",
        user_role=UserRole.IC,
        expected_domain="policy",
        ground_truth="Business account: EIN, articles of incorporation, 2 IDs, $100 deposit. Wire: $50K/day business limit.",
        complexity="complex",
        category="multi_domain",
    ),
    EvalCase(
        id="multi-04",
        query="Customer has an unauthorized ACH debit and wants to close their account",
        user_role=UserRole.IC,
        expected_domain="policy",
        ground_truth="ACH dispute: return within 60 days, Reg E applies, provisional credit in 10 days. Closure: zero balance, no pending transactions, sign form.",
        complexity="complex",
        category="multi_domain",
    ),
    EvalCase(
        id="multi-05",
        query="What's the branch turnover rate and how does our fee revenue compare to targets?",
        user_role=UserRole.MANAGER,
        expected_domain="manager_insights",
        ground_truth="Turnover: 18% (bank avg 22%). Fee target: grow wealth referrals to $50K/q.",
        complexity="complex",
        category="multi_domain",
    ),
    EvalCase(
        id="multi-06",
        query="Customer wants a mortgage rate lock and also needs to file a dispute on their debit card",
        user_role=UserRole.IC,
        expected_domain="policy",
        ground_truth="Rate lock: 30-day free, 45-day 0.125 pts, 60-day 0.25 pts. Dispute: 60-day window, form required.",
        complexity="complex",
        category="multi_domain",
    ),
    EvalCase(
        id="multi-07",
        query="I need to open a business account for a cash-intensive business — any special requirements?",
        user_role=UserRole.IC,
        expected_domain="compliance",
        ground_truth="Standard business docs plus Enhanced Due Diligence (EDD) required for cash-intensive businesses. CDD/CIP verification.",
        complexity="complex",
        category="multi_domain",
    ),
    EvalCase(
        id="multi-08",
        query="Customer wants to send an international wire to a country I'm not sure about — and also wants a personal loan",
        user_role=UserRole.IC,
        expected_domain="compliance",
        ground_truth="International wire: OFAC screening required, wires to sanctioned countries blocked. Loan: min 680 credit, DTI under 43%.",
        complexity="complex",
        category="multi_domain",
    ),
    EvalCase(
        id="multi-09",
        query="Can I authorize overdraft courtesy for a customer who also needs a fee waiver?",
        user_role=UserRole.MANAGER,
        expected_domain="manager_insights",
        ground_truth="OD courtesy: up to $1,000 for 1+ year tenure. Fee waiver: up to $100/incident. Both logged in Override Journal.",
        complexity="moderate",
        category="multi_domain",
    ),
    EvalCase(
        id="multi-10",
        query="Walk me through the full process for a new personal banking customer — checking account plus personal loan application",
        user_role=UserRole.IC,
        expected_domain="policy",
        ground_truth="Checking: 3 tiers (Basic/Plus/Premium). Loan: 2yr employment, income verification, DTI<43%, min 680 credit.",
        complexity="complex",
        category="multi_domain",
    ),

    # =========================================================================
    # COMPLIANCE-SENSITIVE (10 cases)
    # =========================================================================
    EvalCase(
        id="comp-01",
        query="Customer is depositing $9,500 in cash today and says they'll bring more tomorrow",
        user_role=UserRole.IC,
        expected_domain="compliance",
        ground_truth="Potential structuring. CTR required for aggregated cash over $10K/day. Report suspected structuring via SAR. Do NOT inform customer.",
        complexity="complex",
        category="compliance",
    ),
    EvalCase(
        id="comp-02",
        query="When do I need to file a CTR?",
        user_role=UserRole.IC,
        expected_domain="compliance",
        ground_truth="CTR required for cash transactions over $10,000 in a single day (aggregate). Filed within 15 calendar days via FinCEN.",
        complexity="simple",
        category="compliance",
    ),
    EvalCase(
        id="comp-03",
        query="The customer is asking why we need so much information to open their account",
        user_role=UserRole.IC,
        expected_domain="compliance",
        ground_truth="CIP/CDD requirements are mandatory. Verify identity, assess risk. Do NOT disclose specific BSA/AML requirements in detail to customer.",
        complexity="moderate",
        category="compliance",
    ),
    EvalCase(
        id="comp-04",
        query="What's the difference between CDD and EDD?",
        user_role=UserRole.IC,
        expected_domain="compliance",
        ground_truth="CDD: standard for all accounts (identity, risk assessment). EDD: enhanced for high-risk (PEPs, high-risk countries, cash-intensive, MSBs).",
        complexity="moderate",
        category="compliance",
    ),
    EvalCase(
        id="comp-05",
        query="A politically exposed person wants to open an account — what extra steps?",
        user_role=UserRole.IC,
        expected_domain="compliance",
        ground_truth="PEPs require Enhanced Due Diligence (EDD). Higher ongoing monitoring frequency (annual reviews).",
        complexity="complex",
        category="compliance",
    ),
    EvalCase(
        id="comp-06",
        query="Customer wants to wire money to Cuba",
        user_role=UserRole.IC,
        expected_domain="compliance",
        ground_truth="OFAC screening required. Wires to sanctioned countries are blocked automatically. Cannot process.",
        complexity="moderate",
        category="compliance",
    ),
    EvalCase(
        id="comp-07",
        query="How often do we need to review high-risk accounts?",
        user_role=UserRole.IC,
        expected_domain="compliance",
        ground_truth="High-risk: annual reviews. Medium-risk: every 2 years.",
        complexity="simple",
        category="compliance",
    ),
    EvalCase(
        id="comp-08",
        query="What should I do if I suspect a customer is laundering money?",
        user_role=UserRole.IC,
        expected_domain="compliance",
        ground_truth="File SAR within 30 days. Do NOT inform the customer. Escalate to BSA Officer.",
        complexity="complex",
        category="compliance",
    ),
    EvalCase(
        id="comp-09",
        query="Can I tell the customer we filed a CTR on their transaction?",
        user_role=UserRole.IC,
        expected_domain="compliance",
        ground_truth="Do NOT inform the customer about CTR or SAR filings.",
        complexity="moderate",
        category="compliance",
    ),
    EvalCase(
        id="comp-10",
        query="What is a DOEP exemption?",
        user_role=UserRole.IC,
        expected_domain="compliance",
        ground_truth="DOEP (Designation of Exempt Person) — CTR exemption available for established business customers.",
        complexity="simple",
        category="compliance",
    ),

    # =========================================================================
    # EDGE CASES (5 cases)
    # =========================================================================
    EvalCase(
        id="edge-01",
        query="What's the weather like today?",
        user_role=UserRole.IC,
        expected_domain="policy",
        ground_truth="OUT OF SCOPE — not a banking question. Should acknowledge and redirect.",
        complexity="simple",
        category="edge_case",
    ),
    EvalCase(
        id="edge-02",
        query="Tell me everything about our bank",
        user_role=UserRole.IC,
        expected_domain="policy",
        ground_truth="TOO BROAD — should ask for clarification or provide a general overview of available topics.",
        complexity="complex",
        category="edge_case",
    ),
    EvalCase(
        id="edge-03",
        query="",
        user_role=UserRole.IC,
        expected_domain="policy",
        ground_truth="EMPTY QUERY — should handle gracefully, ask for input.",
        complexity="simple",
        category="edge_case",
    ),
    EvalCase(
        id="edge-04",
        query="asdfghjkl random gibberish query",
        user_role=UserRole.IC,
        expected_domain="policy",
        ground_truth="UNINTELLIGIBLE — should ask for clarification.",
        complexity="simple",
        category="edge_case",
    ),
    EvalCase(
        id="edge-05",
        query="I need help with my crypto portfolio and NFT investments",
        user_role=UserRole.IC,
        expected_domain="policy",
        ground_truth="OUT OF SCOPE — bank does not offer crypto services. Should redirect appropriately.",
        complexity="moderate",
        category="edge_case",
    ),
]


def get_dataset() -> list[EvalCase]:
    return EVAL_DATASET


def get_dataset_by_category(category: str) -> list[EvalCase]:
    return [c for c in EVAL_DATASET if c.category == category]


def get_dataset_stats() -> dict:
    """Return dataset statistics."""
    categories = {}
    roles = {}
    complexities = {}
    for case in EVAL_DATASET:
        categories[case.category] = categories.get(case.category, 0) + 1
        roles[case.user_role.value] = roles.get(case.user_role.value, 0) + 1
        complexities[case.complexity] = complexities.get(case.complexity, 0) + 1
    return {
        "total": len(EVAL_DATASET),
        "by_category": categories,
        "by_role": roles,
        "by_complexity": complexities,
    }
