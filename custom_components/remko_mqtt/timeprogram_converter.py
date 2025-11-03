import logging
from typing import Dict, List, Optional
import uuid


_LOGGER = logging.getLogger(__name__)


# 15-Minutes slots per day
SLOTS_PER_DAY = 96
SLOTS_PER_HOUR = 4


# Remko-internal order of weekdays
DAYS_REMKO = ["Sa", "Fr", "Di", "Mi", "Do", "Mo", "So"]
WEEKDAYS_REMKO = ["sat", "fri", "tue", "wed", "thu", "mon", "sun"]


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
    @staticmethod
    def hex_to_timeprogram(hex_string: str) -> dict:
        try:
            if not hex_string or len(hex_string) != 168:
                _LOGGER.error(
                    f"Invalid hex length: {len(hex_string) if hex_string else 0}"
                )
                return RemkoTimeProgramConverter._create_empty_timeprogram()

            timeprogram = RemkoTimeProgramConverter._create_empty_timeprogram()

            WEEKDAYS_REMKO = ["sat", "fri", "tue", "wed", "thu", "mon", "sun"]

            for day_idx, weekday in enumerate(WEEKDAYS_REMKO):
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

            return timeprogram

        except Exception as e:
            _LOGGER.error(f"Error converting hex to time program: {e}")
            return RemkoTimeProgramConverter._create_empty_timeprogram()

    @staticmethod
    def timeprogram_to_hex(timeprogram: dict) -> Optional[str]:
        try:
            if not timeprogram or not isinstance(timeprogram, dict):
                return None

            hex_string = ""

            for weekday in WEEKDAYS_REMKO:
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

            if len(hex_string) == 168:
                _LOGGER.debug(f"Time program to Hex: {hex_string}")
                return hex_string
            else:
                _LOGGER.error(f"Invalid hex length: {len(hex_string)}")
                return None

        except Exception as e:
            _LOGGER.error(f"Error converting time program to hex: {e}")
            return None

    @staticmethod
    def _find_timeslots(bit_string: str) -> List[Dict]:
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
        hours = slot // 4
        minutes = (slot % 4) * 15

        if hours >= 24:
            hours = 0

        return f"{hours:02d}:{minutes:02d}"

    @staticmethod
    def _time_to_slot(time_str: str) -> int:
        try:
            parts = time_str.split(":")
            hours = int(parts[0])
            minutes = int(parts[1])

            slot = hours * 4 + minutes // 15
            return min(slot, SLOTS_PER_DAY - 1)
        except:
            return 0

    @staticmethod
    def _create_empty_timeprogram() -> dict:
        return {
            "mon": {"timeslots": []},
            "tue": {"timeslots": []},
            "wed": {"timeslots": []},
            "thu": {"timeslots": []},
            "fri": {"timeslots": []},
            "sat": {"timeslots": []},
            "sun": {"timeslots": []},
        }
