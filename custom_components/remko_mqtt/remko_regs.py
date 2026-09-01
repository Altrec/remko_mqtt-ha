"""Remko MQTT registries."""

# Model definitions
WKF = "wkf"
WSP = "wsp"
ALL = {WKF, WSP}

# Remko generated register definitions
FIELD_REGID = 0
FIELD_REGTYPE = 1
FIELD_UNIT = 2
FIELD_MINVALUE = 3
FIELD_MAXVALUE = 4
FIELD_ACTIVE = 5

# Registers definition list
# Format: (Entity_Key, [Register_ID, Type, Unit, Min, Max, Active], Supported_Models)
REMKO_REGISTERS = [
    ("dhw_opmode", ["1079", "select_input", "", 0, 16, True], ALL),
    ("timeprogram_dhw_a", ["1081", "timeprogram", "", "", "", False], ALL),
    ("water_temp_req", ["1082", "sensor_temp_inp", "ºC", 20.0, 60.0, True], ALL),
    ("main_mode", ["1088", "select_input", "", "", "", True], {WSP}),
    ("timeprogram_circ", ["1555", "timeprogram", "", "", "", False], ALL),
    ("timeprogram_hc_a", ["1785", "timeprogram", "", "", "", False], ALL),
    ("absence_mode", ["1893", "switch", "", "", "", True], ALL),
    ("party_mode", ["1894", "switch", "", "", "", True], ALL),
    ("user_profile", ["1936", "select_input", "", "", "", True], ALL),
    ("timeprogram_dhw_b", ["1939", "timeprogram", "", "", "", False], ALL),
    ("timeprogram_dhw_c", ["1940", "timeprogram", "", "", "", False], ALL),
    ("timeprogram_hc_b", ["1941", "timeprogram", "", "", "", False], ALL),
    ("timeprogram_hc_c", ["1942", "timeprogram", "", "", "", False], ALL),
    ("temp_adjust", ["1946", "sensor_temp_inp", "ºC", -10.0, 10.0, True], ALL),
    ("main_mode", ["1951", "select_input", "", "", "", True], {WKF}),
    ("heating_circ_mode", ["1972", "switch", "", "", "", False], ALL),
    ("fixed_temp_req", ["1974", "sensor_temp_inp", "ºC", 20.0, 60.0, False], ALL),
    ("timemode", ["2149", "select_input", "", "", "", True], ALL),
    ("opmode", ["5001", "sensor_mode", "", "", "", True], ALL),
    ("circulation_temp", ["5027", "sensor_temp", "ºC", "", "", True], ALL),
    ("out_temp", ["5032", "sensor_temp", "ºC", "", "", True], ALL),
    ("actual_temp", ["5034", "sensor_temp", "ºC", "", "", False], ALL),
    ("water_temp", ["5039", "sensor_temp", "ºC", "", "", True], ALL),
    ("heat_gen_status", ["5051", "binary_sensor", "", "", "", True], ALL),
    ("mixed_temp", ["5055", "sensor_temp", "ºC", "", "", False], ALL),
    ("heat_water_temp_req", ["5085", "sensor_temp_inp", "ºC", 20.0, 60.0, True], ALL),
    ("energy_electric", ["5105", "sensor_en", "kWh", "", "", True], ALL),
    ("energy_thermal", ["5119", "sensor_en", "kWh", "", "", False], ALL),
    ("buff_temp", ["5131", "sensor_temp", "ºC", "", "", False], ALL),
    ("air_temp_mod", ["5145", "sensor_temp", "ºC", "", "", False], ALL),
    ("heating_actual_temp", ["5190", "sensor_temp", "ºC", "", "", True], ALL),
    ("compressor_frequency", ["5205", "sensor_freq", "Hz", "", "", False], ALL),
    ("power_own_use", ["5231", "sensor_el", "W", "", "", False], ALL),
    ("el_consumption", ["5320", "sensor_el", "W", "", "", True], ALL),
    ("th_consumption", ["5321", "sensor_el", "W", "", "", False], ALL),
    ("energy_heating", ["5374", "sensor_en", "kWh", "", "", True], ALL),
    ("energy_DHW_heating", ["5376", "sensor_en", "kWh", "", "", True], ALL),
    ("energy_environmental", ["5600", "sensor_en", "kWh", "", "", False], ALL),
    ("dhw_heating", ["5693", "action", "", "", "", True], ALL),
    ("compressor_starts", ["5822", "sensor_counter", "", 0, 65535, False], ALL),
    ("compressor_hours", ["5824", "sensor_counter", "h", 0, "", False], ALL),
]


def get_remko_regs(selected_model: str = WKF) -> dict:
    """Return register map for the selected heat pump model."""
    regs = {}
    for key, reg_data, supported_models in REMKO_REGISTERS:
        if selected_model in supported_models:
            if isinstance(reg_data, list):
                reg_dict = dict(enumerate(reg_data))
            else:
                reg_dict = reg_data
            regs[key] = reg_dict
    return regs


# Translation dictionary (unverändert gültig für alle Modelle)
# ['en', 'de']
remko_reg_translation = {
    "absence_mode": ["Absence mode", "Abwesenheitssmodus"],
    "actual_temp": ["Actual temperature", "Ist-Temperatur"],
    "air_temp_mod": ["Air temperature module", "Lufttemperatur Modul"],
    "buff_temp": ["Buffer tank temp.", "Pufferspeicher Temp."],
    "circulation_temp": ["Circulation temp.", "Zirkulation Temp."],
    "compressor_frequency": ["Compressor frequency", "Verdichterfrequenz"],
    "compressor_hours": ["Compressor hours", "Verdichterstunden"],
    "compressor_starts": ["compressor starts", "Kompressorstarts"],
    "dhw_heating": ["1x DHW heating", "1x WW aufheizen"],
    "dhw_opmode": ["DHW mode", "WW Modus"],
    "el_consumption": ["Electr. power", "Leistung elektrisch"],
    "energy_DHW_heating": ["Energy DHW heating", "Energie Warmwasser"],
    "energy_electric": ["Electr. energy heatpump ", "Elektrische Energie"],
    "energy_environmental": ["Environmental energy", "Umweltenergie"],
    "energy_heating": ["Energy heating", "Energie Heizen"],
    "energy_thermal": ["Therm. energy heatpump ", "Thermische Energie"],
    "fixed_temp_req": ["Fixed value temp.", "Festwert Temp."],
    "heating_actual_temp": ["Heating water temp. (actual)", "Heizwasser Ist-Temp."],
    "heating_circ_mode": ["Heating circuit mode", "Heizkreis Modus"],
    "heat_gen_status": ["Heat generator status", "Wärmeerzeuger Status"],
    "heat_water_temp_req": ["Heating water temp. req.", "Heizwasser soll"],
    "main_mode": ["Room climate mode", "Raumklima Modus"],
    "mixed_temp": ["Mixed temp.", "Gemischte Temperatur"],
    "opmode": ["Operating mode", "Betriebsmodus"],
    "out_temp": ["Outside temp.", "Außentemperatur"],
    "party_mode": ["Party mode", "Partymodus"],
    "power_own_use": ["Power own use", "Leistung Eigenverbrauch"],
    "temp_adjust": ["Colder / hotter", "Kälter / Wärmer"],
    "th_consumption": ["Therm. power", "Leistung thermisch"],
    "timemode": ["Timeprogram function", "Funktion Zeitprogramm"],
    "timeprogram_circ": ["Time program circ.", "Zeitprogramm Zirk."],
    "timeprogram_dhw_a": ["Time program DHW A", "Zeitprogramm WW A"],
    "timeprogram_dhw_b": ["Time program DHW B", "Zeitprogramm WW B"],
    "timeprogram_dhw_c": ["Time program DHW C", "Zeitprogramm WW C"],
    "timeprogram_hc_a": ["Time program HC A", "Zeitprogramm HK A"],
    "timeprogram_hc_b": ["Time program HC B", "Zeitprogramm HK B"],
    "timeprogram_hc_c": ["Time program HC C", "Zeitprogramm HK C"],
    "user_profile": ["User profile", "Benutzerprofil"],
    "water_temp": ["Water temp.", "Warmwasser Temp."],
    "water_temp_req": ["Water temp. req.", "Warmwasser soll"],
    "dhwopmode0": ["Automatic comfort", "Automatik Komfort"],
    "dhwopmode1": ["Automatic eco", "Automatik Eco"],
    "dhwopmode2": ["Solar/PV only", "Nur Solar/PV"],
    "dhwopmode3": ["Off", "Aus"],
    "mode0": ["Unknown", "Unbekannt"],
    "mode1": ["Auto", "Auto"],
    "mode2": ["Heating", "Heizen"],
    "mode3": ["Standby", "Standby"],
    "mode4": ["Cooling", "Kühlen"],
    "opmode0": ["Unknown / Off", "Unbekannt / Aus"],
    "opmode1": ["Forced off", "Störung"],
    "opmode2": ["Defrosting", "Abtauen"],
    "opmode3": ["Load defr. puffer", "Abtaupuffer"],
    "opmode4": ["DHW loading", "WW Puffer"],
    "opmode5": ["Storage energy", "Speicherenergie"],
    "opmode6": ["Heating", "Heizen"],
    "opmode7": ["Cooling", "Kühlen"],
    "opmode8": ["Pool heating", "Pool"],
    "opmode9": ["Idle", "Umwälzung"],
    "opmode10": ["Standby", "Standby"],
    "opmode11": ["Screed drying", "Estrichtrockung"],
    "opmode12": ["Frost protection", "Frostschutz"],
    "opmode13": ["Test mode", "Prüfbetrieb"],
    "opmode14": ["Blocking signal", "Sperrsignal"],
    "opmode15": ["Hygiene function", "Hygienefunktion"],
    "opmode16": ["Silent mode", "Silent Modus"],
    "timemode0": ["Reduction", "Absenkung"],
    "timemode1": ["Deactivation", "Abschaltung"],
    "user_profile0": ["Profile A", "Profil A"],
    "user_profile1": ["Profile B", "Profil B"],
    "user_profile2": ["Profile C", "Profil C"],
}
