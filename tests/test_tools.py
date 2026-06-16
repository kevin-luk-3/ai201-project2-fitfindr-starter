from tools import search_listings, suggest_outfit, create_fit_card
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe


def _sample_item():
    return search_listings("vintage graphic tee", size=None, max_price=50)[0]


def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0


def test_search_empty_results():
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []


def test_search_price_filter():
    results = search_listings("jacket", size=None, max_price=10)
    assert all(item["price"] <= 10 for item in results)


def test_suggest_outfit_with_wardrobe():
    result = suggest_outfit(_sample_item(), get_example_wardrobe())
    assert isinstance(result, str)
    assert len(result.strip()) > 0


def test_suggest_outfit_empty_wardrobe():
    result = suggest_outfit(_sample_item(), get_empty_wardrobe())
    assert isinstance(result, str)
    assert len(result.strip()) > 0


def test_create_fit_card():
    item = _sample_item()
    outfit = "Pair with baggy jeans and chunky sneakers for a 90s look."
    result = create_fit_card(outfit, item)
    assert isinstance(result, str)
    assert len(result.strip()) > 0
    assert "Can't create a fit card" not in result


def test_create_fit_card_empty_outfit():
    result = create_fit_card("", _sample_item())
    assert result == "Can't create a fit card without an outfit suggestion."
