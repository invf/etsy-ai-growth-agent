from app.services.etsy_validation import validate_listing_update


def test_valid_update_passes():
    assert validate_listing_update({"title": "Nice Mug", "tags": ["mug", "gift"]}) == []


def test_title_too_long_rejected():
    errors = validate_listing_update({"title": "x" * 141})
    assert any("140" in e for e in errors)


def test_empty_title_rejected():
    assert validate_listing_update({"title": "   "})


def test_too_many_tags_rejected():
    errors = validate_listing_update({"tags": [f"tag {i}" for i in range(14)]})
    assert any("13" in e for e in errors)


def test_tag_over_20_chars_rejected():
    errors = validate_listing_update({"tags": ["x" * 21]})
    assert any("20" in e for e in errors)


def test_empty_tag_rejected():
    errors = validate_listing_update({"tags": ["ok", " "]})
    assert any("non-empty" in e for e in errors)


def test_duplicate_tags_rejected():
    errors = validate_listing_update({"tags": ["Mug", "mug"]})
    assert any("unique" in e for e in errors)


def test_empty_tag_list_rejected():
    assert validate_listing_update({"tags": []})


def test_valid_description_passes():
    assert validate_listing_update({"description": "A nicely written description."}) == []


def test_empty_description_rejected():
    errors = validate_listing_update({"description": "   "})
    assert any("non-empty" in e for e in errors)


def test_description_too_long_rejected():
    errors = validate_listing_update({"description": "x" * 102401})
    assert any("102400" in e for e in errors)
