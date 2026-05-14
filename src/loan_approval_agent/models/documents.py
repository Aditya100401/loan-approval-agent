"""Document classification models."""

from enum import Enum
from pydantic import BaseModel, Field


class DocumentType(str, Enum):
    """Supported document types for loan processing."""
    CREDIT_REPORT = "credit_report"
    INCOME_VERIFICATION = "income_verification"
    LOAN_APPLICATION = "loan_application"
    UNKNOWN = "unknown"


class ClassificationResult(BaseModel):
    """Result of document classification."""
    document_type: DocumentType = Field(
        ...,
        description="The classified document type"
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score between 0 and 1"
    )
    metadata: dict = Field(
        default_factory=dict,
        description="Additional metadata about the classification"
    )
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "document_type": "credit_report",
                    "confidence": 0.95,
                    "metadata": {"source": "document.pdf"}
                }
            ]
        }
    }
