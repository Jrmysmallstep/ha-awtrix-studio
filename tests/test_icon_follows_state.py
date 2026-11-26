"""An app's icon that follows the state of an entity (the weather, say)."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.awtrix_studio.const import DOMAIN
from custom_components.awtrix_studio.templates import build_app_template
from custom_components.awtrix_studio.validation import Invalid, normalize_app

from .test_templates import render

WEATHER = "weather.home"
ICONS = {"sunny": "lametric:1", "rainy": "lametric:2", "snowy": "lametric:3"}


def options(**extra: Any) -> dict[str, Any]:
    """A temperature whose icon follows the weather."""
    return {
        "entity_id": "sensor.outside",
        "icon": "lametric:9",
        "icon_entity_id": WEATHER,
        "icon_states": ICONS,
        "decimals": 0,
        "show_unit": False,
        **extra,
    }


@pytest.mark.parametrize("firmware", ["awtrix3", "awtrix_ng"])
async def test_icon_follows_the_weather(hass: HomeAssistant, firmware: str) -> None:
    """Each state brings its icon; any other state brings the default one."""
    template = build_app_template(options(), firmware)
    hass.states.async_set("sensor.outside", "5.6")
    for state, icon in [
        ("sunny", "lametric:1"),
        ("rainy", "lametric:2"),
        ("snowy", "lametric:3"),
        ("fog", "lametric:9"),
        ("unavailable", "lametric:9"),
    ]:
        hass.states.async_set(WEATHER, state)
        [page] = render(hass, template)
        assert page["icon"] == icon, state
        assert page["text"] == "6"


async def test_icon_follows_the_weather_on_a_layout(hass: HomeAssistant) -> None:
    """The icon region of a TC002 layout follows it too."""
    template = build_app_template(options(layout="value"), "awtrix_ng")
    hass.states.async_set("sensor.outside", "5.6")
    hass.states.async_set(WEATHER, "snowy")
    [page] = render(hass, template)
    [icon] = [r for r in page["layout"]["regions"] if r["id"] == "icon"]
    assert icon["icon"] == "lametric:3"


async def test_icon_is_fixed_without_a_table(hass: HomeAssistant) -> None:
    """An entity with no icons does nothing: the app keeps its icon."""
    template = build_app_template(options(icon_states={}), "awtrix3")
    hass.states.async_set("sensor.outside", "5.6")
    hass.states.async_set(WEATHER, "snowy")
    assert render(hass, template)[0]["icon"] == "lametric:9"


async def test_value_from_an_attribute(hass: HomeAssistant) -> None:
    """The temperature of a weather entity is one of its attributes."""
    template = build_app_template(
        {
            "entity_id": WEATHER,
            "attribute": "temperature",
            "icon": "lametric:9",
            "decimals": 1,
            "unit": "°",
        },
        "awtrix3",
    )
    hass.states.async_set(WEATHER, "rainy", {"temperature": 5.64})
    assert render(hass, template)[0]["text"] == "5.6°"
    # No such attribute (or no entity yet): the app is hidden, not "None".
    hass.states.async_set(WEATHER, "rainy", {})
    assert render(hass, template) == []
    hass.states.async_remove(WEATHER)
    assert render(hass, template) == []


def entry() -> MockConfigEntry:
    """A clock to validate against."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="clock",
        data={"firmware": "awtrix3", "prefix": "clock"},
    )


async def test_validation_keeps_the_icons(hass: HomeAssistant) -> None:
    """The entity, the table and the attribute are kept; empty icons are not."""
    clock = entry()
    clock.add_to_hass(hass)
    data = normalize_app(
        hass,
        clock,
        {
            "mode": "simple",
            "app_name": "Temp",
            "attribute": "temperature",
            **options(icon_states={**ICONS, "fog": ""}),
        },
        None,
    )
    assert data["icon_entity_id"] == WEATHER
    assert data["icon_states"] == ICONS
    assert data["attribute"] == "temperature"
    assert data["icon"] == "lametric:9"


@pytest.mark.parametrize(
    ("extra", "field", "key"),
    [
        ({"icon_entity_id": "nope"}, "icon_entity_id", "invalid_entity"),
        ({"icon_states": ["sunny"]}, "icon_states", "invalid_value"),
        ({"icon_states": {"": "lametric:1"}}, "icon_states", "invalid_value"),
        (
            {"icon_states": {f"s{n}": "x" for n in range(41)}},
            "icon_states",
            "invalid_value",
        ),
        ({"icon": ""}, "icon", "icon_default_required"),
        ({"attribute": "no spaces"}, "attribute", "invalid_value"),
    ],
)
async def test_validation_refuses(
    hass: HomeAssistant, extra: dict[str, Any], field: str, key: str
) -> None:
    """Bad icons are refused, with the field to blame."""
    clock = entry()
    clock.add_to_hass(hass)
    with pytest.raises(Invalid) as err:
        normalize_app(
            hass,
            clock,
            {"mode": "simple", "app_name": "Temp", **options(**extra)},
            None,
        )
    assert (err.value.field, err.value.key) == (field, key)


async def test_no_entity_means_no_table(hass: HomeAssistant) -> None:
    """Without an entity to follow, the table is dropped."""
    clock = entry()
    clock.add_to_hass(hass)
    data = normalize_app(
        hass,
        clock,
        {"mode": "simple", "app_name": "Temp", **options(icon_entity_id="")},
        None,
    )
    assert "icon_entity_id" not in data
    assert "icon_states" not in data
