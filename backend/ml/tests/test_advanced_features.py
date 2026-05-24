from __future__ import annotations

from backend.ml.advanced_features import extract_remote_restrictions
from backend.ml.feature_extractor import extract_features


def test_extracts_allowed_country_timezone_and_authorization() -> None:
    text = """
    Fully remote, Canada only. Must be authorized to work in Canada.
    EST hours required for customer coverage.
    """
    extracted = extract_features(text)
    restrictions = extract_remote_restrictions(text, extracted)

    assert "Canada" in restrictions.allowed_countries
    assert restrictions.timezone_requirements
    assert restrictions.work_authorization
    assert restrictions.source_snippets


def test_extracts_hybrid_language() -> None:
    text = "Remote but office required twice weekly. Must commute to New York."
    extracted = extract_features(text)
    restrictions = extract_remote_restrictions(text, extracted)

    assert restrictions.onsite_or_hybrid_requirement
    assert restrictions.source_snippets


def test_flexible_work_options_do_not_create_hybrid_requirement() -> None:
    text = "Benefits include flexible work options (office, hybrid or remote)."
    extracted = extract_features(text)
    restrictions = extract_remote_restrictions(text, extracted)

    assert extracted.remote_type == "Flexible remote option"
    assert restrictions.onsite_or_hybrid_requirement is None


def test_choose_remote_hybrid_or_office_is_optional() -> None:
    text = "Employees can choose remote, hybrid, or office options based on preference."
    extracted = extract_features(text)
    restrictions = extract_remote_restrictions(text, extracted)

    assert extracted.remote_type == "Flexible remote option"
    assert restrictions.onsite_or_hybrid_requirement is None


def test_ignores_url_encoded_remote_filter_noise() -> None:
    text = """
    Browser Title: Jobs on LinkedIn
    on-site%20or%20hybrid%20or%20remote&origin=PREFERENCES_LANDING&originToLandingJobPostings=4414132884%2C4418185205
    Remote in Ontario, Canada99+ results How promoted jobs are ranked Applied Machine Learning Intern

    About the job
    This internship can be remote in Ontario, Canada. You will build machine learning tools with the engineering team.
    """
    extracted = extract_features(text)
    restrictions = extract_remote_restrictions(text, extracted)

    all_text = " ".join([restrictions.onsite_or_hybrid_requirement or "", *restrictions.ambiguous_location_language, *restrictions.source_snippets])
    assert "%20" not in all_text
    assert "origin=" not in all_text


def test_ignores_plain_linkedin_search_filter_noise() -> None:
    text = """
    Browser Title: Jobs on LinkedIn
    on-site or hybrid or remote in Ontario, Canada99+ results · How promoted jobs are rankedApplied Machine Learning Intern (Verified job)

    About the job
    This internship can be remote in Ontario, Canada. You will build machine learning tools with the engineering team.
    """
    extracted = extract_features(text)
    restrictions = extract_remote_restrictions(text, extracted)

    all_text = " ".join([restrictions.onsite_or_hybrid_requirement or "", *restrictions.ambiguous_location_language, *restrictions.source_snippets])
    assert extracted.remote_type == "Remote unclear"
    assert restrictions.onsite_or_hybrid_requirement is None
    assert "99+ results" not in all_text
    assert "promoted jobs" not in all_text.lower()
    assert "remote in Ontario, Canada" in all_text
