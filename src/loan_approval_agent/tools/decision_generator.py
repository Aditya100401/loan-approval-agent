"""LLM-based loan decision generator using UiPathChat with structured output."""

from typing import Optional
from pydantic import BaseModel, Field

from ..models import ApplicantData, Decision, PolicyResult
from ..models.decision import DecisionType
from .prompts import DECISION_SYSTEM_PROMPT

# Module-level LLM init — fails silently when running outside UiPath (no credentials)
try:
    from uipath_langchain.chat import UiPathChat
    from langchain_core.messages import SystemMessage, HumanMessage

    _llm = UiPathChat(model="gpt-4.1-mini-2025-04-14", temperature=0)
except Exception:
    _llm = None


class LLMDecisionOutput(BaseModel):
    """Structured output schema for the LLM decision node."""
    decision: str = Field(
        description="Loan decision: GREEN (approved), YELLOW (needs review), or RED (denied)"
    )
    reasoning: str = Field(
        description="Step-by-step analysis for the human reviewer citing specific metrics and rules"
    )
    citations: list[str] = Field(
        default_factory=list,
        description="Specific rules that influenced the decision"
    )
    email_subject: str = Field(
        description="Subject line for the applicant notification email"
    )
    email_body: str = Field(
        description="Complete HTML email body to send to the applicant"
    )


def _build_human_message(applicant_data: ApplicantData) -> str:
    """Build the per-applicant human message from typed state fields."""
    ex = applicant_data.extracted_data

    def fmt_money(v: Optional[float]) -> str:
        return f"${v:,.2f}" if v is not None else "Not found"

    def fmt_pct(v: Optional[float]) -> str:
        return f"{v:.1f}%" if v is not None else "Cannot calculate — missing data"

    anomaly_lines = "\n".join(f"  • {a}" for a in applicant_data.anomalies) or "  None"

    return f"""## Applicant Profile
Name:  {ex.applicant_name or 'Unknown'}
Email: {ex.applicant_email or 'Not provided'}

## Financial Data
  Credit Score:          {ex.credit_score or 'Not found'}
  Annual Income:         {fmt_money(ex.annual_income)}
  Monthly Debt Payments: {fmt_money(ex.monthly_debts)}
  Total Outstanding Debt:{fmt_money(ex.total_debt)}
  Years of Credit History: {ex.credit_history_years if ex.credit_history_years is not None else 'Not found'}
  Delinquent Accounts:   {ex.delinquencies}

## Loan Request
  Loan Amount:    {fmt_money(ex.loan_amount)}
  Property Value: {fmt_money(ex.property_value)}

## Computed Ratios
  DTI Ratio: {fmt_pct(applicant_data.dti_ratio)}
  LTV Ratio: {fmt_pct(applicant_data.ltv_ratio)}

## Anomalies
{anomaly_lines}

Apply the underwriting rules and return your structured decision.
"""


async def generate_llm_decision(
    applicant_data: ApplicantData,
    policies: list[PolicyResult],
) -> Decision:
    """Call the LLM with the applicant's data and return a populated Decision object."""
    if _llm is None:
        raise RuntimeError(
            "UiPathChat is not available — agent must run inside UiPath Orchestrator"
        )

    structured_llm = _llm.with_structured_output(LLMDecisionOutput)
    raw = await structured_llm.ainvoke([
        SystemMessage(content=DECISION_SYSTEM_PROMPT),
        HumanMessage(content=_build_human_message(applicant_data)),
    ])
    result = LLMDecisionOutput.model_validate(raw) if isinstance(raw, dict) else raw

    ex = applicant_data.extracted_data
    return Decision(
        decision=DecisionType(result.decision),
        reasoning=result.reasoning,
        citations=result.citations,
        applicant_name=ex.applicant_name,
        applicant_email=ex.applicant_email,
        credit_score=ex.credit_score,
        dti_ratio=applicant_data.dti_ratio,
        ltv_ratio=applicant_data.ltv_ratio,
        requires_human_review=result.decision != "GREEN",
        email_draft=result.email_body,
    )
