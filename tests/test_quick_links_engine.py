import pytest
from modules.quick_links import engine


@pytest.fixture
def isolated(monkeypatch, tmp_path):
    links_file = tmp_path / "quick_links.json"
    monkeypatch.setattr(engine.Config, "QUICK_LINKS_FILE", str(links_file))
    if links_file.exists():
        links_file.unlink()
    return links_file


def test_seed_defaults_are_grouped(isolated):
    categories = engine.get_categories()
    names = [c["name"] for c in categories]
    assert names == ["Portals", "Printing", "Identity", "SIS (Omnia)", "NAC"]
    total_links = sum(len(c["links"]) for c in categories)
    assert total_links == 14
    for cat in categories:
        assert cat["id"]
        for link in cat["links"]:
            assert link["id"]
            assert link["name"]
            assert link["url"]
            assert link["icon"]


def test_legacy_flat_data_migrates_to_general(isolated):
    isolated.write_text(
        '{"links": [{"id": "a", "name": "Old", "url": "https://x", "icon": "🔗"}]}'
    )
    categories = engine.get_categories()
    assert len(categories) == 1
    assert categories[0]["name"] == "General"
    assert categories[0]["links"][0]["name"] == "Old"
    assert '"categories"' in isolated.read_text()
    assert "General" in isolated.read_text()


def test_add_and_remove_link_by_category(isolated):
    cat_id = engine.get_categories()[0]["id"]
    link = engine.add_link(cat_id, "New Link", "https://example.com", "🖥️")
    cats = engine.get_categories()
    assert any(l["id"] == link["id"] for l in cats[0]["links"])
    assert engine.remove_link(link["id"]) is True
    cats = engine.get_categories()
    assert all(l["id"] != link["id"] for c in cats for l in c["links"])


def test_add_link_unknown_category_raises(isolated):
    with pytest.raises(KeyError):
        engine.add_link("missing", "X", "https://example.com")


def test_add_and_remove_category(isolated):
    cat = engine.add_category("Temp")
    assert cat["name"] == "Temp"
    assert cat["links"] == []
    assert engine.remove_category(cat["id"]) is True


def test_remove_non_empty_category_raises(isolated):
    cat = engine.add_category("Busy")
    engine.add_link(cat["id"], "X", "https://example.com")
    with pytest.raises(ValueError):
        engine.remove_category(cat["id"])
    assert len(engine.get_categories()) == 6


def test_mutation_persists_grouped_shape(isolated):
    cat = engine.add_category("Persist")
    assert "categories" in isolated.read_text()
    engine.add_link(cat["id"], "L", "https://example.com")
    assert '"categories"' in isolated.read_text()
