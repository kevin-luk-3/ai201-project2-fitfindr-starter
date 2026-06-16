from agent import run_agent
from utils.data_loader import get_example_wardrobe


def test_search_retry_drops_size_filter():
    """Stretch: no results with size filter, retry succeeds without it."""
    session = run_agent(
        "vintage graphic tee size XXS under $50",
        get_example_wardrobe(),
    )
    assert session["error"] is None
    assert session["selected_item"] is not None
    assert session["search_adjustment"] is not None
    assert "size" in session["search_adjustment"].lower()


def test_search_still_fails_after_retries():
    session = run_agent(
        "designer ballgown size XXS under $5",
        get_example_wardrobe(),
    )
    assert session["error"] is not None
    assert session["selected_item"] is None
    assert session["search_adjustment"] is None
