from arduino_to_pins import pin40
from base_test import TestSimplController, check, extract_bits_from_byte
from simpl_macros import OUTPUT_MODE, INPUT_MODE, INPUT_PULLUP_MODE

pins = [
    "PA3",  # 1
    "PA2",  # 2
    "PA1",  # 3
    "PA0",  # 4
    "~RD",  # 5
    "~CS",  # 6
    "GND",  # 7
    "A1",  # 8
    "A0",  # 9
    "PC7",  # 10
    "PC6",  # 11
    "PC5",  # 12
    "PC4",  # 13
    "PC0",  # 14
    "PC1",  # 15
    "PC2",  # 16
    "PC3",  # 17
    "PB0",  # 18
    "PB1",  # 19
    "PB2",  # 20
    "PB3",  # 21
    "PB4",  # 22
    "PB5",  # 23
    "PB6",  # 24
    "PB7",  # 25
    "VCC",  # 26
    "D7",  # 27
    "D6",  # 28
    "D5",  # 29
    "D4",  # 30
    "D3",  # 31
    "D2",  # 32
    "D1",  # 33
    "D0",  # 34
    "RESET",  # 35
    "~WR",  # 36
    "PA7",  # 37
    "PA6",  # 38
    "PA5",  # 39
    "PA4",  # 40
]

PA0_PIN = pin40[pins.index("PA0")]
PA1_PIN = pin40[pins.index("PA1")]
PA2_PIN = pin40[pins.index("PA2")]
PA3_PIN = pin40[pins.index("PA3")]
PA4_PIN = pin40[pins.index("PA4")]
PA5_PIN = pin40[pins.index("PA5")]
PA6_PIN = pin40[pins.index("PA6")]
PA7_PIN = pin40[pins.index("PA7")]

PB0_PIN = pin40[pins.index("PB0")]
PB1_PIN = pin40[pins.index("PB1")]
PB2_PIN = pin40[pins.index("PB2")]
PB3_PIN = pin40[pins.index("PB3")]
PB4_PIN = pin40[pins.index("PB4")]
PB5_PIN = pin40[pins.index("PB5")]
PB6_PIN = pin40[pins.index("PB6")]
PB7_PIN = pin40[pins.index("PB7")]

PC0_PIN = pin40[pins.index("PC0")]
PC1_PIN = pin40[pins.index("PC1")]
PC2_PIN = pin40[pins.index("PC2")]
PC3_PIN = pin40[pins.index("PC3")]
PC4_PIN = pin40[pins.index("PC4")]
PC5_PIN = pin40[pins.index("PC5")]
PC6_PIN = pin40[pins.index("PC6")]
PC7_PIN = pin40[pins.index("PC7")]


D4_PIN = pin40[pins.index("D4")]
D5_PIN = pin40[pins.index("D5")]
D6_PIN = pin40[pins.index("D6")]
D7_PIN = pin40[pins.index("D7")]
D0_PIN = pin40[pins.index("D0")]
D1_PIN = pin40[pins.index("D1")]
D2_PIN = pin40[pins.index("D2")]
D3_PIN = pin40[pins.index("D3")]

RESET_PIN = pin40[pins.index("RESET")]
WR_PIN = pin40[pins.index("~WR")]
RD_PIN = pin40[pins.index("~RD")]
CS_PIN = pin40[pins.index("~CS")]

A0_PIN = pin40[pins.index("A0")]
A1_PIN = pin40[pins.index("A1")]

VCC_PIN = pin40[pins.index("VCC")]
GND_PIN = pin40[pins.index("GND")]

PORT_A = 0
PORT_B = 1
PORT_C = 2
CONTROL = 3

PORT_NAMES = {PORT_A: "PORT A", PORT_B: "PORT B", PORT_C: "PORT C", CONTROL: "CONTROL"}


class Test580vv55(TestSimplController):
    def __init__(self):
        super().__init__()
        self.send_command(f"{VCC_PIN}d{OUTPUT_MODE}1o" f"{GND_PIN}d{OUTPUT_MODE}0o")

        self.send_command(
            f"{A0_PIN}d{OUTPUT_MODE}1o"
            f"{A1_PIN}d{OUTPUT_MODE}0o"
            f"{RESET_PIN}d{OUTPUT_MODE}1o"
            f"{WR_PIN}d{OUTPUT_MODE}1o"
            f"{RD_PIN}d{OUTPUT_MODE}1o"
            f"{CS_PIN}d{OUTPUT_MODE}1o"
        )

        self.send_command(f"100u{RESET_PIN}d0o100u")
        self.add_ports_to_input()

    def add_ports_to_input(self):
        self.send_command(
            f"{PA0_PIN}d{INPUT_PULLUP_MODE}"
            f"{PA1_PIN}d{INPUT_PULLUP_MODE}"
            f"{PA2_PIN}d{INPUT_PULLUP_MODE}"
            f"{PA3_PIN}d{INPUT_PULLUP_MODE}"
            f"{PA4_PIN}d{INPUT_PULLUP_MODE}"
            f"{PA5_PIN}d{INPUT_PULLUP_MODE}"
            f"{PA6_PIN}d{INPUT_PULLUP_MODE}"
            f"{PA7_PIN}d{INPUT_PULLUP_MODE}"
        )

        self.send_command(
            f"{PB0_PIN}d{INPUT_PULLUP_MODE}"
            f"{PB1_PIN}d{INPUT_PULLUP_MODE}"
            f"{PB2_PIN}d{INPUT_PULLUP_MODE}"
            f"{PB3_PIN}d{INPUT_PULLUP_MODE}"
            f"{PB4_PIN}d{INPUT_PULLUP_MODE}"
            f"{PB5_PIN}d{INPUT_PULLUP_MODE}"
            f"{PB6_PIN}d{INPUT_PULLUP_MODE}"
            f"{PB7_PIN}d{INPUT_PULLUP_MODE}"
        )

        self.send_command(
            f"{PC0_PIN}d{INPUT_PULLUP_MODE}"
            f"{PC1_PIN}d{INPUT_PULLUP_MODE}"
            f"{PC2_PIN}d{INPUT_PULLUP_MODE}"
            f"{PC3_PIN}d{INPUT_PULLUP_MODE}"
            f"{PC4_PIN}d{INPUT_PULLUP_MODE}"
            f"{PC5_PIN}d{INPUT_PULLUP_MODE}"
            f"{PC6_PIN}d{INPUT_PULLUP_MODE}"
            f"{PC7_PIN}d{INPUT_PULLUP_MODE}"
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
        a0 = (addr >> 0) & 1
        a1 = (addr >> 1) & 1

        self.send_command(f"{A0_PIN}d{OUTPUT_MODE}{a0}o" f"{A1_PIN}d{OUTPUT_MODE}{a1}o")

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
        return self.send_command(
            f"{D0_PIN}d{INPUT_MODE}iq"
            f"{D1_PIN}d{INPUT_MODE}iq"
            f"{D2_PIN}d{INPUT_MODE}iq"
            f"{D3_PIN}d{INPUT_MODE}iq"
            f"{D4_PIN}d{INPUT_MODE}iq"
            f"{D5_PIN}d{INPUT_MODE}iq"
            f"{D6_PIN}d{INPUT_MODE}iq"
            f"{D7_PIN}d{INPUT_MODE}iq"
        )

    def write_port_a(self, data: int):
        d0, d1, d2, d3, d4, d5, d6, d7, *_ = extract_bits_from_byte(data)

        self.send_command(
            f"{PA0_PIN}d{OUTPUT_MODE}{d0}o"
            f"{PA1_PIN}d{OUTPUT_MODE}{d1}o"
            f"{PA2_PIN}d{OUTPUT_MODE}{d2}o"
            f"{PA3_PIN}d{OUTPUT_MODE}{d3}o"
            f"{PA4_PIN}d{OUTPUT_MODE}{d4}o"
            f"{PA5_PIN}d{OUTPUT_MODE}{d5}o"
            f"{PA6_PIN}d{OUTPUT_MODE}{d6}o"
            f"{PA7_PIN}d{OUTPUT_MODE}{d7}o"
        )

    def write_port_b(self, data: int):
        d0, d1, d2, d3, d4, d5, d6, d7, *_ = extract_bits_from_byte(data)

        self.send_command(
            f"{PB0_PIN}d{OUTPUT_MODE}{d0}o"
            f"{PB1_PIN}d{OUTPUT_MODE}{d1}o"
            f"{PB2_PIN}d{OUTPUT_MODE}{d2}o"
            f"{PB3_PIN}d{OUTPUT_MODE}{d3}o"
            f"{PB4_PIN}d{OUTPUT_MODE}{d4}o"
            f"{PB5_PIN}d{OUTPUT_MODE}{d5}o"
            f"{PB6_PIN}d{OUTPUT_MODE}{d6}o"
            f"{PB7_PIN}d{OUTPUT_MODE}{d7}o"
        )

    def write_port_c(self, data: int):
        d0, d1, d2, d3, d4, d5, d6, d7, *_ = extract_bits_from_byte(data)

        self.send_command(
            f"{PC0_PIN}d{OUTPUT_MODE}{d0}o"
            f"{PC1_PIN}d{OUTPUT_MODE}{d1}o"
            f"{PC2_PIN}d{OUTPUT_MODE}{d2}o"
            f"{PC3_PIN}d{OUTPUT_MODE}{d3}o"
            f"{PC4_PIN}d{OUTPUT_MODE}{d4}o"
            f"{PC5_PIN}d{OUTPUT_MODE}{d5}o"
            f"{PC6_PIN}d{OUTPUT_MODE}{d6}o"
            f"{PC7_PIN}d{OUTPUT_MODE}{d7}o"
        )

    def read_port_a(self):
        return self.send_command(
            f"{PA0_PIN}d{INPUT_PULLUP_MODE}iq"
            f"{PA1_PIN}d{INPUT_PULLUP_MODE}iq"
            f"{PA2_PIN}d{INPUT_PULLUP_MODE}iq"
            f"{PA3_PIN}d{INPUT_PULLUP_MODE}iq"
            f"{PA4_PIN}d{INPUT_PULLUP_MODE}iq"
            f"{PA5_PIN}d{INPUT_PULLUP_MODE}iq"
            f"{PA6_PIN}d{INPUT_PULLUP_MODE}iq"
            f"{PA7_PIN}d{INPUT_PULLUP_MODE}iq"
        )

    def read_port_b(self):
        return self.send_command(
            f"{PB0_PIN}d{INPUT_MODE}iq"
            f"{PB1_PIN}d{INPUT_MODE}iq"
            f"{PB2_PIN}d{INPUT_MODE}iq"
            f"{PB3_PIN}d{INPUT_MODE}iq"
            f"{PB4_PIN}d{INPUT_MODE}iq"
            f"{PB5_PIN}d{INPUT_MODE}iq"
            f"{PB6_PIN}d{INPUT_MODE}iq"
            f"{PB7_PIN}d{INPUT_MODE}iq"
        )

    def read_port_c(self):
        return self.send_command(
            f"{PC0_PIN}d{INPUT_MODE}iq"
            f"{PC1_PIN}d{INPUT_MODE}iq"
            f"{PC2_PIN}d{INPUT_MODE}iq"
            f"{PC3_PIN}d{INPUT_MODE}iq"
            f"{PC4_PIN}d{INPUT_MODE}iq"
            f"{PC5_PIN}d{INPUT_MODE}iq"
            f"{PC6_PIN}d{INPUT_MODE}iq"
            f"{PC7_PIN}d{INPUT_MODE}iq"
        )


if __name__ == "__main__":
    uc = Test580vv55()

    uc.send_command(f"{CS_PIN}l")
    uc.set_address(CONTROL)
    uc.write(0x80)
    uc.send_command(f"{WR_PIN}l" f"1u" f"{WR_PIN}h")
    uc.send_command(f"{CS_PIN}h")

    for port in [PORT_A, PORT_B, PORT_C]:
        print(f"Test port {PORT_NAMES[port]} write")
        for i in range(256):

            uc.send_command(f"{CS_PIN}l")
            uc.set_address(port)
            uc.write(i)
            uc.send_command(f"{WR_PIN}l" f"1u" f"{WR_PIN}h")
            uc.send_command(f"{CS_PIN}h")

            if port == PORT_A:
                result = uc.read_port_a()
            elif port == PORT_B:
                result = uc.read_port_b()
            elif port == PORT_C:
                result = uc.read_port_c()
            else:
                result = None

            expected = bytes(
                [ord("1") if ((i >> bit) & 1) == 1 else ord("0") for bit in range(8)]
            )
            check(result, expected)

    uc.send_command(f"{CS_PIN}l")
    uc.set_address(CONTROL)
    uc.write(0x9B)
    uc.send_command(f"{WR_PIN}l" f"1u" f"{WR_PIN}h")
    uc.send_command(f"{CS_PIN}h")

    for port in [PORT_A, PORT_B, PORT_C]:
        print(f"Test port {PORT_NAMES[port]} read")
        for i in range(256):
            if port == PORT_A:
                uc.write_port_a(i)
            elif port == PORT_B:
                uc.write_port_b(i)
            elif port == PORT_C:
                uc.write_port_c(i)

            uc.all_d_to_input()
            uc.send_command(f"{CS_PIN}l")

            uc.set_address(port)
            uc.send_command(f"{RD_PIN}l")

            result = uc.read()

            uc.send_command(f"{RD_PIN}h")
            uc.send_command(f"{CS_PIN}h")

            expected = bytes(
                [ord("1") if ((i >> bit) & 1) == 1 else ord("0") for bit in range(8)]
            )
            check(result, expected)

    print("All OK")
