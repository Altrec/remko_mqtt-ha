"""Module for Remko MQTT timeprogram conversion."""

import logging

_LOGGER = logging.getLogger(__name__)


# 15-Minutes slots per day
SLOTS_PER_DAY = 96
SLOTS_PER_HOUR = 4


# Remko-internal order of weekdays
DAYS_REMKO = ["Sa", "Fr", "Di", "Mi", "Do", "Mo", "So"]
REMKO_WEEKDAYS = ["sat", "fri", "tue", "wed", "thu", "mon", "sun"]


# Weekday order for simplified time program
WEEKDAY_ORDER = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


# Mapping weekdays → Remko-Byte-Index
WEEKDAY_TO_REMKO_INDEX = {
    "sat": 0,
    "fri": 1,
    "tue": 2,
    "wed": 3,
    "thu": 4,
    "mon": 5,
    "sun": 6,
}


class RemkoTimeProgramConverter:
    """Converter for Remko timeprograms between hex strings and dict representations."""

    @staticmethod
    def hex_to_timeprogram(hex_string: str) -> dict:
        """Convert a 168-character hex string into a timeprogram dict."""
        if not hex_string or len(hex_string) != 168:
            _LOGGER.error(
                "Invalid hex length: %s", len(hex_string) if hex_string else 0
            )
            return RemkoTimeProgramConverter._create_empty_timeprogram()

        try:
            timeprogram = RemkoTimeProgramConverter._create_empty_timeprogram()

            for day_idx, weekday in enumerate(REMKO_WEEKDAYS):
                day_hex = hex_string[day_idx * 24 : (day_idx + 1) * 24]

                # Reverse the hex string for this day (read from right to left)
                day_hex_reversed = day_hex[::-1]

                bit_string = ""
                for hex_char in day_hex_reversed:
                    nibble_val = int(hex_char, 16)
                    bits = format(nibble_val, "04b")
                    # Also reverse the bits within each nibble
                    bits_reversed = bits[::-1]
                    bit_string += bits_reversed

                timeslots = RemkoTimeProgramConverter._find_timeslots(bit_string)
                timeprogram[weekday]["timeslots"] = timeslots

        except (ValueError, KeyError, IndexError) as err:
            _LOGGER.error("Error converting hex to time program: %s", err)
            return RemkoTimeProgramConverter._create_empty_timeprogram()
        else:
            return timeprogram

    @staticmethod
    def timeprogram_to_hex(timeprogram: dict) -> str | None:
        """Convert a timeprogram dict into a 168-character hex string."""
        if not timeprogram or not isinstance(timeprogram, dict):
            return None

        try:
            hex_string = ""

            for weekday in REMKO_WEEKDAYS:
                bit_string = ["0"] * 96

                timeslots = timeprogram.get(weekday, {}).get("timeslots", [])

                for ts in timeslots:
                    if ts.get("on", False):
                        start_slot = RemkoTimeProgramConverter._time_to_slot(
                            ts.get("start", "00:00")
                        )
                        stop_slot = RemkoTimeProgramConverter._time_to_slot(
                            ts.get("stop", "00:00")
                        )

                        if stop_slot == 0:
                            stop_slot = 96

                        for i in range(start_slot, stop_slot):
                            if i < 96:
                                bit_string[i] = "1"

                bit_str = "".join(bit_string)

                # Reverse the bit string (right to left reading)
                bit_str_reversed = bit_str[::-1]

                day_hex = ""
                for hour_idx in range(24):
                    bits_for_hour = bit_str_reversed[hour_idx * 4 : (hour_idx + 1) * 4]
                    # Reverse bits within each nibble
                    bits_for_hour_reversed = bits_for_hour[::-1]
                    hex_nibble = format(int(bits_for_hour_reversed, 2), "X")
                    day_hex += hex_nibble

                hex_string += day_hex

        except (ValueError, KeyError, TypeError, AttributeError) as err:
            _LOGGER.error("Error converting time program to hex: %s", err)
            return None

        if len(hex_string) == 168:
            _LOGGER.debug("Time program to Hex: %s", hex_string)
            return hex_string

        _LOGGER.error("Invalid hex length: %s", len(hex_string))
        return None

    @staticmethod
    def _find_timeslots(bit_string: str) -> list[dict]:
        """Parse bit string into a list of timeslot dictionaries."""
        timeslots = []
        in_timeslot = False
        start_slot = 0

        for i, bit in enumerate(bit_string):
            if bit == "1" and not in_timeslot:
                start_slot = i
                in_timeslot = True
            elif bit == "0" and in_timeslot:
                end_slot = i
                in_timeslot = False

                start_time = RemkoTimeProgramConverter._slot_to_time(start_slot)
                stop_time = RemkoTimeProgramConverter._slot_to_time(end_slot)

                timeslots.append({"start": start_time, "stop": stop_time, "on": True})

        if in_timeslot:
            end_slot = SLOTS_PER_DAY
            start_time = RemkoTimeProgramConverter._slot_to_time(start_slot)
            stop_time = RemkoTimeProgramConverter._slot_to_time(end_slot)

            timeslots.append({"start": start_time, "stop": stop_time, "on": True})

        return timeslots

    @staticmethod
    def _slot_to_time(slot: int) -> str:
        """Convert a 15-minute slot index (0..95) into 'HH:MM' format."""
        hours = slot // 4
        minutes = (slot % 4) * 15

        if hours >= 24:
            hours = 0

        return f"{hours:02d}:{minutes:02d}"

    @staticmethod
    def _time_to_slot(time_str: str) -> int:
        """Convert 'HH:MM' string to 15-minute slot index."""
        try:
            parts = time_str.split(":")
            hours = int(parts[0])
            minutes = int(parts[1])

            slot = hours * 4 + minutes // 15
            return min(slot, SLOTS_PER_DAY - 1)
        except ValueError, IndexError, AttributeError:
            return 0

    @staticmethod
    def _create_empty_timeprogram() -> dict:
        """Create an empty timeprogram structure with all days initialized."""
        return {
            "mon": {"timeslots": []},
            "tue": {"timeslots": []},
            "wed": {"timeslots": []},
            "thu": {"timeslots": []},
            "fri": {"timeslots": []},
            "sat": {"timeslots": []},
            "sun": {"timeslots": []},
        }
