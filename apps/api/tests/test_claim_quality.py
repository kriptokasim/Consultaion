"""Tests for claim quality filter — validates claim cleaning and filtering logic."""

from reporting.claim_quality import clean_claim_text, filter_claims, is_valid_semantic_claim


class TestCleanClaimText:
    def test_strips_bold_markdown(self):
        result = clean_claim_text("**Validate Product-Market Fit (PMF)**")
        assert "**" not in result
        assert "Validate Product-Market Fit (PMF)" == result

    def test_strips_heading_markdown(self):
        result = clean_claim_text("## Key Takeaway")
        assert "##" not in result
        assert result == "Key Takeaway"

    def test_strips_bullet_prefix(self):
        result = clean_claim_text("- Focus on unit economics first")
        assert result == "Focus on unit economics first"

    def test_strips_numbered_prefix(self):
        result = clean_claim_text("1. Build your data room early")
        assert result == "Build your data room early"

    def test_strips_backtick_code(self):
        result = clean_claim_text("`API key` management is critical for security")
        assert "`" not in result
        assert "API key management is critical for security" == result

    def test_preserves_clean_text(self):
        text = "VC readiness requires evidence of repeatable demand."
        assert clean_claim_text(text) == text

    def test_collapses_whitespace(self):
        result = clean_claim_text("Too   many    spaces   here")
        assert result == "Too many spaces here"


class TestIsValidSemanticClaim:
    def test_rejects_intro_phrase(self):
        assert is_valid_semantic_claim("Here's a structured roadmap to get your SaaS VC-ready.") is False

    def test_rejects_step_by_step_intro(self):
        assert is_valid_semantic_claim("Here's a step-by-step guide.") is False

    def test_rejects_consider_the_following(self):
        assert is_valid_semantic_claim("Consider the following points about market fit") is False

    def test_rejects_short_fragment(self):
        assert is_valid_semantic_claim("Team is key") is False

    def test_rejects_heading_only(self):
        assert is_valid_semantic_claim("Product-Market Fit:") is False

    def test_rejects_title_case_heading(self):
        assert is_valid_semantic_claim("Key Findings") is False

    def test_rejects_empty_string(self):
        assert is_valid_semantic_claim("") is False

    def test_rejects_markdown_artifact_only(self):
        assert is_valid_semantic_claim("**") is False

    def test_rejects_ellipsis(self):
        assert is_valid_semantic_claim("...") is False

    def test_accepts_valid_proposition(self):
        assert is_valid_semantic_claim("VC readiness requires evidence of repeatable demand, not only product completeness.") is True

    def test_accepts_specific_saas_claim(self):
        assert is_valid_semantic_claim("A SaaS startup should show scalable acquisition economics before fundraising.") is True

    def test_accepts_enterprise_claim(self):
        assert is_valid_semantic_claim("Enterprise readiness depends on security, auditability, and data-retention controls.") is True

    def test_rejects_must_include_slides(self):
        assert is_valid_semantic_claim("Must-Include Slides for your pitch deck presentation") is False

    def test_rejects_comprehensive_intro_phrases(self):
        assert is_valid_semantic_claim("Here's a comprehensive yet concise draft of the policy framework.") is False
        assert is_valid_semantic_claim("This report synthesizes the key insights.") is False


class TestFilterClaims:
    def test_filters_intro_phrases(self):
        claims = [
            "Here's a structured approach to fundraising.",
            "VC readiness requires evidence of repeatable demand, not only product completeness.",
            "Here's a step-by-step guide.",
            "Enterprise readiness depends on security, auditability, and data-retention controls.",
        ]
        result = filter_claims(claims)
        assert len(result) == 2
        assert "VC readiness" in result[0]
        assert "Enterprise readiness" in result[1]

    def test_removes_markdown_artifacts(self):
        claims = [
            "**Validate Product-Market Fit (PMF)**",
            "## Build Your Data Room",
            "A SaaS startup should show scalable acquisition economics before fundraising.",
        ]
        result = filter_claims(claims)
        assert len(result) == 1
        assert "**" not in result[0]
        assert "scalable acquisition economics" in result[0]

    def test_removes_duplicates(self):
        claims = [
            "Security compliance requirements are essential for enterprise readiness certification processes.",
            "Security compliance requirements are essential for enterprise readiness certification processes.",
            "Unit economics must be proven before raising capital from investors.",
        ]
        result = filter_claims(claims)
        assert len(result) == 2

    def test_preserves_all_valid_claims(self):
        claims = [
            "VC readiness requires evidence of repeatable demand, not only product completeness.",
            "A SaaS startup should show scalable acquisition economics before fundraising.",
            "Enterprise readiness depends on security, auditability, and data-retention controls.",
        ]
        result = filter_claims(claims)
        assert len(result) == 3

    def test_empty_input(self):
        assert filter_claims([]) == []

    def test_all_invalid_returns_empty(self):
        claims = [
            "Here's a structured approach.",
            "Key Findings",
            "...",
            "**",
        ]
        result = filter_claims(claims)
        assert len(result) == 0

    def test_filters_short_fragments(self):
        claims = [
            "Team matters",
            "Product readiness is critical for successful venture capital fundraising rounds.",
        ]
        result = filter_claims(claims)
        assert len(result) == 1
        assert "Product readiness" in result[0]
