"""Business rules for loan approval decisions."""

from enum import Enum
from typing import Callable, Optional
from pydantic import BaseModel, Field


class RuleCategory(str, Enum):
    """Categories of business rules."""
    CREDIT = "credit"
    INCOME = "income"
    DTI = "dti"
    LTV = "ltv"
    EMPLOYMENT = "employment"
    DOCUMENTATION = "documentation"


class RuleSeverity(str, Enum):
    """Severity level when a rule fails."""
    CRITICAL = "critical"    # Automatic rejection (RED)
    WARNING = "warning"      # Needs review (YELLOW)
    INFO = "info"            # Informational only


class BusinessRule(BaseModel):
    """A single business rule for loan approval."""
    rule_id: str = Field(..., description="Unique identifier (e.g., 'CREDIT_001')")
    name: str = Field(..., description="Human-readable rule name")
    category: RuleCategory = Field(..., description="Rule category")
    description: str = Field(..., description="Full description of the rule")
    severity: RuleSeverity = Field(
        default=RuleSeverity.WARNING,
        description="Severity when rule fails"
    )
    policy_source: str = Field(
        ...,
        description="Policy document citation (e.g., 'credit_policies.pdf, Section 2.1')"
    )
    
    # Threshold values (optional, depends on rule type)
    min_value: Optional[float] = Field(None, description="Minimum acceptable value")
    max_value: Optional[float] = Field(None, description="Maximum acceptable value")
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "rule_id": "CREDIT_001",
                    "name": "Minimum Credit Score",
                    "category": "credit",
                    "description": "Applicant must have a minimum credit score of 620",
                    "severity": "critical",
                    "policy_source": "credit_policies.pdf, Section 2.1",
                    "min_value": 620
                }
            ]
        }
    }


class RuleEvaluation(BaseModel):
    """Result of evaluating a single business rule."""
    rule: BusinessRule = Field(..., description="The rule that was evaluated")
    passed: bool = Field(..., description="Whether the rule passed")
    actual_value: Optional[float] = Field(
        None,
        description="The actual value from the application"
    )
    message: str = Field(..., description="Human-readable result message")
    
    @property
    def failed(self) -> bool:
        return not self.passed


class RuleResult(BaseModel):
    """Simplified rule result for ApplicantData."""
    rule_name: str = Field(..., description="Name of the rule")
    category: RuleCategory = Field(..., description="Rule category")
    passed: bool = Field(..., description="Whether the rule passed")
    actual_value: Optional[float] = Field(None, description="Actual value from application")
    threshold: float = Field(..., description="Threshold value")
    severity: RuleSeverity = Field(default=RuleSeverity.WARNING, description="Rule severity")


class RuleEvaluationResult(BaseModel):
    """Complete result of evaluating all business rules."""
    evaluations: list[RuleEvaluation] = Field(
        default_factory=list,
        description="All rule evaluations"
    )
    
    # Summary counts
    total_rules: int = Field(default=0, description="Total number of rules evaluated")
    passed_count: int = Field(default=0, description="Number of rules passed")
    failed_count: int = Field(default=0, description="Number of rules failed")
    
    # Breakdown by severity
    critical_failures: list[RuleEvaluation] = Field(
        default_factory=list,
        description="Rules with critical severity that failed"
    )
    warnings: list[RuleEvaluation] = Field(
        default_factory=list,
        description="Rules with warning severity that failed"
    )
    
    # Determination
    recommended_decision: str = Field(
        default="YELLOW",
        description="Recommended decision based on rule evaluation"
    )
    
    def add_evaluation(self, evaluation: RuleEvaluation) -> None:
        """Add an evaluation result and update counts."""
        self.evaluations.append(evaluation)
        self.total_rules += 1
        
        if evaluation.passed:
            self.passed_count += 1
        else:
            self.failed_count += 1
            if evaluation.rule.severity == RuleSeverity.CRITICAL:
                self.critical_failures.append(evaluation)
            elif evaluation.rule.severity == RuleSeverity.WARNING:
                self.warnings.append(evaluation)
        
        # Update recommended decision
        self._update_recommendation()
    
    def _update_recommendation(self) -> None:
        """Update recommended decision based on failures."""
        if self.critical_failures:
            self.recommended_decision = "RED"
        elif self.warnings:
            self.recommended_decision = "YELLOW"
        else:
            self.recommended_decision = "GREEN"
    
    @property
    def passed_rules(self) -> list[RuleEvaluation]:
        """Get all passed rule evaluations."""
        return [e for e in self.evaluations if e.passed]
    
    @property
    def failed_rules(self) -> list[RuleEvaluation]:
        """Get all failed rule evaluations."""
        return [e for e in self.evaluations if e.failed]


# =============================================================================
# DEFAULT BUSINESS RULES
# =============================================================================

DEFAULT_RULES: list[BusinessRule] = [
    # Credit Rules
    BusinessRule(
        rule_id="CREDIT_001",
        name="Minimum Credit Score",
        category=RuleCategory.CREDIT,
        description="Applicant must have a minimum credit score of 620",
        severity=RuleSeverity.CRITICAL,
        policy_source="credit_policies.pdf, Section 2.1",
        min_value=620
    ),
    BusinessRule(
        rule_id="CREDIT_002",
        name="Preferred Credit Score",
        category=RuleCategory.CREDIT,
        description="Credit score of 720 or higher is preferred for best rates",
        severity=RuleSeverity.INFO,
        policy_source="credit_policies.pdf, Section 2.2",
        min_value=720
    ),
    BusinessRule(
        rule_id="CREDIT_003",
        name="Maximum Delinquencies",
        category=RuleCategory.CREDIT,
        description="No more than 2 delinquent accounts in the past 24 months",
        severity=RuleSeverity.WARNING,
        policy_source="credit_policies.pdf, Section 3.1",
        max_value=2
    ),
    
    # DTI Rules
    BusinessRule(
        rule_id="DTI_001",
        name="Maximum DTI Ratio",
        category=RuleCategory.DTI,
        description="Debt-to-Income ratio must not exceed 43%",
        severity=RuleSeverity.CRITICAL,
        policy_source="dti_standards.pdf, Section 1.1",
        max_value=43.0
    ),
    BusinessRule(
        rule_id="DTI_002",
        name="Preferred DTI Ratio",
        category=RuleCategory.DTI,
        description="DTI ratio of 36% or lower is preferred",
        severity=RuleSeverity.INFO,
        policy_source="dti_standards.pdf, Section 1.2",
        max_value=36.0
    ),
    BusinessRule(
        rule_id="DTI_003",
        name="High DTI Threshold",
        category=RuleCategory.DTI,
        description="DTI between 37-43% requires compensating factors",
        severity=RuleSeverity.WARNING,
        policy_source="dti_standards.pdf, Section 1.2",
        min_value=37.0,
        max_value=43.0
    ),
    
    # LTV Rules
    BusinessRule(
        rule_id="LTV_001",
        name="Maximum LTV Ratio",
        category=RuleCategory.LTV,
        description="Loan-to-Value ratio must not exceed 80%",
        severity=RuleSeverity.WARNING,
        policy_source="underwriting_guidelines.pdf, Section 4.1",
        max_value=80.0
    ),
    BusinessRule(
        rule_id="LTV_002",
        name="Preferred LTV Ratio",
        category=RuleCategory.LTV,
        description="LTV ratio of 70% or lower is preferred",
        severity=RuleSeverity.INFO,
        policy_source="underwriting_guidelines.pdf, Section 4.2",
        max_value=70.0
    ),
    
    # Employment Rules
    BusinessRule(
        rule_id="EMP_001",
        name="Minimum Employment History",
        category=RuleCategory.EMPLOYMENT,
        description="Minimum 2 years of employment history required",
        severity=RuleSeverity.WARNING,
        policy_source="underwriting_guidelines.pdf, Section 5.1",
        min_value=2
    ),
    BusinessRule(
        rule_id="EMP_002",
        name="Stable Employment",
        category=RuleCategory.EMPLOYMENT,
        description="3 or more years at current employer is preferred",
        severity=RuleSeverity.INFO,
        policy_source="underwriting_guidelines.pdf, Section 5.2",
        min_value=3
    ),
    
    # Documentation Rules
    BusinessRule(
        rule_id="DOC_001",
        name="Income Documentation",
        category=RuleCategory.DOCUMENTATION,
        description="Income verification document must be provided",
        severity=RuleSeverity.WARNING,
        policy_source="underwriting_guidelines.pdf, Section 6.1"
    ),
    BusinessRule(
        rule_id="DOC_002",
        name="Credit Report Recency",
        category=RuleCategory.DOCUMENTATION,
        description="Credit report must be within 90 days",
        severity=RuleSeverity.WARNING,
        policy_source="credit_policies.pdf, Section 1.1"
    ),
]


def get_rules_by_category(category: RuleCategory) -> list[BusinessRule]:
    """Get all rules for a specific category."""
    return [rule for rule in DEFAULT_RULES if rule.category == category]


def get_rules_by_severity(severity: RuleSeverity) -> list[BusinessRule]:
    """Get all rules with a specific severity."""
    return [rule for rule in DEFAULT_RULES if rule.severity == severity]


class RuleRegistry:
    """Registry for accessing and managing business rules."""
    
    def __init__(self, rules: Optional[list[BusinessRule]] = None):
        self._rules = rules or DEFAULT_RULES
    
    def get_all_rules(self) -> list[BusinessRule]:
        """Get all registered rules."""
        return self._rules
    
    def get_rule_by_id(self, rule_id: str) -> Optional[BusinessRule]:
        """Get a specific rule by its ID."""
        for rule in self._rules:
            if rule.rule_id == rule_id:
                return rule
        return None
    
    def get_rules_by_category(self, category: RuleCategory) -> list[BusinessRule]:
        """Get all rules for a category."""
        return [r for r in self._rules if r.category == category]
    
    def get_critical_rules(self) -> list[BusinessRule]:
        """Get all critical severity rules."""
        return [r for r in self._rules if r.severity == RuleSeverity.CRITICAL]
