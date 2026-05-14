"""Data validation tool.

Validates extracted data against business rules and calculates metrics.
"""

from ..models import ApplicantData, ExtractedData, RuleResult
from ..models.rules import RuleRegistry


def validate_data(extracted_data: ExtractedData, document_paths: list[str]) -> ApplicantData:
    """Validate extracted data and calculate DTI/LTV metrics.
    
    Args:
        extracted_data: Data extracted from documents
        document_paths: List of source document paths
        
    Returns:
        ApplicantData with validation results and metrics
    """
    # Calculate DTI (Debt-to-Income ratio)
    # DTI = (Monthly Debt Payments / Monthly Income) × 100
    monthly_income = extracted_data.annual_income / 12 if extracted_data.annual_income else 0
    dti_ratio = (extracted_data.monthly_debts / monthly_income * 100) if monthly_income > 0 else 0.0
    
    # Calculate LTV (Loan-to-Value ratio)
    # LTV = (Loan Amount / Property Value) × 100
    ltv_ratio = (extracted_data.loan_amount / extracted_data.property_value * 100) if extracted_data.property_value and extracted_data.property_value > 0 else 0.0
    
    # Run business rules
    registry = RuleRegistry()
    rules = registry.get_all_rules()
    
    rule_results: list[RuleResult] = []
    
    for rule in rules:
        if rule.name == "DTI_RATIO":
            actual_value = dti_ratio
            passed = actual_value <= rule.threshold
        elif rule.name == "LTV_RATIO":
            actual_value = ltv_ratio
            passed = actual_value <= rule.threshold
        elif rule.name == "MIN_CREDIT_SCORE":
            actual_value = extracted_data.credit_score or 0
            passed = actual_value >= rule.threshold
        elif rule.name == "EMPLOYMENT_HISTORY":
            actual_value = extracted_data.credit_history_years or 0
            passed = actual_value >= rule.threshold
        else:
            continue
            
        rule_results.append(RuleResult(
            rule_name=rule.name,
            category=rule.category,
            passed=passed,
            actual_value=actual_value,
            threshold=rule.threshold,
            severity=rule.severity
        ))
    
    # Identify anomalies
    anomalies = []
    if not extracted_data.annual_income:
        anomalies.append("Missing annual income")
    if not extracted_data.property_value:
        anomalies.append("Missing property value")
    if not extracted_data.credit_score:
        anomalies.append("Missing credit score")
    
    return ApplicantData(
        applicant_name=extracted_data.applicant_name,
        applicant_email=extracted_data.applicant_email,
        extracted_data=extracted_data,
        dti_ratio=round(dti_ratio, 2),
        ltv_ratio=round(ltv_ratio, 2),
        rule_results=rule_results,
        document_paths=document_paths,
        anomalies=anomalies
    )
