import os
import random
import time

from tqdm import tqdm

from arduino_to_pins import pin16
from base_test import TestSimplController, check, extract_bits_from_byte
from pattern_generator import generate_memory_patterns, get_bit_from_pattern
from simpl_macros import OUTPUT_MODE, INPUT_PULLUP_MODE, INPUT_MODE

pins = [
    "A6",  # 1
    "A5",  # 2
    "R/W",  # 3
    "A1",  # 4
    "A2",  # 5
    "A3",  # 6
    "A4",  # 7
    "A0",  # 8
    "GND",  # 9
    "VCC",  # 10
    "DI",  # 11
    "DO",  # 12
    "~CE",  # 13
    "A9",  # 14
    "A8",  # 15
    "A7",  # 16
]

VCC_PIN = pin16[pins.index("VCC")]
GND_PIN = pin16[pins.index("GND")]
A6_PIN = pin16[pins.index("A6")]
A5_PIN = pin16[pins.index("A5")]
RW_PIN = pin16[pins.index("R/W")]
A1_PIN = pin16[pins.index("A1")]
A2_PIN = pin16[pins.index("A2")]
A3_PIN = pin16[pins.index("A3")]
A4_PIN = pin16[pins.index("A4")]
A0_PIN = pin16[pins.index("A0")]
DI_PIN = pin16[pins.index("DI")]
DO_PIN = pin16[pins.index("DO")]
CE_PIN = pin16[pins.index("~CE")]
A9_PIN = pin16[pins.index("A9")]
A8_PIN = pin16[pins.index("A8")]
A7_PIN = pin16[pins.index("A7")]


class TestK565RU2(TestSimplController):
    def __init__(self):
        super().__init__()
        self.send_command(f"{VCC_PIN}d{OUTPUT_MODE}1o" f"{GND_PIN}d{OUTPUT_MODE}0o")

        self.send_command(
            f"{RW_PIN}d{OUTPUT_MODE}1o"
            f"{CE_PIN}d{OUTPUT_MODE}1o"
            f"{A0_PIN}d{OUTPUT_MODE}0o"
            f"{A1_PIN}d{OUTPUT_MODE}0o"
            f"{A2_PIN}d{OUTPUT_MODE}0o"
            f"{A3_PIN}d{OUTPUT_MODE}0o"
            f"{A4_PIN}d{OUTPUT_MODE}0o"
            f"{A5_PIN}d{OUTPUT_MODE}0o"
            f"{A6_PIN}d{OUTPUT_MODE}0o"
            f"{A7_PIN}d{OUTPUT_MODE}0o"
            f"{A8_PIN}d{OUTPUT_MODE}0o"
            f"{A9_PIN}d{OUTPUT_MODE}0o"
            f"{DI_PIN}d{OUTPUT_MODE}0o"
        )

        self.send_command(f"{DO_PIN}d{INPUT_PULLUP_MODE}")

    def set_address(self, addr):
        a0, a1, a2, a3, a4, a5, a6, a7, a8, a9, *_ = extract_bits_from_byte(addr)

        self.send_command(
            f"{A0_PIN}d{a0}o"
            f"{A1_PIN}d{a1}o"
            f"{A2_PIN}d{a2}o"
            f"{A3_PIN}d{a3}o"
            f"{A4_PIN}d{a4}o"
            f"{A5_PIN}d{a5}o"
            f"{A6_PIN}d{a6}o"
            f"{A7_PIN}d{a7}o"
            f"{A8_PIN}d{a8}o"
            f"{A9_PIN}d{a9}o"
        )

    def set_data(self, data):
        d1 = (data >> 0) & 1
        self.send_command(f"{DI_PIN}d{d1}o")

    def read_data(self):
        return self.send_command(f"{DO_PIN}d{INPUT_PULLUP_MODE}iq")


if __name__ == "__main__":
    uc = TestK565RU2()

    # Generate patterns
    patterns = generate_memory_patterns()

    random.seed(int(time.time() * 1000) ^ os.getpid())

    for pattern in [
        [random.randint(0, 0xFF) for _ in range(128)],
        [0x00 for _ in range(128)],
        [0xFF for _ in range(128)],
        [0xAA for _ in range(128)],
        [0xCC for _ in range(128)],
        [0x01 for _ in range(128)],
        [0x02 for _ in range(128)],
        [0x04 for _ in range(128)],
        [0x08 for _ in range(128)],
        [0x10 for _ in range(128)],
        [0x20 for _ in range(128)],
        [0x40 for _ in range(128)],
        [0x80 for _ in range(128)],
    ]:
        for i in tqdm(
            range(1024),
            desc=f"Writing to memory pattern {pattern[0:1]}",
            unit="address",
        ):
            uc.set_address(i)
            bit = get_bit_from_pattern(pattern, i)
            uc.send_command(
                f"{CE_PIN}d0o"
                f"{DI_PIN}d{bit}o"
                f"{RW_PIN}d0o"
                f"10n"
                f"{RW_PIN}d1o"
                f"{CE_PIN}d1o"
            )

        for i in tqdm(
            range(1024),
            desc=f"Reading from memory pattern {pattern[0:1]}",
            unit="address",
        ):
            uc.set_address(i)
            result = uc.send_command(f"{CE_PIN}d0o" f"1u" f"{DO_PIN}diq" f"{CE_PIN}d1o")

            if get_bit_from_pattern(pattern, i):
                expected = b"1"
            else:
                expected = b"0"

            check(result, expected)

    print("ALL OK")
