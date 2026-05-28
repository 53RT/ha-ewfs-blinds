"""Constants for Warema EWFS covers."""

DOMAIN = "warema_ewfs"

DEFAULT_NAME = "Warema EWFS"
DEFAULT_TRAVEL_TIME_UP = 22.0
DEFAULT_TRAVEL_TIME_DOWN = 22.0
DEFAULT_TILT_STEP_TIME_UP = 1.25
DEFAULT_TILT_STEP_TIME_DOWN = 1.25
DEFAULT_SEND_STOP_AFTER_MOVE = True
DEFAULT_COMMAND_DELAY = 0.0

TILT_STEP_COUNT = 7

CONF_IS_GROUP = "is_group"
CONF_IS_NATIVE_GROUP = "is_native_group"
CONF_GROUP_MEMBERS = "group_members"

CONF_TRAVEL_TIME_UP = "travel_time_up"
CONF_TRAVEL_TIME_DOWN = "travel_time_down"
CONF_TILT_STEP_TIME_UP = "tilt_step_time_up"
CONF_TILT_STEP_TIME_DOWN = "tilt_step_time_down"
CONF_SEND_STOP_AFTER_MOVE = "send_stop_after_move"
CONF_COMMAND_DELAY = "command_delay"

CONF_BTN_OPEN = "btn_open"
CONF_BTN_CLOSE = "btn_close"
CONF_BTN_STOP = "btn_stop"
CONF_BTN_TILT_UP = "btn_tilt_up"
CONF_BTN_TILT_DOWN = "btn_tilt_down"

ATTR_KNOWN_POSITION = "known_position"
ATTR_KNOWN_TILT_POSITION = "known_tilt_position"
