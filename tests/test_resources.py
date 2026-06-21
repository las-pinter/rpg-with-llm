"""Tests for the Resource Data model — Task 1.2 of the Character Sheet Overhaul."""

from __future__ import annotations

import pytest

from app.character.resources import ResourceData

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_resource(**overrides: object) -> ResourceData:
    """Build a ResourceData with safe defaults for quick test setup."""
    defaults: dict[str, object] = {
        "value": 5,
        "max": 10,
        "short_rest_recovery": "none",
        "long_rest_recovery": "full",
    }
    defaults.update(overrides)
    return ResourceData(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# ResourceData creation
# ---------------------------------------------------------------------------


class TestResourceDataCreation:
    """ResourceData dataclass must store all fields correctly."""

    def test_all_fields_stored(self) -> None:
        resource = ResourceData(
            value=15,
            max=20,
            short_rest_recovery="1d8",
            long_rest_recovery="half",
        )
        assert resource.value == 15
        assert resource.max == 20
        assert resource.short_rest_recovery == "1d8"
        assert resource.long_rest_recovery == "half"

    def test_default_value(self) -> None:
        resource = _make_resource()
        assert resource.value == 5

    def test_default_max(self) -> None:
        resource = ResourceData()
        assert resource.max == 10

    def test_default_short_rest_recovery(self) -> None:
        resource = ResourceData()
        assert resource.short_rest_recovery == "none"

    def test_default_long_rest_recovery(self) -> None:
        resource = ResourceData()
        assert resource.long_rest_recovery == "full"

    def test_string_max_stored_as_string(self) -> None:
        """String max formulas must be stored verbatim (not resolved)."""
        resource = ResourceData(value=0, max="12+CON")
        assert resource.max == "12+CON"
        assert isinstance(resource.max, str)

    def test_dice_recovery_formulas_stored_verbatim(self) -> None:
        """Dice formula strings must be stored as-is."""
        resource = ResourceData(
            value=5,
            max=20,
            short_rest_recovery="1d8+2",
            long_rest_recovery="2d4+1",
        )
        assert resource.short_rest_recovery == "1d8+2"
        assert resource.long_rest_recovery == "2d4+1"

    def test_zero_value_is_allowed(self) -> None:
        """A resource can have a zero current value (depleted)."""
        resource = _make_resource(value=0, max=10)
        assert resource.value == 0


# ---------------------------------------------------------------------------
# current_ratio
# ---------------------------------------------------------------------------


class TestCurrentRatio:
    """current_ratio() must return value/max capped 0.0–1.0."""

    def test_normal_ratio(self) -> None:
        resource = _make_resource(value=5, max=10)
        assert resource.current_ratio() == 0.5

    def test_full_resource(self) -> None:
        resource = _make_resource(value=10, max=10)
        assert resource.current_ratio() == 1.0

    def test_depleted_resource(self) -> None:
        resource = _make_resource(value=0, max=10)
        assert resource.current_ratio() == 0.0

    def test_ratio_capped_at_one(self) -> None:
        """Value exceeding max must still return 1.0 (capped).

        Validation prevents this state at construction, but we test
        the method's defensive behaviour directly.
        """
        resource = _make_resource(value=5, max=10)
        object.__setattr__(resource, "value", 15)
        assert resource.value == 15  # bypassed validation
        assert resource.current_ratio() == 1.0

    def test_ratio_capped_at_zero(self) -> None:
        """Negative value must return 0.0 (capped).

        Validation prevents this state at construction, but we test
        the method's defensive behaviour directly.
        """
        resource = _make_resource(value=5, max=10)
        object.__setattr__(resource, "value", -5)
        assert resource.value == -5  # bypassed validation
        assert resource.current_ratio() == 0.0

    def test_exact_quarter(self) -> None:
        resource = _make_resource(value=3, max=12)
        assert resource.current_ratio() == 0.25

    def test_float_precision(self) -> None:
        """Ratio must be a proper float, not truncated."""
        resource = _make_resource(value=1, max=3)
        assert resource.current_ratio() == pytest.approx(0.3333333)

    def test_string_max_returns_zero(self) -> None:
        """When max is an unresolved string formula, ratio must return 0.0."""
        resource = ResourceData(value=5, max="12+CON")
        assert resource.current_ratio() == 0.0

    def test_string_max_with_zero_value(self) -> None:
        """String max with zero value must still return 0.0."""
        resource = ResourceData(value=0, max="8+CON")
        assert resource.current_ratio() == 0.0


# ---------------------------------------------------------------------------
# apply_recovery — short rest (dice formula)
# ---------------------------------------------------------------------------


class TestApplyRecoveryShortRest:
    """apply_recovery(is_long_rest=False) uses short_rest_recovery."""

    def test_short_rest_none_returns_zero(self) -> None:
        resource = _make_resource(value=5, max=10, short_rest_recovery="none")
        recovered = resource.apply_recovery(is_long_rest=False)
        assert recovered == 0
        assert resource.value == 5

    def test_short_rest_dice_recovers(self) -> None:
        """Using a deterministic formula "1d1" always recovers 1."""
        resource = _make_resource(value=5, max=10, short_rest_recovery="1d1")
        recovered = resource.apply_recovery(is_long_rest=False)
        assert recovered == 1
        assert resource.value == 6

    def test_short_rest_dice_capped_at_max(self) -> None:
        """Recovery must not push value above max."""
        resource = _make_resource(value=9, max=10, short_rest_recovery="1d6")
        recovered = resource.apply_recovery(is_long_rest=False)
        # 1d6 can roll up to 6, but we're capped at max 10 → recover 1
        assert recovered <= 1
        assert 9 <= resource.value <= 10

    def test_short_rest_full_capped(self) -> None:
        """Even "full" recovery as short rest must cap at max."""
        resource = _make_resource(value=5, max=10, short_rest_recovery="full")
        recovered = resource.apply_recovery(is_long_rest=False)
        assert recovered == 5
        assert resource.value == 10

    def test_short_rest_already_full_returns_zero(self) -> None:
        """Recovery when value already equals max must return 0."""
        resource = _make_resource(value=10, max=10, short_rest_recovery="full")
        recovered = resource.apply_recovery(is_long_rest=False)
        assert recovered == 0
        assert resource.value == 10

    def test_short_rest_dice_multiple_dice(self) -> None:
        """Recovery formula "2d1" rolls 2 dice of 1 side => always 2."""
        resource = _make_resource(value=3, max=20, short_rest_recovery="2d1")
        recovered = resource.apply_recovery(is_long_rest=False)
        assert recovered == 2
        assert resource.value == 5

    def test_short_rest_dice_with_modifier(self) -> None:
        """Recovery formula "1d1+2" must roll 1 + 2 = 3."""
        resource = _make_resource(value=5, max=20, short_rest_recovery="1d1+2")
        recovered = resource.apply_recovery(is_long_rest=False)
        assert recovered == 3
        assert resource.value == 8


# ---------------------------------------------------------------------------
# apply_recovery — long rest
# ---------------------------------------------------------------------------


class TestApplyRecoveryLongRest:
    """apply_recovery(is_long_rest=True) uses long_rest_recovery."""

    def test_long_rest_full_recovers_all(self) -> None:
        resource = _make_resource(value=3, max=10, long_rest_recovery="full")
        recovered = resource.apply_recovery(is_long_rest=True)
        assert recovered == 7
        assert resource.value == 10

    def test_long_rest_half_recovers_half(self) -> None:
        """Half recovery restores max/2 of the resource."""
        resource = _make_resource(value=3, max=10, long_rest_recovery="half")
        recovered = resource.apply_recovery(is_long_rest=True)
        assert recovered == 5  # 10 // 2 = 5
        assert resource.value == 8

    def test_long_rest_half_capped_at_max(self) -> None:
        """Half recovery must not exceed max even when close to full."""
        resource = _make_resource(value=7, max=10, long_rest_recovery="half")
        recovered = resource.apply_recovery(is_long_rest=True)
        # 10 // 2 = 5; 7 + 5 = 12 → capped at 10 => recover 3
        assert recovered == 3
        assert resource.value == 10

    def test_long_rest_half_minimum_one(self) -> None:
        """Half recovery of 1 should still give 1 (minimum)."""
        resource = _make_resource(value=0, max=1, long_rest_recovery="half")
        recovered = resource.apply_recovery(is_long_rest=True)
        # max(1, 1 // 2) = max(1, 0) = 1
        assert recovered == 1
        assert resource.value == 1

    def test_long_rest_none_returns_zero(self) -> None:
        resource = _make_resource(value=5, max=10, long_rest_recovery="none")
        recovered = resource.apply_recovery(is_long_rest=True)
        assert recovered == 0
        assert resource.value == 5

    def test_long_rest_dice_formula(self) -> None:
        """Long rest can also use a dice formula."""
        resource = _make_resource(value=5, max=20, long_rest_recovery="1d1")
        recovered = resource.apply_recovery(is_long_rest=True)
        assert recovered == 1
        assert resource.value == 6

    def test_long_rest_full_when_already_full(self) -> None:
        resource = _make_resource(value=10, max=10, long_rest_recovery="full")
        recovered = resource.apply_recovery(is_long_rest=True)
        assert recovered == 0
        assert resource.value == 10


# ---------------------------------------------------------------------------
# apply_recovery — does not exceed max
# ---------------------------------------------------------------------------


class TestApplyRecoveryCapping:
    """apply_recovery() must never set value above max."""

    def test_dice_recovery_capped(self) -> None:
        """Large dice roll must be capped at max."""
        resource = _make_resource(value=8, max=10, short_rest_recovery="1d1+10")
        resource.apply_recovery(is_long_rest=False)
        assert resource.value == 10

    def test_full_recovery_capped(self) -> None:
        resource = _make_resource(value=5, max=10, long_rest_recovery="full")
        resource.apply_recovery(is_long_rest=True)
        assert resource.value == 10

    def test_half_recovery_capped(self) -> None:
        resource = _make_resource(value=9, max=10, long_rest_recovery="half")
        resource.apply_recovery(is_long_rest=True)
        # half of 10 = 5, but 9 + 5 = 14 → capped at 10
        assert resource.value == 10

    def test_multiple_recoveries_do_not_exceed_max(self) -> None:
        """Calling recovery twice must never exceed max."""
        resource = _make_resource(
            value=5, max=10, short_rest_recovery="1d1", long_rest_recovery="full"
        )
        resource.apply_recovery(is_long_rest=False)  # +1 → 6
        resource.apply_recovery(is_long_rest=True)  # full → 10
        assert resource.value == 10


# ---------------------------------------------------------------------------
# apply_recovery — edge cases with string max
# ---------------------------------------------------------------------------


class TestApplyRecoveryStringMax:
    """When max is a string, apply_recovery must return 0 (can't resolve)."""

    def test_short_rest_string_max_returns_zero(self) -> None:
        resource = ResourceData(value=5, max="12+CON", short_rest_recovery="1d1")
        recovered = resource.apply_recovery(is_long_rest=False)
        assert recovered == 0
        assert resource.value == 5

    def test_long_rest_full_string_max_returns_zero(self) -> None:
        resource = ResourceData(value=5, max="12+CON", long_rest_recovery="full")
        recovered = resource.apply_recovery(is_long_rest=True)
        assert recovered == 0
        assert resource.value == 5

    def test_long_rest_half_string_max_returns_zero(self) -> None:
        resource = ResourceData(value=5, max="12+CON", long_rest_recovery="half")
        recovered = resource.apply_recovery(is_long_rest=True)
        assert recovered == 0
        assert resource.value == 5


# ---------------------------------------------------------------------------
# to_dict / from_dict — serialisation round-trip
# ---------------------------------------------------------------------------


class TestResourceSerialization:
    """ResourceData.to_dict() and .from_dict() must round-trip correctly."""

    def test_to_dict_returns_all_fields(self) -> None:
        resource = ResourceData(
            value=7,
            max=15,
            short_rest_recovery="1d8+2",
            long_rest_recovery="half",
        )
        data = resource.to_dict()
        assert isinstance(data, dict)
        assert data["value"] == 7
        assert data["max"] == 15
        assert data["short_rest_recovery"] == "1d8+2"
        assert data["long_rest_recovery"] == "half"

    def test_from_dict_reconstructs_resource(self) -> None:
        data: dict[str, object] = {
            "value": 12,
            "max": 20,
            "short_rest_recovery": "2d4",
            "long_rest_recovery": "full",
        }
        resource = ResourceData.from_dict(data)
        assert resource.value == 12
        assert resource.max == 20
        assert resource.short_rest_recovery == "2d4"
        assert resource.long_rest_recovery == "full"

    def test_round_trip_preserves_all_fields(self) -> None:
        original = _make_resource(
            value=8,
            max=18,
            short_rest_recovery="1d6",
            long_rest_recovery="half",
        )
        restored = ResourceData.from_dict(original.to_dict())
        assert restored.value == original.value
        assert restored.max == original.max
        assert restored.short_rest_recovery == original.short_rest_recovery
        assert restored.long_rest_recovery == original.long_rest_recovery

    def test_round_trip_default_resource(self) -> None:
        """Even default-constructed ResourceData must survive round-trip."""
        original = ResourceData()
        restored = ResourceData.from_dict(original.to_dict())
        assert restored.value == original.value
        assert restored.max == original.max
        assert restored.short_rest_recovery == original.short_rest_recovery
        assert restored.long_rest_recovery == original.long_rest_recovery

    def test_round_trip_string_max(self) -> None:
        """String max must survive serialization."""
        original = ResourceData(value=0, max="12+CON")
        restored = ResourceData.from_dict(original.to_dict())
        assert restored.max == "12+CON"
        assert isinstance(restored.max, str)

    def test_from_dict_extra_fields_forward_compat(self) -> None:
        """Unknown keys must be silently ignored."""
        data = _make_resource().to_dict()
        data["unknown_field"] = "ignored"
        resource = ResourceData.from_dict(data)
        assert resource.value == 5
        assert resource.max == 10

    def test_from_dict_missing_fields_use_defaults(self) -> None:
        """Omitting optional fields must result in their default values."""
        data: dict[str, object] = {"value": 8, "max": 20}
        resource = ResourceData.from_dict(data)
        assert resource.value == 8
        assert resource.max == 20
        assert resource.short_rest_recovery == "none"
        assert resource.long_rest_recovery == "full"


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class TestResourceValidation:
    """Resource validation must enforce rules at construction time."""

    def test_value_exceeds_int_max_raises(self) -> None:
        with pytest.raises(ValueError, match="cannot exceed max"):
            _make_resource(value=15, max=10)

    def test_value_equals_int_max_is_valid(self) -> None:
        resource = _make_resource(value=10, max=10)
        assert resource.value == 10
        assert resource.max == 10

    def test_negative_max_raises(self) -> None:
        with pytest.raises(ValueError, match="must be positive"):
            _make_resource(max=-5)

    def test_zero_max_raises(self) -> None:
        with pytest.raises(ValueError, match="must be positive"):
            _make_resource(max=0)

    def test_negative_value_raises(self) -> None:
        with pytest.raises(ValueError, match="cannot be negative"):
            _make_resource(value=-1, max=10)

    def test_non_int_value_raises(self) -> None:
        with pytest.raises(ValueError, match="must be an int"):
            _make_resource(value="5", max=10)  # type: ignore[arg-type]

    def test_empty_string_max_raises(self) -> None:
        with pytest.raises(ValueError, match="cannot be empty"):
            ResourceData(value=0, max="")

    def test_whitespace_only_string_max_raises(self) -> None:
        with pytest.raises(ValueError, match="cannot be empty"):
            ResourceData(value=0, max="   ")

    def test_none_max_raises(self) -> None:
        with pytest.raises(ValueError, match="must be an int or a string"):
            ResourceData(value=0, max=None)  # type: ignore[arg-type]

    def test_float_max_raises(self) -> None:
        with pytest.raises(ValueError, match="must be an int or a string"):
            ResourceData(value=0, max=10.5)  # type: ignore[arg-type]

    def test_string_max_allows_any_non_empty_string(self) -> None:
        """String max is stored without validation of formula syntax."""
        resource = ResourceData(value=0, max="some-formula")
        assert resource.max == "some-formula"

    def test_string_max_value_can_be_anything(self) -> None:
        """Value can be anything when max is a string (not resolved yet)."""
        resource = ResourceData(value=100, max="12+CON")
        assert resource.value == 100
        assert resource.max == "12+CON"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Boundary and edge-case values must be handled correctly."""

    def test_large_values(self) -> None:
        resource = _make_resource(value=999999, max=1000000)
        assert resource.value == 999999
        assert resource.current_ratio() == pytest.approx(0.999999)

    def test_minimal_max(self) -> None:
        """Max of 1 is the smallest valid int max."""
        resource = _make_resource(value=0, max=1)
        assert resource.max == 1
        assert resource.current_ratio() == 0.0

    def test_max_of_one_with_recovery(self) -> None:
        """Max of 1 with full recovery must work."""
        resource = _make_resource(value=0, max=1, long_rest_recovery="full")
        recovered = resource.apply_recovery(is_long_rest=True)
        assert recovered == 1
        assert resource.value == 1
