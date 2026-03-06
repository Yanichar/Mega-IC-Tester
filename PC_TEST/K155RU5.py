from collections import OrderedDict

from arduino_to_pins import pin16
from base_test import TestSimplController, check, extract_bits_from_byte
from pattern_generator import generate_memory_patterns, get_bit_from_pattern
from simpl_macros import OUTPUT_MODE, INPUT_PULLUP_MODE, INPUT_MODE

pins = OrderedDict(
    [
        ("A1", "0"),  # 1
        ("A2", "1"),  # 2
        ("A3", "1"),  # 3
        ("A4", "0"),  # 4
        ("~CS1", "X"),  # 5
        ("~CS2", "0"),  # 6
        ("CS3", "X"),  # 7
        ("GND", "G"),  # 8
        ("DI", "X"),  # 9
        ("~WE", "0"),  # 10
        ("Y", "X"),  # 11
        ("B1", "0"),  # 12
        ("B2", "0"),  # 13
        ("B3", "0"),  # 14
        ("B4", "0"),  # 15
        ("VCC", "V"),  # 16
    ]
)

A2_PIN = pin16[list(pins.keys()).index("A2")]
A3_PIN = pin16[list(pins.keys()).index("A3")]
A1_PIN = pin16[list(pins.keys()).index("A1")]
A4_PIN = pin16[list(pins.keys()).index("A4")]
CS1_PIN = pin16[list(pins.keys()).index("~CS1")]
CS2_PIN = pin16[list(pins.keys()).index("~CS2")]
CS3_PIN = pin16[list(pins.keys()).index("CS3")]
GND_PIN = pin16[list(pins.keys()).index("GND")]
DI_PIN = pin16[list(pins.keys()).index("DI")]
WE_PIN = pin16[list(pins.keys()).index("~WE")]
Y_PIN = pin16[list(pins.keys()).index("Y")]
B1_PIN = pin16[list(pins.keys()).index("B1")]
B2_PIN = pin16[list(pins.keys()).index("B2")]
B3_PIN = pin16[list(pins.keys()).index("B3")]
B4_PIN = pin16[list(pins.keys()).index("B4")]
VCC_PIN = pin16[list(pins.keys()).index("VCC")]


class TestR155RU5(TestSimplController):
    def __init__(self):
        super().__init__()
        self.send_command(f"{VCC_PIN}d{OUTPUT_MODE}1o" f"{GND_PIN}d{OUTPUT_MODE}0o")

        self.send_command(
            f"{WE_PIN}d{OUTPUT_MODE}1o"
            f"{CS1_PIN}d{OUTPUT_MODE}1o"
            f"{CS2_PIN}d{OUTPUT_MODE}1o"
            f"{CS3_PIN}d{OUTPUT_MODE}0o"
            f"{A1_PIN}d{OUTPUT_MODE}0o"
            f"{A2_PIN}d{OUTPUT_MODE}0o"
            f"{A3_PIN}d{OUTPUT_MODE}0o"
            f"{A4_PIN}d{OUTPUT_MODE}0o"
        )

        self.send_command(
            f"{B1_PIN}d{OUTPUT_MODE}0o"
            f"{B2_PIN}d{OUTPUT_MODE}0o"
            f"{B3_PIN}d{OUTPUT_MODE}0o"
            f"{B4_PIN}d{OUTPUT_MODE}0o"
            f"{DI_PIN}d{OUTPUT_MODE}0o"
        )

        self.send_command(f"{Y_PIN}d{INPUT_PULLUP_MODE}")

    def set_address(self, addr):
        a1, a2, a3, a4, b1, b2, b3, b4, *_ = extract_bits_from_byte(addr)

        self.send_command(
            f"{A1_PIN}d{a1}o"
            f"{A2_PIN}d{a2}o"
            f"{A3_PIN}d{a3}o"
            f"{A4_PIN}d{a4}o"
            f"{B1_PIN}d{b1}o"
            f"{B2_PIN}d{b2}o"
            f"{B3_PIN}d{b3}o"
            f"{B4_PIN}d{b4}o"
        )

    def set_data(self, data):
        d1 = (data >> 0) & 1

        self.send_command(f"{DI_PIN}d{d1}o")

    def __del__(self):
        super().__del__()
        self.send_command(
            f"{WE_PIN}d{INPUT_MODE}1o"
            f"{CS1_PIN}d{INPUT_MODE}1o"
            f"{CS2_PIN}d{INPUT_MODE}1o"
            f"{CS3_PIN}d{INPUT_MODE}0o"
            f"{A1_PIN}d{INPUT_MODE}0o"
            f"{A2_PIN}d{INPUT_MODE}0o"
            f"{A3_PIN}d{INPUT_MODE}0o"
            f"{A4_PIN}d{INPUT_MODE}0o"
        )

        self.send_command(
            f"{B1_PIN}d{INPUT_MODE}0o"
            f"{B2_PIN}d{INPUT_MODE}0o"
            f"{B3_PIN}d{INPUT_MODE}0o"
            f"{B4_PIN}d{INPUT_MODE}0o"
            f"{DI_PIN}d{INPUT_MODE}0o"
        )

        self.send_command(f"{VCC_PIN}d{INPUT_MODE}" f"{GND_PIN}d{INPUT_MODE}")


def print_patterns(data):
    """Prints patterns in a readable format"""
    for i, p in enumerate(data, 1):
        print(f"Pattern {i:2d}: ", end="")
        for j, byte in enumerate(p):
            if j > 0 and j % 8 == 0:
                print(" ", end="")
            print(f"{byte:02X}", end=" ")
        print()


def save_patterns_to_file(data, filename="memory_patterns.bin"):
    """Saves patterns to a binary file"""
    with open(filename, "wb") as f:
        for p in data:
            f.write(p)
    print(f"Patterns saved to file: {filename}")


if __name__ == "__main__":
    uc = TestR155RU5()

    # Generate patterns
    patterns = generate_memory_patterns()

    for pattern in patterns:
        print(f"---===Pattern {pattern}===---")
        for a in range(256):
            # print(f"Write {a}, {get_bit_from_pattern(pattern, a)}")
            uc.set_address(a)
            uc.set_data(get_bit_from_pattern(pattern, a))

            response = uc.send_command(
                f"{CS1_PIN}l"
                f"{CS2_PIN}l"
                f"{CS3_PIN}h"
                f"{WE_PIN}l"
                f"10u"
                f"{WE_PIN}h"
                f"{CS1_PIN}h"
                f"{CS2_PIN}h"
                f"{CS3_PIN}l"
            )

        pass

        for a in range(256):
            # print(f"Read {a}")
            uc.set_address(a)

            # fmt: off
            response = uc.send_command(
                f"{WE_PIN}h"
                f"{CS1_PIN}l"
                f"{CS2_PIN}l"
                f"{CS3_PIN}h" 
                f"10u"
                f"{Y_PIN}diq"
                f"{CS1_PIN}h"
                f"{CS2_PIN}h"
                f"{CS3_PIN}l"

            )
            # fmt: on

            expected_byte = b"1" if get_bit_from_pattern(pattern, a) else b"0"
            check(response, expected_byte)

    # for i in range(16):
    #     print(f"Check inverters pattern A:{i}")
    #     uc.set_address(i)
    #
    #     for d in range(16):
    #         uc.set_data(d)
    #
    #         response = uc.send_command(
    #             f"{CS_PIN}l"
    #             f"{WE_PIN}l"
    #             f"{Q1_PIN}diq"
    #             f"{Q2_PIN}diq"
    #             f"{Q3_PIN}diq"
    #             f"{Q4_PIN}diq"
    #             f"{WE_PIN}h"
    #             f"{CS_PIN}h"
    #         )
    #         expected = bytes(
    #             [ord("1") if ((d >> bit) & 1) == 0 else ord("0") for bit in range(4)]
    #         )
    #
    #         CHECK(response, expected)
    #
    # for shift in range(16):
    #     for i in range(16):
    #         d = i + shift
    #         print(f"Write A:{i}, {d}")
    #         uc.set_address(i)
    #         uc.set_data(d)
    #
    #         response = uc.send_command(
    #             f"{CS_PIN}l" f"{WE_PIN}l" f"{WE_PIN}h" f"{CS_PIN}h"
    #         )
    #
    #     for i in range(16):
    #         d = i + shift
    #         print(f"Read A:{i}")
    #         uc.set_address(i)
    #
    #         response = uc.send_command(
    #             f"{CS_PIN}l"
    #             f"{Q1_PIN}diq"
    #             f"{Q2_PIN}diq"
    #             f"{Q3_PIN}diq"
    #             f"{Q4_PIN}diq"
    #             f"{WE_PIN}h"
    #             f"{CS_PIN}h"
    #         )
    #         expected = bytes(
    #             [ord("1") if ((d >> bit) & 1) == 0 else ord("0") for bit in range(4)]
    #         )
    #
    #         CHECK(response, expected)
