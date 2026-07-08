"""Headless smoke test: run the whole Streamlit script in-process and assert it
executes without raising. Uses Streamlit's AppTest, so no browser is needed.
Skipped automatically if streamlit isn't installed.
"""

import importlib.util
import pathlib

import pytest

_APP = pathlib.Path(__file__).resolve().parent.parent / "app" / "streamlit_app.py"
_HAS_STREAMLIT = importlib.util.find_spec("streamlit") is not None


@pytest.mark.skipif(not _HAS_STREAMLIT, reason="streamlit not installed")
def test_app_runs_without_exception():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(_APP), default_timeout=60)
    at.run()

    assert not at.exception, f"App raised: {at.exception}"
    subheaders = [s.value for s in at.subheader]
    assert any("Axe Matcher" in s for s in subheaders)
    assert any("Pre-Call Brief" in s for s in subheaders)


@pytest.mark.skipif(not _HAS_STREAMLIT, reason="streamlit not installed")
def test_app_survives_changing_the_axe_selection():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(_APP), default_timeout=60)
    at.run()
    # Flip to a different axe (2nd option) and re-run -> must not error.
    if at.selectbox and len(at.selectbox[0].options) > 1:
        at.selectbox[0].select_index(1).run()
        assert not at.exception
