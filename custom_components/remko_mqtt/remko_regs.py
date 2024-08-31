# Remko generated register definitions
FIELD_REGNUM = 0
FIELD_REGTYPE = 1
FIELD_UNIT = 2
FIELD_MINVALUE = 3
FIELD_MAXVALUE = 4

# Query list
query_list = [1079, 1082, 1893, 1894, 1951, 1972, 1974, 5001, 5032, 5027, 5039, 5051, 5055, 5085, 5131, 5320, 5321, 5693]

# Register as sensors
reg_id = {
    #  reg_id: ['reg#', 'type', 'unit', 'min', 'max'],
    "dhw_opmode": ["1079", "select_input", "", 0, 16],
    "water_temp_req": ["1082", "temperature_input", "ºC", 20.0, 60.0],
    "absence_mode": ["1893", "switch", "", "", ""],
    "party_mode": ["1894", "switch", "", "", ""],
    "fixed_value": ["1972", "switch", "", "", ""],
    "fixed_value_temp_req": ["1974", "temperature_input", "ºC", 20.0, 60.0],
    "main_mode": ["1951", "select_input", "", "", ""],
    "opmode": ["5001", "sensor_mode", "", "", ""],
    "heat_gen_status": ["5051", "sensor_mode", "", "", ""],
    "out_temp": ["5032", "temperature", "ºC", 0, 40],
    "mixed_temp": ["5055", "temperature", "ºC", 0, 40],
    "water_temp": ["5039", "temperature", "ºC", 0, 70],
    "buffer_temp_target": ["5085", "temperature", "ºC", 0, 70],
    "buffer_temp": ["5131", "temperature", "ºC", 0, 70],
    "circulation_temp": ["5027", "temperature", "ºC", 0, 70],
    "el_consumption": ["5320", "sensor_el", "W", 0, 6000],
    "th_consumption": ["5321", "sensor_el", "W", 0, 20000],
    "dhw_heating": ["5693", "action", "", "", ""],
    "communication_status": ["communication_status", "generated_sensor", "", 0, 0],
}

# Translation dictionary
#  ['en', 'de']
id_names = {
    "water_temp_req": ["Water temp. req.", "Warmwasser soll"],
    "buffer_temp_target": ["Buffer temp. target", "Heizwasser Soll"],
    "fixed_value_temp_req": ["Fixed value", "Festwert"],
    "out_temp": ["Outside temp.", "Außentemperatur"],
    "mixed_temp": ["Mixed temp.", "Gemischte Temperatur"],
    "water_temp": ["Water temp.", "Warmwasser Temp."],
    "buffer_temp": ["Buffer temp.", "Heizwasser Temp."],
    "circulation_temp": ["Circulation temp.", "Zirkulation Temp."],
    "el_consumption": ["Electr. power", "Leistung elektrisch"],
    "th_consumption": ["Therm. power", "Leistung thermisch"],
    "main_mode": ["Room climate mode", "Raumklima Modus"],
    "opmode": ["Operating mode", "Betriebsmodus"],
    "heat_gen_status": ["Heat generator status", "Wärmeerzeuger Status"],
    "dhw_opmode": ["DHW mode", "WW Modus"],
    "absence_mode": ["Absence mode", "Abwesenheitssmodus"],
    "party_mode": ["Party mode", "Partymodus"],
    "fixed_value": ["Fixed value", "Festwert"],
    "dhw_heating": ["1x DHW heating", "1x WW aufheizen"],
    "mode1": ["Auto", "Auto"],
    "mode2": ["Heating", "Heizen"],
    "mode3": ["Standby", "Standby"],
    "mode4": ["Cooling", "Kühlen"],
    "dhwopmode0": ["Automatic comfort", "Automatik Komfort"],
    "dhwopmode1": ["Automatic eco", "Automatik Eco"],
    "dhwopmode2": ["Solar/PV only", "Nur Solar/PV"],
    "dhwopmode3": ["Off", "Aus"],
    "opmode1": ["Forced off", "Störung"],
    "opmode2": ["Defosting", "Abtauen"],
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
    "heatgenstatus0": ["OFF", "Aus"],
    "heatgenstatus1": ["ON", "An"]
}
