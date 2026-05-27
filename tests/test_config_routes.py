"""Tests for the character creation config API — GET /api/config/character-rules."""

from __future__ import annotations

import pytest

from app.server import app


@pytest.fixture
def client():
    """Create a test client for the Flask app."""
    with app.test_client() as c:
        yield c


class TestCharacterRules:
    """Tests for GET /api/config/character-rules."""

    def test_returns_ok(self, client):
        """GET returns 200 with ok=true."""
        resp = client.get("/api/config/character-rules")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert "rules" in data

    def test_valid_classes_has_four_entries(self, client):
        """GET returns four valid classes."""
        resp = client.get("/api/config/character-rules")
        rules = resp.get_json()["rules"]
        assert len(rules["valid_classes"]) == 4
        assert set(rules["valid_classes"]) == {"Fighter", "Rogue", "Mage", "Cleric"}

    def test_class_templates_has_all_four_classes(self, client):
        """GET returns templates for all four classes."""
        resp = client.get("/api/config/character-rules")
        templates = resp.get_json()["rules"]["class_templates"]
        assert set(templates.keys()) == {"Fighter", "Rogue", "Mage", "Cleric"}

    def test_class_templates_have_required_fields(self, client):
        """Each class template has abilities, hp, ac, skills, inventory, gold."""
        resp = client.get("/api/config/character-rules")
        templates = resp.get_json()["rules"]["class_templates"]
        required = {"abilities", "hp", "ac", "skills", "inventory", "gold"}
        for cls_name, tmpl in templates.items():
            assert set(tmpl.keys()) == required, (
                f"{cls_name} missing fields: {required - set(tmpl.keys())}"
            )

    def test_point_buy_costs_has_eight_entries(self, client):
        """GET returns point_buy costs for scores 8 through 15."""
        resp = client.get("/api/config/character-rules")
        costs = resp.get_json()["rules"]["point_buy"]["costs"]
        assert len(costs) == 8
        # Keys should be string representations of 8..15
        expected_keys = {str(i) for i in range(8, 16)}
        assert set(costs.keys()) == expected_keys

    def test_point_buy_max_points(self, client):
        """GET returns max_points of 27."""
        resp = client.get("/api/config/character-rules")
        pb = resp.get_json()["rules"]["point_buy"]
        assert pb["max_points"] == 27
        assert pb["min_score"] == 8
        assert pb["max_score"] == 15

    def test_assisted_creation_questions(self, client):
        """GET returns assisted creation questions."""
        resp = client.get("/api/config/character-rules")
        questions = resp.get_json()["rules"]["assisted_creation_questions"]
        assert len(questions) == 7
        assert all(isinstance(q, str) for q in questions)

    def test_standard_abilities_returns_six(self, client):
        """GET returns six standard abilities."""
        resp = client.get("/api/config/character-rules")
        abilities = resp.get_json()["rules"]["standard_abilities"]
        assert len(abilities) == 6
        assert set(abilities) == {"STR", "DEX", "CON", "INT", "WIS", "CHA"}
