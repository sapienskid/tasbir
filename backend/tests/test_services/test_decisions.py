"""Gateway transport + decision provider tests (no network — monkeypatched)."""

import pytest

from app.services import decision_packs as packs
from app.services import decisions as dec
from app.services import llm as llm_svc
from app.services import models as models_svc


def test_gateway_model_name_mapping():
    assert llm_svc.gateway_model_name("gemini-3.1-flash-lite") == (
        "google/gemini-3.1-flash-lite"
    )
    assert llm_svc.gateway_model_name("gemini-3.1-flash-lite", for_api_path=True) == (
        "google-ai-studio/gemini-3.1-flash-lite"
    )
    assert llm_svc.gateway_model_name("dynamic/tasbir-fast") == "dynamic/tasbir-fast"
    assert llm_svc.gateway_model_name("workers-ai/@cf/x") == "workers-ai/@cf/x"


def test_gateway_route_for_role_tiers():
    assert llm_svc.gateway_route_for_role("strategist") == "dynamic/tasbir-fast"
    assert llm_svc.gateway_route_for_role("copywriter") == "dynamic/tasbir-creative"
    assert llm_svc.gateway_route_for_role("verifier") == "dynamic/tasbir-vision"
    assert llm_svc.gateway_route_for_role("unknown-role") == "dynamic/tasbir-fast"


def test_gateway_tiers_cover_model_routes():
    routed = {r for roles in models_svc.GATEWAY_TIERS.values() for r in roles}
    for role in models_svc.MODEL_ROUTES:
        assert role in routed, f"agent role {role} has no gateway tier"


def test_gateway_not_configured_by_default(monkeypatch):
    for var in (
        "CF_ACCOUNT_ID",
        "CF_AIG_TOKEN",
        "CLOUDFLARE_ACCOUNT_ID",
        "CLOUDFLARE_AI_GATEWAY_TOKEN",
    ):
        monkeypatch.setenv(var, "")
    from app.config import get_settings

    get_settings.cache_clear()
    try:
        assert llm_svc.gateway_configured() is False
        assert dec.providers_configured() is False
    finally:
        get_settings.cache_clear()


def test_gateway_env_naming_both_supported(monkeypatch):
    from app.config import Settings

    legacy = Settings(
        cf_account_id="acct-legacy", cf_aig_token="tok-legacy",
    )
    assert legacy.resolved_cf_account_id == "acct-legacy"
    assert legacy.resolved_cf_token == "tok-legacy"
    canonical = Settings(
        cloudflare_account_id="acct-new",
        cloudflare_ai_gateway_token="tok-new",
    )
    assert canonical.resolved_cf_account_id == "acct-new"
    assert canonical.resolved_cf_token == "tok-new"
    # Canonical wins when both are set.
    both = Settings(
        cf_account_id="acct-legacy",
        cf_aig_token="tok-legacy",
        cloudflare_account_id="acct-new",
        cloudflare_ai_gateway_token="tok-new",
    )
    assert both.resolved_cf_account_id == "acct-new"
    assert both.resolved_cf_token == "tok-new"


def test_pack_registry_valid():
    for pid in packs.PACKS:
        pack = packs.get_pack(pid)
        assert 1 <= len(pack["questions"]) <= 12, pid
        for qid, q in pack["questions"].items():
            assert q["type"] in ("choice", "noul", "score"), (pid, qid)
            assert q.get("instructions"), (pid, qid)
            if q["type"] == "choice":
                assert 2 <= len(q["criteria"]) <= 255, (pid, qid)
            if q["type"] == "score":
                assert 2 <= len(q["criteria"]) <= 10, (pid, qid)
    with pytest.raises(ValueError):
        packs.get_pack("nope")


def test_confidence_helpers():
    assert dec.noul_confidence(0.97) == pytest.approx(0.94)
    assert dec.noul_confidence(0.5) == pytest.approx(0.0)
    assert dec.choice_confidence({"a": 1.0, "b": 0.0}) == pytest.approx(1.0)
    assert dec.choice_confidence({"a": 0.5, "b": 0.5}) == pytest.approx(0.0)


def test_disagreement_detection():
    a = {"q": {"type": "choice", "choice": "x", "probabilities": {"x": 0.9}}}
    b = {"q": {"type": "choice", "choice": "y", "probabilities": {"y": 0.9}}}
    assert dec._disagree(a, b) is True
    assert dec._disagree(a, a) is False
    n1 = {"u": {"type": "noul", "noul": 0.9}}
    n2 = {"u": {"type": "noul", "noul": 0.1}}
    assert dec._disagree(n1, n2) is True


def test_copy_quality_composite():
    voice = {"brand_fit": {"type": "noul", "noul": 0.9}, "hype": {"score": 1.0}}
    claims = {"misleading": {"type": "noul", "noul": 0.1}}
    structure = {
        "has_cta": {"type": "choice", "choice": "explicit"},
        "value_clear": {"type": "noul", "noul": 0.9},
    }
    out = packs.copy_quality(voice, claims, structure)
    assert out["verdict"] == "pass"
    assert 0.0 <= out["score"] <= 1.0
    bad = packs.copy_quality(
        {"brand_fit": {"type": "noul", "noul": 0.1}, "hype": {"score": 3.5}},
        {"misleading": {"type": "noul", "noul": 0.95}},
        {"has_cta": {"type": "choice", "choice": "none"},
         "value_clear": {"type": "noul", "noul": 0.1}},
    )
    assert bad["verdict"] == "rewrite"
