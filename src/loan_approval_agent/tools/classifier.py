"""Document classification tool."""

import pdfplumber

from ..models import ClassificationResult
from ..models.documents import DocumentType


def _extract_text(document_path: str) -> str:
    with pdfplumber.open(document_path) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def classify_document(document_path: str) -> ClassificationResult:
    try:
        text = _extract_text(document_path).lower()
    except Exception:
        return ClassificationResult(
            document_type=DocumentType.LOAN_APPLICATION,
            confidence=0.60,
            metadata={"source": document_path},
        )

    credit_keywords = {"fico", "credit score", "credit report", "payment history", "delinquenc"}
    income_keywords = {"w-2", "w2", "pay stub", "paystub", "annual income", "gross income"}
    loan_keywords   = {"loan application", "mortgage application", "loan amount", "property value"}

    if any(kw in text for kw in credit_keywords):
        return ClassificationResult(document_type=DocumentType.CREDIT_REPORT, confidence=0.95, metadata={"source": document_path})
    if any(kw in text for kw in income_keywords):
        return ClassificationResult(document_type=DocumentType.INCOME_VERIFICATION, confidence=0.95, metadata={"source": document_path})
    if any(kw in text for kw in loan_keywords):
        return ClassificationResult(document_type=DocumentType.LOAN_APPLICATION, confidence=0.90, metadata={"source": document_path})

    return ClassificationResult(document_type=DocumentType.LOAN_APPLICATION, confidence=0.60, metadata={"source": document_path})
