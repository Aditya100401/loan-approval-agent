"""Pydantic models for structured data."""

from .documents import DocumentType, ClassificationResult
from .applicant import ApplicantData, ExtractedData
from .decision import Decision, DecisionType, PolicyResult
from .rules import (
    RuleCategory,
    RuleSeverity,
    BusinessRule,
    RuleEvaluation,
    RuleEvaluationResult,
    RuleResult,
    RuleRegistry,
    DEFAULT_RULES,
    get_rules_by_category,
    get_rules_by_severity,
)

__all__ = [
    # Documents
    "DocumentType",
    "ClassificationResult",
    # Applicant
    "ApplicantData",
    "ExtractedData",
    # Decision
    "Decision",
    "DecisionType",
    "PolicyResult",
    # Rules
    "RuleCategory",
    "RuleSeverity",
    "BusinessRule",
    "RuleEvaluation",
    "RuleEvaluationResult",
    "RuleResult",
    "RuleRegistry",
    "DEFAULT_RULES",
    "get_rules_by_category",
    "get_rules_by_severity",
]
