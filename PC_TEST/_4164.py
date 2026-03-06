import random

from arduino_to_pins import pin16
from base_test import TestSimplController, check, extract_bits_from_byte
from pattern_generator import get_bit_from_pattern
from simpl_macros import OUTPUT_MODE, INPUT_PULLUP_MODE
from tqdm import tqdm

from pins_4164 import pins

W_PIN = pin16[pins.index("~W")]
A2_PIN = pin16[pins.index("A2")]
RAS_PIN = pin16[pins.index("~RAS")]
A0_PIN = pin16[pins.index("A0")]
DI_PIN = pin16[pins.index("DI")]
A7_PIN = pin16[pins.index("A7")]
A5_PIN = pin16[pins.index("A5")]
A4_PIN = pin16[pins.index("A4")]
A3_PIN = pin16[pins.index("A3")]
VCC_PIN = pin16[pins.index("VCC")]
DO_PIN = pin16[pins.index("DO")]
A1_PIN = pin16[pins.index("A1")]
CAS_PIN = pin16[pins.index("~CAS")]
GND_PIN = pin16[pins.index("GND")]
A6_PIN = pin16[pins.index("A6")]


class Test4164(TestSimplController):
    def __init__(self):
        super().__init__()
        self.send_command(f"{VCC_PIN}d{OUTPUT_MODE}1o" f"{GND_PIN}d{OUTPUT_MODE}0o")

        self.send_command(
            f"{RAS_PIN}d{OUTPUT_MODE}1o"
            f"{CAS_PIN}d{OUTPUT_MODE}1o"
            f"{W_PIN}d{OUTPUT_MODE}1o"
            f"{A0_PIN}d{OUTPUT_MODE}0o"
            f"{A1_PIN}d{OUTPUT_MODE}0o"
        )
        self.send_command(
            f"{A2_PIN}d{OUTPUT_MODE}0o"
            f"{A3_PIN}d{OUTPUT_MODE}0o"
            f"{A4_PIN}d{OUTPUT_MODE}0o"
            f"{A5_PIN}d{OUTPUT_MODE}0o"
            f"{A6_PIN}d{OUTPUT_MODE}0o"
        )
        self.send_command(
            f"{A7_PIN}d{OUTPUT_MODE}0o"
            f"{DI_PIN}d{OUTPUT_MODE}0o"
            f"{DO_PIN}d{INPUT_PULLUP_MODE}"
        )

    ASSERT_RAS = f"{RAS_PIN}l"
    DEASSERT_RAS = f"{RAS_PIN}h"

    ASSERT_CAS = f"{CAS_PIN}l"
    DEASSERT_CAS = f"{CAS_PIN}h"

    ASSERT_WRITE = f"{W_PIN}l"
    DEASSERT_WRITE = f"{W_PIN}h"

    def read(self, addr):
        a0, a1, a2, a3, a4, a5, a6, a7, a8, a9, a10, a11, a12, a13, a14, a15 = (
            extract_bits_from_byte(addr)
        )

        result = self.send_command(
            f"{A0_PIN}d{a0}o"
            f"{A1_PIN}d{a1}o"
            f"{A2_PIN}d{a2}o"
            f"{A3_PIN}d{a3}o"
            f"{A4_PIN}d{a4}o"
            f"{A5_PIN}d{a5}o"
            f"{A6_PIN}d{a6}o"
            f"{A7_PIN}d{a7}o"
            f"{self.ASSERT_RAS}"
            f"{A0_PIN}d{a8}o"
            f"{A1_PIN}d{a9}o"
            f"{A2_PIN}d{a10}o"
            f"{A3_PIN}d{a11}o"
            f"{A4_PIN}d{a12}o"
            f"{A5_PIN}d{a13}o"
            f"{A6_PIN}d{a14}o"
            f"{A7_PIN}d{a15}o"
            f"{self.ASSERT_CAS}"
            f"{DO_PIN}diq"
            f"{self.DEASSERT_RAS}"
            f"{self.DEASSERT_CAS}"
        )

        return result

    def write(self, addr: int, value: int):
        a0 = (addr >> 0) & 1
        a1 = (addr >> 1) & 1
        a2 = (addr >> 2) & 1
        a3 = (addr >> 3) & 1
        a4 = (addr >> 4) & 1
        a5 = (addr >> 5) & 1
        a6 = (addr >> 6) & 1

        a7 = (addr >> 7) & 1
        a8 = (addr >> 8) & 1
        a9 = (addr >> 9) & 1
        a10 = (addr >> 10) & 1
        a11 = (addr >> 11) & 1
        a12 = (addr >> 12) & 1
        a13 = (addr >> 13) & 1
        a14 = (addr >> 14) & 1
        a15 = (addr >> 15) & 1

        self.send_command(
            f"{A0_PIN}d{a0}o"
            f"{A1_PIN}d{a1}o"
            f"{A2_PIN}d{a2}o"
            f"{A3_PIN}d{a3}o"
            f"{A4_PIN}d{a4}o"
            f"{A5_PIN}d{a5}o"
            f"{A6_PIN}d{a6}o"
            f"{A7_PIN}d{a7}o"
            f"{self.ASSERT_RAS}"
            f"{self.ASSERT_WRITE}"
            f"{A0_PIN}d{a8}o"
            f"{A1_PIN}d{a9}o"
            f"{A2_PIN}d{a10}o"
            f"{A3_PIN}d{a11}o"
            f"{A4_PIN}d{a12}o"
            f"{A5_PIN}d{a13}o"
            f"{A6_PIN}d{a14}o"
            f"{A7_PIN}d{a15}o"
            f"{DI_PIN}d{value}o"
            f"{self.ASSERT_CAS}"
            f"{self.DEASSERT_WRITE}"
            f"{self.DEASSERT_RAS}"
            f"{self.DEASSERT_CAS}"
        )

    def __del__(self):
        pass


if __name__ == "__main__":
    uc = Test4164()

    for pattern in [
        [random.randint(0, 0xFF) for _ in range(8192)],
        [0x00 for _ in range(8192)],
        [0xFF for _ in range(8192)],
        [0xAA for _ in range(8192)],
        [0xCC for _ in range(8192)],
        [0x01 for _ in range(8192)],
        [0x02 for _ in range(8192)],
        [0x04 for _ in range(8192)],
        [0x08 for _ in range(8192)],
        [0x10 for _ in range(8192)],
        [0x20 for _ in range(8192)],
        [0x40 for _ in range(8192)],
        [0x80 for _ in range(8192)],
    ]:
        for i in tqdm(
            range(64 * 1024),
            desc=f"Writing to memory pattern {pattern[0:1]}",
            unit="address",
        ):
            uc.write(i, get_bit_from_pattern(pattern, i))

        for i in tqdm(
            range(64 * 1024),
            desc=f"Reading from memory pattern {pattern[0:1]}",
            unit="address",
        ):
            read = uc.read(i)

            if get_bit_from_pattern(pattern, i):
                expected = b"1"
            else:
                expected = b"0"

            check(read, expected)
