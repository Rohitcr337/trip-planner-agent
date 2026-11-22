from backend.app.text import clean_text


def test_clean_text_decodes_markup_numbers_and_whitespace():
    assert clean_text("1. **Chapora** &mdash; _North Goa_\n\nnear &nbsp; the fort") == (
        "Chapora — North Goa near the fort"
    )


def test_clean_text_keeps_non_emphasis_underscores_and_plain_text():
    assert clean_text("goa_wiki  place") == "goa_wiki place"
