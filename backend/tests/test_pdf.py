import pytest
from app.pdf.generator import generate_pdf_report


def test_pdf_report_generation():
    report_data = {
        "exam_overview": "Official recruitment for SSC CGL 2026.",
        "important_dates": "Start: 01-10-2026",
        "eligibility": "Bachelor's Degree",
        "personalized_eligibility": [],
        "vacancies": "12,000",
        "salary": "Pay Level 7",
        "application_fees": "INR 100",
        "required_documents": "Aadhaar, Degree Certificate",
        "selection_process": "Tier I + Tier II",
        "exam_pattern_syllabus": "Maths, Reasoning, English, GK",
        "application_procedure": "Visit ssc.gov.in",
        "faqs": [],
        "important_notes": "Verify official notice.",
        "sources": "ssc.gov.in",
    }
    rec_info = {"name": "SSC CGL 2026", "org": "Staff Selection Commission", "advt_number": "01/2026"}

    pdf_bytes = generate_pdf_report(report_data, rec_info, version="1.0")

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 0
