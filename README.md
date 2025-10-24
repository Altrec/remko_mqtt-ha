# Home Assistant Remko-MQTT Integration

![python badge](https://img.shields.io/badge/Made%20with-Python-orange)
![HassFest tests](https://github.com/Altrec/remko_mqtt-ha/workflows/Validate%20with%20hassfest/badge.svg)
![github contributors](https://img.shields.io/github/contributors/Altrec/remko_mqtt-ha)
![last commit](https://img.shields.io/github/last-commit/Altrec/remko_mqtt-ha)

This integration allows you to control and monitor your Remko heatpump from Home Assistant. 

# Prerequisite
You need a configured MQTT connection to your heatpump. (Directly or via a broker like Mosquitto). Username and password are needed for the connection.
- The username is "0000000000000000"
- The password can be found in the smt.min.js file from the web interface.
- ![smt.min.js](docs/smt.min.js.png)

# Steps to install
The integration can be installed via [HACS](https://hacs.xyz/), or by manually copying the [`remko_mqtt`](https://github.com/Altrec/remko_mqtt-ha/tree/master/custom_components/) directory to Home Assistant's `config/custom_components/` directory.

# Configuration
This integration can be configured through the Home Assistant UI. From the Devices & Services page click 'Add Integration' and search for 'Remko MQTT'.

_The heatpump sends a message every second. To reduce log entries you can skip messages with the 'Skipped MQTT messages' config option._

## Debugging
Make sure you see proper mqtt messages from the heatpump in a MQTT-Explorer before setting up HA.

Debug messages are not yet fully implemented.

# Available data
The data available is listed in [REGISTERS.md](https://github.com/Altrec/remko_mqtt-ha/blob/master/REGISTERS.md)

# Features and Limitations
- Currently, provides all data from the heatpump in the form of sensors and binary sensors
- Allows control over the heatpump
- Only works with software versions 4.26+ (earlier version are not yet tested)

# Contributing
Contributions are welcome! If you'd like to contribute, feel free to pick up anything on the current [GitHub issues](https://github.com/Altrec/remko_mqtt-ha/issues) list!
The naming, translation and grouping of registers can be improved, your input is appreciated. Most of it is in the [remko_regs.py](https://github.com/Altrec/remko_mqtt-ha/blob/master/custom_components/remko_mqtt/remko_regs.py)  

All help improving the integration is appreciated!







