"""Design systems service unit tests — validation, payload, logo, preview."""

from app.services import design_systems as ds_service


def test_slugify():
    assert ds_service.slugify("Acme Co") == "acme-co"
    assert ds_service.slugify("  A !@#$ Brand  ") == "a-brand"
    assert ds_service.slugify("") == "default"


def test_validate_design_system_accepts_good():
    assert ds_service.validate_design_system({"tokens": {"--x": "1"}}) == []


def test_validate_design_system_rejects_bad_tokens():
    issues = ds_service.validate_design_system({"tokens": {"color": "#fff"}})
    assert any("start with '--'" in i for i in issues)


def test_validate_design_system_rejects_bad_campaign_ground():
    issues = ds_service.validate_design_system(
        {"campaigns": {"c": {"ground": "pink"}}}
    )
    assert any("ground" in i for i in issues)


def test_validate_design_system_rejects_bad_allowed_grounds():
    issues = ds_service.validate_design_system(
        {"design_instruction": {"style": {"allowed_grounds": ["blue"]}}}
    )
    assert issues


def test_logo_data_uri():
    class FakeDS:
        logo = {"mime": "image/png", "data": "AAAA", "filename": "l.png"}

    assert ds_service.logo_data_uri(FakeDS()) == "data:image/png;base64,AAAA"

    class EmptyDS:
        logo = None

    assert ds_service.logo_data_uri(EmptyDS()) == ""


def test_build_pipeline_payload_merges_tokens():
    class FakeDS:
        id = "x"
        tokens = {"--color-accent": "#FF0000"}
        token_roles = {"--color-accent": "accent"}
        brand = {"name": "Acme"}
        footer = {"left": "A", "right": "@B"}
        categories = [{"name": "WRITING"}]
        overrides = {}
        campaigns = {"default": {}}
        design_instruction = {}
        logo = None

    payload = ds_service.build_pipeline_payload(FakeDS())
    assert payload["design_tokens"]["--color-accent"] == "#FF0000"
    # standard defaults merged in
    assert "--color-bg" in payload["design_tokens"]
    assert payload["logo"] == ""
    assert payload["design_system_id"] == "x"
