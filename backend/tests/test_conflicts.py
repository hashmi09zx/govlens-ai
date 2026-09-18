import pytest
from app.agents.conflict_agent import resolve_fact_conflict


def test_conflict_resolution_official_vs_blog():
    facts = [
        {
            "field": "application_deadline",
            "value": "15 Oct 2026",
            "source": "https://bpsc.bih.nic.in/notice.pdf",
            "source_type": "official_notification",
            "source_date": "2026-09-01",
            "confidence": 0.95,
        },
        {
            "field": "application_deadline",
            "value": "20 Oct 2026",
            "source": "https://somejobblog.com/bpsc-date",
            "source_type": "secondary",
            "source_date": "2026-09-02",
            "confidence": 0.60,
        },
    ]

    conflict = resolve_fact_conflict("application_deadline", facts)
    assert conflict.resolved is True
    assert conflict.resolved_value == "15 Oct 2026"


def test_conflict_resolution_official_vs_corrigendum():
    facts = [
        {
            "field": "application_deadline",
            "value": "15 Oct 2026",
            "source": "https://bpsc.bih.nic.in/notification.pdf",
            "source_type": "official_notification",
            "source_date": "2026-09-01",
            "confidence": 0.95,
        },
        {
            "field": "application_deadline",
            "value": "20 Oct 2026",
            "source": "https://bpsc.bih.nic.in/corrigendum-1.pdf",
            "source_type": "corrigendum",
            "source_date": "2026-09-10",
            "confidence": 0.99,
        },
    ]

    conflict = resolve_fact_conflict("application_deadline", facts)
    assert conflict.resolved is True
    assert conflict.resolved_value == "20 Oct 2026"
