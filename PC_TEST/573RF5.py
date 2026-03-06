from arduino_to_pins import pin24
from base_test import TestSimplController, extract_bits_from_byte
from simpl_macros import OUTPUT_MODE, INPUT_MODE, INPUT_PULLUP_MODE

pins = [
    "A7",  # 1
    "A6",  # 2
    "A5",  # 3
    "A4",  # 4
    "A3",  # 5
    "A2",  # 6
    "A1",  # 7
    "A0",  # 8
    "D0",  # 9
    "D1",  # 10
    "D2",  # 11
    "GND",  # 12
    "D3",  # 13
    "D4",  # 14
    "D5",  # 15
    "D6",  # 16
    "D7",  # 17
    "~CS",  # 18
    "A10",  # 19
    "~OE",  # 20
    "VPP",  # 21
    "A9",  # 22
    "A8",  # 23
    "VCC",  # 24
]

A7_PIN = pin24[pins.index("A7")]
A6_PIN = pin24[pins.index("A6")]
A5_PIN = pin24[pins.index("A5")]
A4_PIN = pin24[pins.index("A4")]
A3_PIN = pin24[pins.index("A3")]
A2_PIN = pin24[pins.index("A2")]
A1_PIN = pin24[pins.index("A1")]
A0_PIN = pin24[pins.index("A0")]
D0_PIN = pin24[pins.index("D0")]
D1_PIN = pin24[pins.index("D1")]
D2_PIN = pin24[pins.index("D2")]
GND_PIN = pin24[pins.index("GND")]
D3_PIN = pin24[pins.index("D3")]
D4_PIN = pin24[pins.index("D4")]
D5_PIN = pin24[pins.index("D5")]
D6_PIN = pin24[pins.index("D6")]
D7_PIN = pin24[pins.index("D7")]
CS_PIN = pin24[pins.index("~CS")]
A10_PIN = pin24[pins.index("A10")]
OE_PIN = pin24[pins.index("~OE")]
VPP_PIN = pin24[pins.index("VPP")]
A9_PIN = pin24[pins.index("A9")]
A8_PIN = pin24[pins.index("A8")]
VCC_PIN = pin24[pins.index("VCC")]


class Test573RF5(TestSimplController):
    def __init__(self):
        super().__init__()
        self.send_command(f"{VCC_PIN}d{OUTPUT_MODE}1o" f"{GND_PIN}d{OUTPUT_MODE}0o")

        self.all_d_to_input()

        self.send_command(
            f"{VPP_PIN}d{OUTPUT_MODE}1o"
            f"{OE_PIN}d{OUTPUT_MODE}0o"
            f"{CS_PIN}d{OUTPUT_MODE}0o"
        )

        self.send_command(
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
            f"{A10_PIN}d{OUTPUT_MODE}0o"
        )

    def all_d_to_input(self):
        self.send_command(
            f"{D0_PIN}d{INPUT_MODE}"
            f"{D1_PIN}d{INPUT_MODE}"
            f"{D2_PIN}d{INPUT_MODE}"
            f"{D3_PIN}d{INPUT_MODE}"
            f"{D4_PIN}d{INPUT_MODE}"
            f"{D5_PIN}d{INPUT_MODE}"
            f"{D6_PIN}d{INPUT_MODE}"
            f"{D7_PIN}d{INPUT_MODE}"
        )

    def all_d_to_output(self):
        self.send_command(
            f"{D0_PIN}d{OUTPUT_MODE}"
            f"{D1_PIN}d{OUTPUT_MODE}"
            f"{D2_PIN}d{OUTPUT_MODE}"
            f"{D3_PIN}d{OUTPUT_MODE}"
            f"{D4_PIN}d{OUTPUT_MODE}"
            f"{D5_PIN}d{OUTPUT_MODE}"
            f"{D6_PIN}d{OUTPUT_MODE}"
            f"{D7_PIN}d{OUTPUT_MODE}"
        )

    def set_address(self, addr: int):
        a0, a1, a2, a3, a4, a5, a6, a7, a8, a9, a10, *_ = extract_bits_from_byte(addr)

        self.send_command(
            f"{A0_PIN}d{OUTPUT_MODE}{a0}o"
            f"{A1_PIN}d{OUTPUT_MODE}{a1}o"
            f"{A2_PIN}d{OUTPUT_MODE}{a2}o"
            f"{A3_PIN}d{OUTPUT_MODE}{a3}o"
            f"{A4_PIN}d{OUTPUT_MODE}{a4}o"
            f"{A5_PIN}d{OUTPUT_MODE}{a5}o"
            f"{A6_PIN}d{OUTPUT_MODE}{a6}o"
            f"{A7_PIN}d{OUTPUT_MODE}{a7}o"
            f"{A8_PIN}d{OUTPUT_MODE}{a8}o"
            f"{A9_PIN}d{OUTPUT_MODE}{a9}o"
            f"{A10_PIN}d{OUTPUT_MODE}{a10}o"
        )

    def write(self, data: int):
        d0, d1, d2, d3, d4, d5, d6, d7, *_ = extract_bits_from_byte(data)

        self.send_command(
            f"{D0_PIN}d{OUTPUT_MODE}{d0}o"
            f"{D1_PIN}d{OUTPUT_MODE}{d1}o"
            f"{D2_PIN}d{OUTPUT_MODE}{d2}o"
            f"{D3_PIN}d{OUTPUT_MODE}{d3}o"
            f"{D4_PIN}d{OUTPUT_MODE}{d4}o"
            f"{D5_PIN}d{OUTPUT_MODE}{d5}o"
            f"{D6_PIN}d{OUTPUT_MODE}{d6}o"
            f"{D7_PIN}d{OUTPUT_MODE}{d7}o"
        )

    def read(self):
        result = self.send_command(
            f"{D0_PIN}d{INPUT_PULLUP_MODE}iq"
            f"{D1_PIN}d{INPUT_PULLUP_MODE}iq"
            f"{D2_PIN}d{INPUT_PULLUP_MODE}iq"
            f"{D3_PIN}d{INPUT_PULLUP_MODE}iq"
            f"{D4_PIN}d{INPUT_PULLUP_MODE}iq"
            f"{D5_PIN}d{INPUT_PULLUP_MODE}iq"
            f"{D6_PIN}d{INPUT_PULLUP_MODE}iq"
            f"{D7_PIN}d{INPUT_PULLUP_MODE}iq"
        )
        return result


if __name__ == "__main__":
    uc = Test573RF5()

    for i in range(2048):
        uc.set_address(i)
        # print(uc.read(i))
