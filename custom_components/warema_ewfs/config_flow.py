"""Config flow for Warema EWFS Cover."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.helpers.selector import (
    BooleanSelector,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)

from .const import (
    CONF_BTN_CLOSE,
    CONF_BTN_OPEN,
    CONF_BTN_STOP,
    CONF_BTN_TILT_DOWN,
    CONF_BTN_TILT_UP,
    CONF_COMMAND_DELAY,
    CONF_GROUP_MEMBERS,
    CONF_IS_GROUP,
    CONF_IS_NATIVE_GROUP,
    CONF_SEND_STOP_AFTER_MOVE,
    CONF_TILT_STEP_TIME_DOWN,
    CONF_TILT_STEP_TIME_UP,
    CONF_TRAVEL_TIME_DOWN,
    CONF_TRAVEL_TIME_UP,
    DEFAULT_COMMAND_DELAY,
    DEFAULT_SEND_STOP_AFTER_MOVE,
    DEFAULT_TILT_STEP_TIME_DOWN,
    DEFAULT_TILT_STEP_TIME_UP,
    DEFAULT_TRAVEL_TIME_DOWN,
    DEFAULT_TRAVEL_TIME_UP,
    DOMAIN,
)

COVER_TYPE_SINGLE = "single"
COVER_TYPE_GROUP = "group"
COVER_TYPE_NATIVE_GROUP = "native_group"

_BUTTON_SELECTOR = EntitySelector(EntitySelectorConfig(domain="button"))
_COVER_SELECTOR = EntitySelector(EntitySelectorConfig(domain="cover", multiple=True))


def _time_selector(min_val: float = 0.01, max_val: float = 600) -> NumberSelector:
    return NumberSelector(
        NumberSelectorConfig(
            min=min_val,
            max=max_val,
            step=0.1,
            mode=NumberSelectorMode.BOX,
            unit_of_measurement="s",
        )
    )


def _single_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    d = defaults or {}
    return vol.Schema(
        {
            vol.Required(CONF_NAME, default=d.get(CONF_NAME, "")): TextSelector(),
            vol.Required(CONF_BTN_OPEN, default=d.get(CONF_BTN_OPEN, "")): _BUTTON_SELECTOR,
            vol.Required(CONF_BTN_CLOSE, default=d.get(CONF_BTN_CLOSE, "")): _BUTTON_SELECTOR,
            vol.Required(CONF_BTN_STOP, default=d.get(CONF_BTN_STOP, "")): _BUTTON_SELECTOR,
            vol.Required(CONF_BTN_TILT_UP, default=d.get(CONF_BTN_TILT_UP, "")): _BUTTON_SELECTOR,
            vol.Required(CONF_BTN_TILT_DOWN, default=d.get(CONF_BTN_TILT_DOWN, "")): _BUTTON_SELECTOR,
            vol.Optional(
                CONF_TRAVEL_TIME_UP,
                default=d.get(CONF_TRAVEL_TIME_UP, DEFAULT_TRAVEL_TIME_UP),
            ): _time_selector(),
            vol.Optional(
                CONF_TRAVEL_TIME_DOWN,
                default=d.get(CONF_TRAVEL_TIME_DOWN, DEFAULT_TRAVEL_TIME_DOWN),
            ): _time_selector(),
            vol.Optional(
                CONF_TILT_STEP_TIME_UP,
                default=d.get(CONF_TILT_STEP_TIME_UP, DEFAULT_TILT_STEP_TIME_UP),
            ): _time_selector(min_val=0.01, max_val=60),
            vol.Optional(
                CONF_TILT_STEP_TIME_DOWN,
                default=d.get(CONF_TILT_STEP_TIME_DOWN, DEFAULT_TILT_STEP_TIME_DOWN),
            ): _time_selector(min_val=0.01, max_val=60),
            vol.Optional(
                CONF_SEND_STOP_AFTER_MOVE,
                default=d.get(CONF_SEND_STOP_AFTER_MOVE, DEFAULT_SEND_STOP_AFTER_MOVE),
            ): BooleanSelector(),
        }
    )


def _group_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    d = defaults or {}
    return vol.Schema(
        {
            vol.Required(CONF_NAME, default=d.get(CONF_NAME, "")): TextSelector(),
            vol.Required(
                CONF_GROUP_MEMBERS,
                default=d.get(CONF_GROUP_MEMBERS, []),
            ): _COVER_SELECTOR,
            vol.Optional(
                CONF_COMMAND_DELAY,
                default=d.get(CONF_COMMAND_DELAY, DEFAULT_COMMAND_DELAY),
            ): _time_selector(min_val=0, max_val=60),
        }
    )


def _native_group_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    d = defaults or {}
    return vol.Schema(
        {
            vol.Required(CONF_NAME, default=d.get(CONF_NAME, "")): TextSelector(),
            vol.Required(
                CONF_GROUP_MEMBERS,
                default=d.get(CONF_GROUP_MEMBERS, []),
            ): _COVER_SELECTOR,
            vol.Required(CONF_BTN_OPEN, default=d.get(CONF_BTN_OPEN, "")): _BUTTON_SELECTOR,
            vol.Required(CONF_BTN_CLOSE, default=d.get(CONF_BTN_CLOSE, "")): _BUTTON_SELECTOR,
            vol.Required(CONF_BTN_STOP, default=d.get(CONF_BTN_STOP, "")): _BUTTON_SELECTOR,
            vol.Required(CONF_BTN_TILT_UP, default=d.get(CONF_BTN_TILT_UP, "")): _BUTTON_SELECTOR,
            vol.Required(CONF_BTN_TILT_DOWN, default=d.get(CONF_BTN_TILT_DOWN, "")): _BUTTON_SELECTOR,
            vol.Optional(
                CONF_TRAVEL_TIME_UP,
                default=d.get(CONF_TRAVEL_TIME_UP, DEFAULT_TRAVEL_TIME_UP),
            ): _time_selector(),
            vol.Optional(
                CONF_TRAVEL_TIME_DOWN,
                default=d.get(CONF_TRAVEL_TIME_DOWN, DEFAULT_TRAVEL_TIME_DOWN),
            ): _time_selector(),
            vol.Optional(
                CONF_TILT_STEP_TIME_UP,
                default=d.get(CONF_TILT_STEP_TIME_UP, DEFAULT_TILT_STEP_TIME_UP),
            ): _time_selector(min_val=0.01, max_val=60),
            vol.Optional(
                CONF_TILT_STEP_TIME_DOWN,
                default=d.get(CONF_TILT_STEP_TIME_DOWN, DEFAULT_TILT_STEP_TIME_DOWN),
            ): _time_selector(min_val=0.01, max_val=60),
            vol.Optional(
                CONF_SEND_STOP_AFTER_MOVE,
                default=d.get(CONF_SEND_STOP_AFTER_MOVE, DEFAULT_SEND_STOP_AFTER_MOVE),
            ): BooleanSelector(),
        }
    )


def _cover_type_from_data(data: dict[str, Any]) -> str:
    if data.get(CONF_IS_NATIVE_GROUP):
        return COVER_TYPE_NATIVE_GROUP
    if data.get(CONF_IS_GROUP):
        return COVER_TYPE_GROUP
    return COVER_TYPE_SINGLE


class WaremaEWFSConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Warema EWFS Cover."""

    VERSION = 1

    def __init__(self) -> None:
        self._cover_type: str | None = None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> config_entries.ConfigFlowResult:
        if user_input is not None:
            self._cover_type = user_input["cover_type"]
            if self._cover_type == COVER_TYPE_SINGLE:
                return await self.async_step_single()
            if self._cover_type == COVER_TYPE_GROUP:
                return await self.async_step_group()
            return await self.async_step_native_group()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("cover_type"): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                {"value": COVER_TYPE_SINGLE, "label": "Single shutter"},
                                {"value": COVER_TYPE_GROUP, "label": "Fan-out group"},
                                {
                                    "value": COVER_TYPE_NATIVE_GROUP,
                                    "label": "Native remote group",
                                },
                            ],
                            mode=SelectSelectorMode.LIST,
                            translation_key="cover_type",
                        )
                    )
                }
            ),
        )

    async def async_step_single(self, user_input: dict[str, Any] | None = None) -> config_entries.ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(
                title=user_input[CONF_NAME],
                data={
                    **user_input,
                    CONF_IS_GROUP: False,
                    CONF_IS_NATIVE_GROUP: False,
                },
            )
        return self.async_show_form(step_id="single", data_schema=_single_schema())

    async def async_step_group(self, user_input: dict[str, Any] | None = None) -> config_entries.ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(
                title=user_input[CONF_NAME],
                data={
                    **user_input,
                    CONF_IS_GROUP: True,
                    CONF_IS_NATIVE_GROUP: False,
                },
            )
        return self.async_show_form(step_id="group", data_schema=_group_schema())

    async def async_step_native_group(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(
                title=user_input[CONF_NAME],
                data={
                    **user_input,
                    CONF_IS_GROUP: False,
                    CONF_IS_NATIVE_GROUP: True,
                },
            )
        return self.async_show_form(step_id="native_group", data_schema=_native_group_schema())

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        return WaremaEWFSOptionsFlow(config_entry)


class WaremaEWFSOptionsFlow(config_entries.OptionsFlowWithConfigEntry):
    """Handle options for an existing Warema EWFS entry."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> config_entries.ConfigFlowResult:
        """Route to the correct step based on cover type."""
        effective = {**self.config_entry.data, **self.config_entry.options}
        cover_type = _cover_type_from_data(effective)
        if cover_type == COVER_TYPE_GROUP:
            return await self.async_step_group(user_input)
        if cover_type == COVER_TYPE_NATIVE_GROUP:
            return await self.async_step_native_group(user_input)
        return await self.async_step_single(user_input)

    async def async_step_single(self, user_input: dict[str, Any] | None = None) -> config_entries.ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        effective = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(step_id="single", data_schema=_single_schema(defaults=effective))

    async def async_step_group(self, user_input: dict[str, Any] | None = None) -> config_entries.ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        effective = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(step_id="group", data_schema=_group_schema(defaults=effective))

    async def async_step_native_group(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        effective = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(step_id="native_group", data_schema=_native_group_schema(defaults=effective))
