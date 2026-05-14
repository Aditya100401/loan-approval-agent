"""Applicant and extracted data models."""

from typing import Optional
from pydantic import BaseModel, Field, field_validator

from .rules import RuleResult


class ExtractedData(BaseModel):
    """Data extracted from loan documents."""
    # Personal info
    applicant_name: Optional[str] = Field(None, description="Full name of applicant")
    applicant_email: Optional[str] = Field(None, description="Email address")
    
    # Credit data
    credit_score: Optional[int] = Field(
        None, 
        ge=300, 
        le=850,
        description="FICO credit score (300-850)"
    )
    delinquencies: int = Field(
        default=0,
        ge=0,
        description="Number of delinquent accounts"
    )
    total_debt: Optional[float] = Field(
        None,
        ge=0,
        description="Total outstanding debt in dollars"
    )
    credit_history_years: Optional[int] = Field(
        None,
        ge=0,
        description="Years of credit history"
    )
    
    # Income data
    annual_income: Optional[float] = Field(
        None,
        ge=0,
        description="Annual gross income in dollars"
    )
    employer: Optional[str] = Field(None, description="Current employer name")
    employment_years: Optional[int] = Field(
        None,
        ge=0,
        description="Years at current employer"
    )
    
    # Loan data
    loan_amount: Optional[float] = Field(
        None,
        ge=0,
        description="Requested loan amount in dollars"
    )
    loan_type: Optional[str] = Field(None, description="Type of loan (e.g., mortgage, auto)")
    property_value: Optional[float] = Field(
        None,
        ge=0,
        description="Property value for secured loans"
    )
    down_payment: Optional[float] = Field(
        None,
        ge=0,
        description="Down payment amount"
    )
    
    # Monthly debts (extracted or calculated)
    monthly_debts: Optional[float] = Field(
        None,
        ge=0,
        description="Sum of monthly debt payments"
    )
    
    @property
    def monthly_income(self) -> Optional[float]:
        """Calculate monthly income from annual."""
        return self.annual_income / 12 if self.annual_income else None


class ApplicantData(BaseModel):
    """Complete applicant profile for loan decision."""
    applicant_name: Optional[str] = Field(None, description="Full name of applicant")
    applicant_email: Optional[str] = Field(None, description="Email address")
    extracted_data: ExtractedData
    
    # Source documents
    document_paths: list[str] = Field(
        default_factory=list,
        description="List of source documents processed"
    )
    
    # Calculated metrics
    dti_ratio: Optional[float] = Field(
        None,
        description="Debt-to-Income ratio as percentage"
    )
    ltv_ratio: Optional[float] = Field(
        None,
        description="Loan-to-Value ratio as percentage"
    )
    
    # Validation results
    rule_results: list[RuleResult] = Field(
        default_factory=list,
        description="Results of business rule validation"
    )
    
    # Anomalies
    anomalies: list[str] = Field(
        default_factory=list,
        description="Detected data anomalies or inconsistencies"
    )
    
    @field_validator("dti_ratio")
    @classmethod
    def validate_dti(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and (v < 0 or v > 100):
            raise ValueError("DTI ratio must be between 0 and 100")
        return v
    
    @field_validator("ltv_ratio")
    @classmethod
    def validate_ltv(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v < 0:
            raise ValueError("LTV ratio cannot be negative")
        return v
