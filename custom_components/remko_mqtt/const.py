"""Constants for the component."""

# Component domain, used to store component data in hass data.
DOMAIN = "remko_mqtt"

# == Remko Const
CONF_ID = "id_name"
CONF_MQTT_NODE = "V04P28/SMTID"
CONF_MQTT_DBG = "remko_dbg"
CONF_LANGUAGE = "language"
CONF_DATA = "data_msg"
CONF_FREQ = "freq"
DEFAULT_DBG = False
AVAILABLE_LANGUAGES = ["en", "de"]


PLATFORM_AUTOMATION = "automation"
PLATFORM_GROUP = "group"
PLATFORM_INPUT_BUTTON = "input_button"
PLATFORM_INPUT_NUMBER = "input_number"
PLATFORM_INPUT_SELECT = "input_select"
PLATFORM_INPUT_TEXT = "input_text"
CONF_ENTITY_PLATFORM = "entity_platform"
