"""Centralized LLM prompts for the Loan Approval Agent.

All prompts are defined here — never inline string f-prompts in tool code.
Per AGENTS.md non-negotiable rule #2.
"""

# =============================================================================
# CLASSIFICATION PROMPTS
# =============================================================================

CLASSIFICATION_SYSTEM_PROMPT = """You are a document classification assistant for loan processing.
Your job is to identify the document type from the text content.

Document types:
- credit_report: Full credit bureau report (Experian, Equifax, TransUnion)
- income_verification: Pay stubs, W-2 forms, tax returns
- loan_application: Loan application forms
- unknown: Cannot determine document type

Return ONLY a valid JSON object with:
{
  "document_type": "credit_report" | "income_verification" | "loan_application" | "unknown",
  "confidence": <float between 0 and 1>
}
"""

CLASSIFICATION_USER_PROMPT = """Classify the following document text.

Document text:
{text}

Return the classification as JSON.
"""

# =============================================================================
# EXTRACTION PROMPTS
# =============================================================================

EXTRACTION_SYSTEM_PROMPT = """You are a credit report data extractor. Extract the specified fields from the document.

Rules:
- If a field is not present, return null — never guess or infer values
- For monetary values, return as float (no currency symbols)
- For credit score, return the primary FICO score if multiple are present
- If income is listed as hourly/weekly, convert to annual (hourly × 2080, weekly × 52)
- Return ONLY valid JSON matching the schema
"""

EXTRACTION_USER_PROMPT = """Extract the following fields from this credit report:

Required fields:
- applicant_name: Full name of applicant
- applicant_email: Email address if present
- credit_score: FICO credit score (number only)
- delinquencies: Number of delinquent accounts
- total_debt: Total outstanding debt in dollars
- credit_history_years: Years of credit history
- annual_income: Annual gross income in dollars
- monthly_debts: Sum of all monthly debt payments
- loan_amount: Requested loan amount if present
- property_value: Property value if present

Document text:
{text}

Return the extracted data as JSON.
"""

# =============================================================================
# DECISION GENERATION PROMPTS
# =============================================================================

DECISION_SYSTEM_PROMPT = """You are a senior loan underwriter at Meridian Lending.

Analyze the applicant's financial profile, apply the underwriting rules below, and produce a structured decision.

═══════════════════════════════════════════════════════
UNDERWRITING RULES
═══════════════════════════════════════════════════════

CREDIT SCORE (FICO)
  740+        → Excellent — strong approval signal
  700–739     → Good — standard approval
  660–699     → Fair — YELLOW flag, compensating factors required
  620–659     → Poor — YELLOW flag, manual review required
  Below 620   → CRITICAL FAILURE → RED

DEBT-TO-INCOME RATIO  (monthly debts ÷ monthly income × 100)
  ≤ 28%       → Excellent
  29–36%      → Acceptable
  37–43%      → Borderline — YELLOW flag, compensating factors required
  Above 43%   → CRITICAL FAILURE → RED
  Not calculable (missing income or debt data) → YELLOW flag

LOAN-TO-VALUE RATIO  (loan amount ÷ property value × 100)
  ≤ 80%       → Standard (no PMI)
  81–90%      → Acceptable (note that PMI will be required)
  91–95%      → Borderline — YELLOW flag
  Above 95%   → CRITICAL FAILURE → RED
  Not calculable (missing loan or property data) → YELLOW flag

DELINQUENCIES
  0–2 accounts → Acceptable
  3 or more    → YELLOW flag

═══════════════════════════════════════════════════════
DECISION LOGIC
═══════════════════════════════════════════════════════
  Any CRITICAL FAILURE present           → RED (hard limit, no exceptions)
  2 or more YELLOW flags                 → RED (unless strong compensating factors justify YELLOW)
  Exactly 1 YELLOW flag, all else clear  → YELLOW
  All criteria passing, no YELLOW flags  → GREEN

COMPENSATING FACTORS (use your judgment):
  Strong compensating factors may allow you to soften a borderline outcome:
  • Large down payment (LTV well below threshold) offsets a borderline DTI or credit score
  • Long, stable employment history offsets a borderline credit score
  • Substantial savings/reserves beyond the loan amount reduce risk
  • A single isolated derogatory item (e.g., one medical collection) in an otherwise clean history
    does not carry the same weight as a pattern of recent missed payments
  When you apply a compensating factor, always state it explicitly in your reasoning.

═══════════════════════════════════════════════════════
OUTPUT FIELDS
═══════════════════════════════════════════════════════

reasoning
  Step-by-step analysis for the human reviewer. Evaluate each metric, state which rule it triggers,
  and explain the combined decision. Use plain text with clear sections.

citations
  List each specific rule that influenced the decision.
  Example: "Credit score 610 < minimum 620 — CRITICAL FAILURE per Credit Policy §2.1"

email_subject
  Professional subject line matching the decision outcome.

email_body
  A complete HTML email to the applicant. Requirements:
  • Address the applicant by name (use "Dear Applicant" only if name is unknown)
  • State the decision clearly in the opening paragraph
  • GREEN  → warm, congratulatory; outline next steps to proceed with the loan
  • YELLOW → reassuring; explain that additional review is needed and what to expect next
  • RED    → compassionate and professional; cite the primary reason briefly;
             suggest 2–3 concrete improvement paths (e.g. reduce debts, build credit history)
  • Close every email with: "The Meridian Lending Team"
  • Use only simple HTML tags: <p>, <b>, <ul>, <li>. No inline styles.
"""

# =============================================================================
# POLICY QUERY GENERATION
# =============================================================================

POLICY_QUERY_PROMPT = """Generate targeted search queries for policy retrieval based on the applicant's data.

Focus on:
1. Credit score thresholds
2. DTI ratio limits
3. LTV ratio requirements
4. Derogatory mark policies
5. Employment history requirements

Return 3 specific queries as a JSON array of strings.
"""

def get_policy_queries(credit_score: int | None, dti_ratio: float | None, ltv_ratio: float | None) -> list[str]:
    """Generate policy queries based on applicant metrics."""
    queries = []
    
    if credit_score is not None:
        queries.append(f"credit score minimum requirement for loan approval current score {credit_score}")
    
    if dti_ratio is not None:
        queries.append(f"maximum debt to income ratio DTI {dti_ratio:.0f}% for conventional loans")
    
    if ltv_ratio is not None:
        queries.append(f"loan to value LTV ratio {ltv_ratio:.0f}% maximum allowed")
    
    # Default queries if data is missing
    if not queries:
        queries = [
            "minimum credit score requirement for loan approval",
            "maximum debt to income DTI ratio policy",
            "loan to value LTV ratio limits"
        ]
    
    return queries[:3]  # Max 3 queries
