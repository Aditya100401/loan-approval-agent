"""Tests for the document classification tool."""
import pytest
from src.loan_approval_agent.tools.classifier import classify_document
from src.loan_approval_agent.models.documents import DocumentType


def test_credit_report_classified(make_pdf):
    path = make_pdf("FICO Score: 720\nCredit Report\nPayment History: Excellent")
    result = classify_document(path)
    assert result.document_type == DocumentType.CREDIT_REPORT
    assert result.confidence >= 0.9


def test_income_verification_classified(make_pdf):
    path = make_pdf("W-2 Form\nAnnual Income: $85,000\nGross Income: $90,000")
    result = classify_document(path)
    assert result.document_type == DocumentType.INCOME_VERIFICATION
    assert result.confidence >= 0.9


def test_loan_application_classified(make_pdf):
    path = make_pdf("Loan Application\nLoan Amount: $250,000\nProperty Value: $320,000")
    result = classify_document(path)
    assert result.document_type == DocumentType.LOAN_APPLICATION
    assert result.confidence >= 0.8


def test_unknown_falls_back_to_loan_application(make_pdf):
    path = make_pdf("Random text with no relevant keywords.")
    result = classify_document(path)
    assert result.document_type == DocumentType.LOAN_APPLICATION
    assert result.confidence == pytest.approx(0.60)
