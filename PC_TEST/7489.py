from collections import OrderedDict

from arduino_to_pins import pin16
from base_test import TestSimplController, check, extract_bits_from_byte
from simpl_macros import OUTPUT_MODE, INPUT_PULLUP_MODE, INPUT_MODE

pins = OrderedDict(
    [
        ("A1", "0"),  # 1
        ("~CS", "1"),  # 2
        ("~WE", "1"),  # 3
        ("D1", "0"),  # 4
        ("~Q1", "X"),  # 5
        ("D2", "0"),  # 6
        ("~Q2", "X"),  # 7
        ("GND", "G"),  # 8
        ("~Q3", "X"),  # 9
        ("D3", "0"),  # 10
        ("~Q4", "X"),  # 11
        ("D4", "0"),  # 12
        ("A4", "0"),  # 13
        ("A3", "0"),  # 14
        ("A2", "0"),  # 15
        ("VCC", "V"),  # 16
    ]
)
COM_PORT = "COM13"
COM_BAUD = 2000000

CS_PIN = pin16[list(pins.keys()).index("~CS")]
WE_PIN = pin16[list(pins.keys()).index("~WE")]

A1_PIN = pin16[list(pins.keys()).index("A1")]
A2_PIN = pin16[list(pins.keys()).index("A2")]
A3_PIN = pin16[list(pins.keys()).index("A3")]
A4_PIN = pin16[list(pins.keys()).index("A4")]

D1_PIN = pin16[list(pins.keys()).index("D1")]
D2_PIN = pin16[list(pins.keys()).index("D2")]
D3_PIN = pin16[list(pins.keys()).index("D3")]
D4_PIN = pin16[list(pins.keys()).index("D4")]

Q1_PIN = pin16[list(pins.keys()).index("~Q1")]
Q2_PIN = pin16[list(pins.keys()).index("~Q2")]
Q3_PIN = pin16[list(pins.keys()).index("~Q3")]
Q4_PIN = pin16[list(pins.keys()).index("~Q4")]

GND_PIN = pin16[list(pins.keys()).index("GND")]
VCC_PIN = pin16[list(pins.keys()).index("VCC")]


class Test7489(TestSimplController):
    def __init__(self):
        super().__init__()
        self.send_command(f"{VCC_PIN}d{OUTPUT_MODE}1o" f"{GND_PIN}d{OUTPUT_MODE}0o")

        self.send_command(
            f"{WE_PIN}d{OUTPUT_MODE}1o"
            f"{CS_PIN}d{OUTPUT_MODE}1o"
            f"{A1_PIN}d{OUTPUT_MODE}0o"
            f"{A2_PIN}d{OUTPUT_MODE}0o"
            f"{A3_PIN}d{OUTPUT_MODE}0o"
            f"{A4_PIN}d{OUTPUT_MODE}0o"
        )

        self.send_command(
            f"{D1_PIN}d{OUTPUT_MODE}0o"
            f"{D2_PIN}d{OUTPUT_MODE}0o"
            f"{D3_PIN}d{OUTPUT_MODE}0o"
            f"{D4_PIN}d{OUTPUT_MODE}0o"
        )

        self.send_command(
            f"{Q1_PIN}d{INPUT_PULLUP_MODE}"
            f"{Q2_PIN}d{INPUT_PULLUP_MODE}"
            f"{Q3_PIN}d{INPUT_PULLUP_MODE}"
            f"{Q4_PIN}d{INPUT_PULLUP_MODE}"
        )

    def set_address(self, addr):
        a1, a2, a3, a4, *_ = extract_bits_from_byte(addr)

        self.send_command(
            f"{A1_PIN}d{a1}o" f"{A2_PIN}d{a2}o" f"{A3_PIN}d{a3}o" f"{A4_PIN}d{a4}o"
        )

    def set_data(self, data):
        d1, d2, d3, d4, *_ = extract_bits_from_byte(data)

        self.send_command(
            f"{D1_PIN}d{d1}o" f"{D2_PIN}d{d2}o" f"{D3_PIN}d{d3}o" f"{D4_PIN}d{d4}o"
        )

    def __del__(self):
        pass
        self.send_command(
            f"{WE_PIN}d{INPUT_MODE}"
            f"{CS_PIN}d{INPUT_MODE}"
            f"{A1_PIN}d{INPUT_MODE}"
            f"{A2_PIN}d{INPUT_MODE}"
            f"{A3_PIN}d{INPUT_MODE}"
            f"{A4_PIN}d{INPUT_MODE}"
        )
        self.send_command(
            f"{D1_PIN}d{INPUT_MODE}"
            f"{D2_PIN}d{INPUT_MODE}"
            f"{D3_PIN}d{INPUT_MODE}"
            f"{D4_PIN}d{INPUT_MODE}"
        )
        self.send_command(
            f"{Q1_PIN}d{INPUT_MODE}" f"{Q2_PIN}d{INPUT_MODE}" f"{Q3_PIN}d{INPUT_MODE}"
        )
        self.send_command(
            f"{Q4_PIN}d{INPUT_MODE}" f"{VCC_PIN}d{INPUT_MODE}" f"{GND_PIN}d{INPUT_MODE}"
        )


if __name__ == "__main__":
    uc = Test7489()

    for i in range(16):
        print(f"Check inverters pattern A:{i}")
        uc.set_address(i)

        for d in range(16):
            uc.set_data(d)

            response = uc.send_command(
                f"{CS_PIN}l"
                f"{WE_PIN}l"
                f"{Q1_PIN}diq"
                f"{Q2_PIN}diq"
                f"{Q3_PIN}diq"
                f"{Q4_PIN}diq"
                f"{WE_PIN}h"
                f"{CS_PIN}h"
            )
            expected = bytes(
                [ord("1") if ((d >> bit) & 1) == 0 else ord("0") for bit in range(4)]
            )

            check(response, expected)

    for shift in range(16):
        for i in range(16):
            d = i + shift
            print(f"Write A:{i}, {d}")
            uc.set_address(i)
            uc.set_data(d)

            response = uc.send_command(
                f"{CS_PIN}l" f"{WE_PIN}l" f"{WE_PIN}h" f"{CS_PIN}h"
            )

        for i in range(16):
            d = i + shift
            print(f"Read A:{i}")
            uc.set_address(i)

            response = uc.send_command(
                f"{CS_PIN}l"
                f"{Q1_PIN}diq"
                f"{Q2_PIN}diq"
                f"{Q3_PIN}diq"
                f"{Q4_PIN}diq"
                f"{WE_PIN}h"
                f"{CS_PIN}h"
            )
            expected = bytes(
                [ord("1") if ((d >> bit) & 1) == 0 else ord("0") for bit in range(4)]
            )

            check(response, expected)
