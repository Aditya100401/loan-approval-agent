"""Document extraction tool."""

import re
from ..models import ExtractedData


def _parse_number(s: str) -> float:
    return float(s.replace(",", "").replace("$", "").strip())


def _find(patterns: list[str], text: str) -> str | None:
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


def extract_information(document_path: str, document_type: str) -> ExtractedData:
    try:
        from docling.document_converter import DocumentConverter
        converter = DocumentConverter()
        result = converter.convert(document_path)
        text = result.document.export_to_markdown()
    except Exception:
        return ExtractedData()

    def num(patterns: list[str]) -> float | None:
        v = _find(patterns, text)
        try:
            return _parse_number(v) if v else None
        except ValueError:
            return None

    def integer(patterns: list[str]) -> int | None:
        v = num(patterns)
        return int(v) if v is not None else None

    credit_score = integer([
        r'(?:fico|credit\s+score)[:\s]+(\d{3})',
        r'\bscore[:\s]+(\d{3})\b',
        r'(\d{3})\s+(?:fico\s+)?score',
    ])
    annual_income = num([
        r'annual\s+(?:gross\s+)?income[:\s]+\$?([\d,]+)',
        r'gross\s+income[:\s]+\$?([\d,]+)',
        r'yearly\s+income[:\s]+\$?([\d,]+)',
        r'total\s+income[:\s]+\$?([\d,]+)',
    ])
    monthly_debts = num([
        r'monthly\s+(?:debt\s+)?payments?[:\s]+\$?([\d,]+)',
        r'total\s+monthly\s+(?:obligations?|debts?)[:\s]+\$?([\d,]+)',
        r'monthly\s+obligations?[:\s]+\$?([\d,]+)',
    ])
    loan_amount = num([
        r'(?:loan|mortgage)\s+amount[:\s]+\$?([\d,]+)',
        r'amount\s+requested[:\s]+\$?([\d,]+)',
        r'requested\s+(?:loan\s+)?amount[:\s]+\$?([\d,]+)',
    ])
    property_value = num([
        r'property\s+value[:\s]+\$?([\d,]+)',
        r'appraised\s+value[:\s]+\$?([\d,]+)',
        r'estimated\s+value[:\s]+\$?([\d,]+)',
        r'home\s+value[:\s]+\$?([\d,]+)',
    ])
    total_debt = num([
        r'total\s+(?:outstanding\s+)?debt[:\s]+\$?([\d,]+)',
        r'total\s+balance[:\s]+\$?([\d,]+)',
    ])
    delinquencies_raw = integer([
        r'delinquent\s+accounts?[:\s]+(\d+)',
        r'(?:number\s+of\s+)?delinquenc\w*[:\s]+(\d+)',
        r'late\s+payments?[:\s]+(\d+)',
    ])
    credit_history = integer([
        r'credit\s+history[:\s]+(\d+)\s+years?',
        r'oldest\s+account[:\s]+(\d+)\s+years?',
        r'(\d+)\s+years?\s+of\s+credit',
    ])
    name_raw = _find([
        r'(?:applicant|borrower|prepared\s+for|name)[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',
    ], text)

    return ExtractedData(
        applicant_name=name_raw,
        credit_score=credit_score if credit_score and 300 <= credit_score <= 850 else None,
        annual_income=annual_income,
        monthly_debts=monthly_debts,
        loan_amount=loan_amount,
        property_value=property_value,
        total_debt=total_debt,
        delinquencies=delinquencies_raw or 0,
        credit_history_years=credit_history,
    )
