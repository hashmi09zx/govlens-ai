import pytest
from app.agents.report_agent import evaluate_personalized_eligibility


def test_eligibility_exact_qualification_match():
    facts_map = {"eligibility_education": "B.Tech Computer Science"}
    profile = {"education": "B.Tech Computer Science", "age": 25}

    evals = evaluate_personalized_eligibility(facts_map, profile)
    qual_eval = next(e for e in evals if e["requirement"] == "Educational Qualification")
    assert qual_eval["status"] == "Eligible"


def test_eligibility_differing_qualification_needs_verification():
    facts_map = {"eligibility_education": "B.Tech Computer Science"}
    profile = {"education": "MCA", "age": 26}

    evals = evaluate_personalized_eligibility(facts_map, profile)
    qual_eval = next(e for e in evals if e["requirement"] == "Educational Qualification")
    # Differing qualification names MUST yield 'Needs verification', never 'Eligible'
    assert qual_eval["status"] == "Needs verification"


def test_eligibility_missing_profile_does_not_crash():
    facts_map = {"eligibility_education": "Master of Computer Applications"}
    profile = {}

    evals = evaluate_personalized_eligibility(facts_map, profile)
    assert len(evals) == 3
    qual_eval = next(e for e in evals if e["requirement"] == "Educational Qualification")
    assert qual_eval["status"] == "Needs verification"
    assert qual_eval["official"] == "Master of Computer Applications"
