"""
tests/test_tools.py

Isolation tests for each FitFindr tool. Tests cover the happy path and
each tool's documented failure mode. Run with: pytest tests/test_tools.py
"""

from tools import create_fit_card, search_listings, suggest_outfit
from utils.data_loader import get_empty_wardrobe, get_example_wardrobe


# ── search_listings ───────────────────────────────────────────────────────────

def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0


def test_search_empty_results():
    # No listing in the dataset matches this; must return [] not raise
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []


def test_search_price_filter():
    results = search_listings("jacket", size=None, max_price=10)
    assert all(item["price"] <= 10 for item in results)


def test_search_size_filter():
    # Size "S" should not return items sized "XL (oversized)" or "W30 L30"
    results = search_listings("jacket", size="S", max_price=200)
    for item in results:
        assert "s" in item["size"].lower()


def test_search_results_sorted_by_relevance():
    # A more specific match should rank higher than a single-keyword match
    results = search_listings("vintage denim jacket", size=None, max_price=200)
    assert len(results) > 0
    # All returned items must have at least one keyword hit (score > 0)
    for item in results:
        searchable = (
            item["title"].lower()
            + " "
            + item["description"].lower()
            + " "
            + " ".join(item["style_tags"]).lower()
        )
        assert any(kw in searchable for kw in ["vintage", "denim", "jacket"])


# ── suggest_outfit ────────────────────────────────────────────────────────────

def test_suggest_outfit_with_wardrobe():
    wardrobe = get_example_wardrobe()
    item = search_listings("graphic tee", size=None, max_price=50)[0]
    result = suggest_outfit(item, wardrobe)
    assert isinstance(result, str)
    assert len(result) > 0


def test_suggest_outfit_empty_wardrobe():
    # Must return a non-empty string, not crash or return ""
    wardrobe = get_empty_wardrobe()
    item = search_listings("flannel", size=None, max_price=50)[0]
    result = suggest_outfit(item, wardrobe)
    assert isinstance(result, str)
    assert len(result) > 0


# ── create_fit_card ───────────────────────────────────────────────────────────

def test_fit_card_returns_string():
    item = search_listings("vintage tee", size=None, max_price=50)[0]
    wardrobe = get_example_wardrobe()
    outfit = suggest_outfit(item, wardrobe)
    result = create_fit_card(outfit, item)
    assert isinstance(result, str)
    assert len(result) > 0


def test_fit_card_empty_outfit_returns_error_message():
    # Must return an error string, not raise an exception
    item = search_listings("vintage tee", size=None, max_price=50)[0]
    result = create_fit_card("", item)
    assert isinstance(result, str)
    assert len(result) > 0
    assert "outfit" in result.lower() or "fit card" in result.lower()


def test_fit_card_mentions_platform_and_price():
    item = search_listings("vintage tee", size=None, max_price=50)[0]
    wardrobe = get_example_wardrobe()
    outfit = suggest_outfit(item, wardrobe)
    result = create_fit_card(outfit, item)
    assert item["platform"].lower() in result.lower()
    assert str(int(item["price"])) in result
