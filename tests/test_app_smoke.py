"""Headless smoke test: run the whole Streamlit script in-process and assert it
executes without raising. Uses Streamlit's AppTest, so no browser is needed.
Skipped automatically if streamlit isn't installed.
"""

import importlib.util
import pathlib

import pytest

_APP = pathlib.Path(__file__).resolve().parent.parent / "app" / "streamlit_app.py"
_HAS_STREAMLIT = importlib.util.find_spec("streamlit") is not None


def _app():
    from streamlit.testing.v1 import AppTest
    return AppTest.from_file(str(_APP), default_timeout=60)


@pytest.mark.skipif(not _HAS_STREAMLIT, reason="streamlit not installed")
def test_home_shows_two_boxes_and_no_data():
    at = _app().run()
    assert not at.exception, f"App raised: {at.exception}"
    md = " ".join(m.value for m in at.markdown)
    assert "Axurry" in md
    # Two entry buttons, and NO tool selectbox on the landing page.
    keys = {b.key for b in at.button}
    assert {"open_axe", "open_brief"} <= keys
    assert len(at.selectbox) == 0


@pytest.mark.skipif(not _HAS_STREAMLIT, reason="streamlit not installed")
def test_theme_toggle_does_not_crash():
    at = _app().run()
    next(b for b in at.button if b.key == "theme_toggle").click().run()
    assert not at.exception
    # Still on a clean home after toggling.
    keys = {b.key for b in at.button}
    assert {"open_axe", "open_brief"} <= keys


@pytest.mark.skipif(not _HAS_STREAMLIT, reason="streamlit not installed")
def test_can_open_axe_matcher():
    at = _app().run()
    next(b for b in at.button if b.key == "open_axe").click().run()
    assert not at.exception
    assert len(at.selectbox) == 1          # the axe picker now appears
    assert any("Axe Matcher" in m.value for m in at.markdown)


@pytest.mark.skipif(not _HAS_STREAMLIT, reason="streamlit not installed")
def test_can_open_brief_and_go_back():
    at = _app().run()
    next(b for b in at.button if b.key == "open_brief").click().run()
    assert not at.exception
    assert any("Pre-Call Brief" in m.value for m in at.markdown)
    # Back button returns to the clean home (no selectbox).
    next(b for b in at.button if b.key == "back_brief").click().run()
    assert not at.exception
    assert len(at.selectbox) == 0
