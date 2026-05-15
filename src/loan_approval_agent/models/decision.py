"""Decision and policy models."""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field

from .rules import RuleEvaluationResult


class DecisionType(str, Enum):
    """Loan decision outcomes."""
    GREEN = "GREEN"      # Approved - all policies satisfied
    YELLOW = "YELLOW"    # Conditional - needs review or more info
    RED = "RED"          # Denied - policy violations


class PolicyResult(BaseModel):
    """A retrieved policy section from Context Grounding."""
    text: str = Field(..., description="Policy text content")
    source: str = Field(
        ...,
        description="Source document and section (e.g., 'dti_standards.pdf, Section 1.2')"
    )
    score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Relevance score from Context Grounding"
    )


class Decision(BaseModel):
    """Final loan approval decision."""
    decision: DecisionType = Field(..., description="The decision outcome")
    reasoning: str = Field(
        ...,
        description="Detailed explanation of the decision"
    )
    citations: list[str] = Field(
        default_factory=list,
        description="Policy citations supporting the decision"
    )
    
    # Rule evaluation results
    rule_evaluation: Optional[RuleEvaluationResult] = Field(
        None,
        description="Complete business rule evaluation results"
    )
    
    # Applicant reference
    applicant_name: Optional[str] = Field(None, description="Applicant name")
    applicant_email: Optional[str] = Field(None, description="Applicant email for notification")
    
    # Key metrics that influenced decision
    credit_score: Optional[int] = Field(None, description="Credit score used in decision")
    dti_ratio: Optional[float] = Field(None, description="DTI ratio used in decision")
    ltv_ratio: Optional[float] = Field(None, description="LTV ratio used in decision")
    
    # LLM-generated email draft for the applicant
    email_draft: Optional[str] = Field(
        None,
        description="HTML email body drafted by the LLM to send to the applicant"
    )

    # Human review status
    requires_human_review: bool = Field(
        default=False,
        description="Whether this decision needs HITL approval"
    )
    human_review_status: Optional[str] = Field(
        None,
        description="Status of human review (pending, approved, rejected)"
    )
    human_review_comments: Optional[str] = Field(
        None,
        description="Comments from human reviewer"
    )
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "decision": "GREEN",
                    "reasoning": "Applicant meets all policy requirements. Credit score of 750 exceeds minimum of 620. DTI of 24% is below maximum of 43%.",
                    "citations": [
                        "credit_policies.pdf, Section 2.1: Minimum credit score 620",
                        "dti_standards.pdf, Section 1.2: Maximum DTI 43%"
                    ],
                    "applicant_name": "John Doe",
                    "credit_score": 750,
                    "dti_ratio": 24.0,
                    "requires_human_review": False
                }
            ]
        }
    }
