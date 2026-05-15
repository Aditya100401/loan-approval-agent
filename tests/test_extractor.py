"""Tests for the document extraction tool."""
import pytest
from src.loan_approval_agent.tools.extractor import extract_information


def test_credit_score_extracted(make_pdf):
    path = make_pdf("FICO Score: 720\nAnnual Income: $85,000\nMonthly Debt Payments: $1,500")
    result = extract_information(path, "credit_report")
    assert result.credit_score == 720


def test_annual_income_extracted(make_pdf):
    path = make_pdf("Annual Gross Income: $95,000")
    result = extract_information(path, "credit_report")
    assert result.annual_income == 95000.0


def test_out_of_range_credit_score_rejected(make_pdf):
    path = make_pdf("FICO Score: 999")
    result = extract_information(path, "credit_report")
    assert result.credit_score is None


def test_empty_document_returns_empty(make_pdf):
    path = make_pdf("No financial data here at all.")
    result = extract_information(path, "unknown")
    assert result.credit_score is None
    assert result.annual_income is None
    assert result.monthly_debts is None


def test_loan_fields_extracted(make_pdf):
    path = make_pdf(
        "Loan Amount: $250,000\nProperty Value: $320,000\nMonthly Debt Payments: $1,200"
    )
    result = extract_information(path, "loan_application")
    assert result.loan_amount == 250000.0
    assert result.property_value == 320000.0
    assert result.monthly_debts == 1200.0
