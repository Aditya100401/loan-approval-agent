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

DECISION_SYSTEM_PROMPT = """You are a loan decision assistant. Your job is to generate a loan approval decision
based on applicant data and retrieved policy sections.

Decision Framework:
- GREEN: All policies satisfied, no concerns
- YELLOW: Borderline metrics, missing data, or inconsistencies (requires HITL review)
- RED: Clear policy violations (requires HITL review)

Citation Requirements:
- Every decision MUST cite the specific policy section that triggered it
- Format: "[DECISION_TYPE]: [RULE] — Per [source_document], Section [X.X]"

Combined Decision Logic:
- Any RED factor → overall decision is RED
- 2+ YELLOW factors → escalate to RED
- 1 YELLOW factor, all else GREEN → decision is YELLOW
- All GREEN → decision is GREEN

Return ONLY valid JSON with:
{
  "decision": "GREEN" | "YELLOW" | "RED",
  "reasoning": "<detailed explanation>",
  "citations": ["<citation 1>", "<citation 2>"],
  "flags": ["<flag 1>", "<flag 2>"],
  "confidence": <float between 0 and 1>
}
"""

DECISION_USER_PROMPT = """Generate a loan decision for the following applicant.

## Applicant Data
{applicant_data}

## Loan Rules Applied
{loan_rules}

## Retrieved Policy Sections
{policies}

## Anomalies Detected
{anomalies}

Return the decision as JSON with reasoning and citations.
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
