"""Decision generation tool using LLM."""

import json
from typing import Optional

from ..models import ApplicantData, Decision, DecisionType, PolicyResult, RuleEvaluationResult
from ..models.rules import (
    BusinessRule,
    RuleEvaluation,
    RuleSeverity,
    RuleCategory,
    DEFAULT_RULES,
)
from ..config import get_settings
from .prompts import DECISION_SYSTEM_PROMPT, DECISION_USER_PROMPT


# =============================================================================
# LOAN RULES FROM DOCS/LOAN_RULES.MD
# =============================================================================

# Credit Score Thresholds
CREDIT_EXCELLENT = 740
CREDIT_GOOD = 700
CREDIT_FAIR = 660
CREDIT_POOR = 620
CREDIT_UNACCEPTABLE = 620

# DTI Thresholds
DTI_EXCELLENT = 28
DTI_ACCEPTABLE = 36
DTI_BORDERLINE = 43

# LTV Thresholds
LTV_STANDARD = 80
LTV_ACCEPTABLE = 90
LTV_BORDERLINE = 95


def evaluate_credit_score(score: Optional[int]) -> RuleEvaluation:
    """Evaluate credit score against policy thresholds."""
    rule = BusinessRule(
        rule_id="CREDIT_001",
        name="Minimum Credit Score",
        category=RuleCategory.CREDIT,
        description="Applicant must have a minimum credit score of 620",
        severity=RuleSeverity.CRITICAL,
        policy_source="credit_policies.pdf, Section 2.1",
        min_value=620
    )
    
    if score is None:
        return RuleEvaluation(
            rule=rule,
            passed=False,
            actual_value=None,
            message="Credit score not found in report"
        )
    
    if score >= CREDIT_EXCELLENT:
        return RuleEvaluation(
            rule=rule,
            passed=True,
            actual_value=score,
            message=f"Excellent credit score: {score} (≥740)"
        )
    elif score >= CREDIT_GOOD:
        return RuleEvaluation(
            rule=rule,
            passed=True,
            actual_value=score,
            message=f"Good credit score: {score} (700-739)"
        )
    elif score >= CREDIT_FAIR:
        return RuleEvaluation(
            rule=rule,
            passed=True,
            actual_value=score,
            message=f"Fair credit score: {score} (660-699), may require compensating factors"
        )
    elif score >= CREDIT_POOR:
        return RuleEvaluation(
            rule=rule,
            passed=True,
            actual_value=score,
            message=f"Poor credit score: {score} (620-659), requires manual review",
            # Note: passes rule but should trigger YELLOW
        )
    else:
        return RuleEvaluation(
            rule=rule,
            passed=False,
            actual_value=score,
            message=f"RED: Credit score {score} is below minimum 620 — Per credit_policies.pdf, Section 2.1"
        )


def evaluate_dti(dti: Optional[float]) -> RuleEvaluation:
    """Evaluate DTI ratio against policy thresholds."""
    rule = BusinessRule(
        rule_id="DTI_001",
        name="Maximum DTI Ratio",
        category=RuleCategory.DTI,
        description="Debt-to-Income ratio must not exceed 43%",
        severity=RuleSeverity.CRITICAL,
        policy_source="dti_standards.pdf, Section 1.1",
        max_value=43.0
    )
    
    if dti is None:
        return RuleEvaluation(
            rule=rule,
            passed=False,
            actual_value=None,
            message="DTI cannot be calculated — missing income or debt data"
        )
    
    if dti <= DTI_EXCELLENT:
        return RuleEvaluation(
            rule=rule,
            passed=True,
            actual_value=dti,
            message=f"Excellent DTI: {dti:.1f}% (≤28%)"
        )
    elif dti <= DTI_ACCEPTABLE:
        return RuleEvaluation(
            rule=rule,
            passed=True,
            actual_value=dti,
            message=f"Acceptable DTI: {dti:.1f}% (29-36%)"
        )
    elif dti <= DTI_BORDERLINE:
        return RuleEvaluation(
            rule=rule,
            passed=True,
            actual_value=dti,
            message=f"YELLOW: DTI {dti:.1f}% in borderline range (37-43%), requires compensating factors — Per dti_standards.pdf, Section 1.2"
        )
    else:
        return RuleEvaluation(
            rule=rule,
            passed=False,
            actual_value=dti,
            message=f"RED: DTI {dti:.1f}% exceeds maximum 43% — Per dti_standards.pdf, Section 1.1"
        )


def evaluate_ltv(ltv: Optional[float]) -> RuleEvaluation:
    """Evaluate LTV ratio against policy thresholds."""
    rule = BusinessRule(
        rule_id="LTV_001",
        name="Maximum LTV Ratio",
        category=RuleCategory.LTV,
        description="Loan-to-Value ratio must not exceed 80% for standard approval",
        severity=RuleSeverity.WARNING,
        policy_source="underwriting_guidelines.pdf, Section 4.1",
        max_value=80.0
    )
    
    if ltv is None:
        return RuleEvaluation(
            rule=rule,
            passed=False,
            actual_value=None,
            message="LTV cannot be calculated — missing loan amount or property value"
        )
    
    if ltv <= LTV_STANDARD:
        return RuleEvaluation(
            rule=rule,
            passed=True,
            actual_value=ltv,
            message=f"Standard LTV: {ltv:.1f}% (≤80%), no PMI required"
        )
    elif ltv <= LTV_ACCEPTABLE:
        return RuleEvaluation(
            rule=rule,
            passed=True,
            actual_value=ltv,
            message=f"Acceptable LTV: {ltv:.1f}% (81-90%), PMI required"
        )
    elif ltv <= LTV_BORDERLINE:
        return RuleEvaluation(
            rule=rule,
            passed=True,
            actual_value=ltv,
            message=f"YELLOW: LTV {ltv:.1f}% in borderline range (91-95%) — Per underwriting_guidelines.pdf, Section 4.1"
        )
    else:
        return RuleEvaluation(
            rule=rule,
            passed=False,
            actual_value=ltv,
            message=f"RED: LTV {ltv:.1f}% exceeds maximum 95% — Per underwriting_guidelines.pdf, Section 4.1"
        )


def evaluate_all_rules(applicant_data: ApplicantData) -> RuleEvaluationResult:
    """Evaluate all business rules for an applicant."""
    result = RuleEvaluationResult()
    extracted = applicant_data.extracted_data
    
    # Credit score evaluation
    credit_eval = evaluate_credit_score(extracted.credit_score)
    result.add_evaluation(credit_eval)
    
    # DTI evaluation
    dti_eval = evaluate_dti(applicant_data.dti_ratio)
    result.add_evaluation(dti_eval)
    
    # LTV evaluation
    ltv_eval = evaluate_ltv(applicant_data.ltv_ratio)
    result.add_evaluation(ltv_eval)
    
    # Delinquencies evaluation
    if extracted.delinquencies > 2:
        delinq_rule = BusinessRule(
            rule_id="CREDIT_003",
            name="Maximum Delinquencies",
            category=RuleCategory.CREDIT,
            description="No more than 2 delinquent accounts in the past 24 months",
            severity=RuleSeverity.WARNING,
            policy_source="credit_policies.pdf, Section 3.1",
            max_value=2
        )
        result.add_evaluation(RuleEvaluation(
            rule=delinq_rule,
            passed=False,
            actual_value=extracted.delinquencies,
            message=f"YELLOW: {extracted.delinquencies} delinquent accounts exceeds maximum of 2 — Per credit_policies.pdf, Section 3.1"
        ))
    
    # Check for anomalies
    for anomaly in applicant_data.anomalies:
        anomaly_rule = BusinessRule(
            rule_id="DATA_001",
            name="Data Anomaly",
            category=RuleCategory.DOCUMENTATION,
            description="Data validation anomaly detected",
            severity=RuleSeverity.WARNING,
            policy_source="underwriting_guidelines.pdf, Section 6.1"
        )
        result.add_evaluation(RuleEvaluation(
            rule=anomaly_rule,
            passed=False,
            actual_value=None,
            message=f"YELLOW: Data anomaly — {anomaly}"
        ))
    
    return result


def generate_decision(
    applicant_data: ApplicantData,
    policies: list[PolicyResult]
) -> Decision:
    """Generate a loan approval decision.
    
    Args:
        applicant_data: Validated applicant data with metrics
        policies: Retrieved policy sections from Context Grounding
        
    Returns:
        Decision with GREEN/YELLOW/RED determination, reasoning, and citations
    """
    settings = get_settings()
    extracted = applicant_data.extracted_data
    
    # Evaluate all business rules
    rule_result = evaluate_all_rules(applicant_data)
    
    # Determine decision based on rule evaluation
    if rule_result.critical_failures:
        decision_type = DecisionType.RED
    elif rule_result.warnings or rule_result.failed_count > 0:
        decision_type = DecisionType.YELLOW
    else:
        decision_type = DecisionType.GREEN
    
    # Build reasoning
    reasoning_parts = []
    citations = []
    flags = []
    
    for eval in rule_result.passed_rules:
        reasoning_parts.append(f"✓ {eval.message}")
    
    for eval in rule_result.failed_rules:
        reasoning_parts.append(f"✗ {eval.message}")
        if eval.rule.policy_source:
            citations.append(eval.rule.policy_source)
        flags.append(eval.rule.rule_id)
    
    # Add policy citations
    for policy in policies[:3]:  # Top 3 policies
        if policy.source not in citations:
            citations.append(policy.source)
    
    reasoning = "\n".join(reasoning_parts)
    
    # Calculate confidence
    confidence = 1.0 if decision_type == DecisionType.GREEN else 0.7 if decision_type == DecisionType.YELLOW else 0.5
    
    return Decision(
        decision=decision_type,
        reasoning=reasoning,
        citations=citations,
        rule_evaluation=rule_result,
        applicant_name=extracted.applicant_name,
        applicant_email=extracted.applicant_email,
        credit_score=extracted.credit_score,
        dti_ratio=applicant_data.dti_ratio,
        ltv_ratio=applicant_data.ltv_ratio,
        requires_human_review=decision_type != DecisionType.GREEN
    )
