import os
import random
import time

from tqdm import tqdm

from arduino_to_pins import pin24
from base_test import TestSimplController, check, extract_bits_from_byte
from pattern_generator import generate_memory_patterns, get_bit_from_pattern
from simpl_macros import OUTPUT_MODE, INPUT_PULLUP_MODE, INPUT_MODE

"""
К537РУ10 — статическое ОЗУ 2К x 8 бит (2048 слов по 8 бит)
Корпус DIP-24

Распиновка:
 1 - A7      9 - D0      17 - D7      24 - Vcc (+5V)
 2 - A6     10 - D1      18 - CE (Chip Enable)
 3 - A5     11 - D2      19 - A10
 4 - A4     12 - GND     20 - OE (Output Enable)
 5 - A3     13 - D3      21 - WE (Write Enable)
 6 - A2     14 - D4      22 - A9
 7 - A1     15 - D5      23 - A8
 8 - A0     16 - D6
"""

MEM_SIZE = 2048  # 2К x 8 бит

pins = [
    "A3",  # 1
    "A6",  # 2
    "A5",  # 3
    "A4",  # 4
    "A7",  # 5
    "A8",  # 6
    "A9",  # 7
    "A10",  # 8
    "D0",  # 9
    "D1",  # 10
    "D2",  # 11
    "GND",  # 12
    "D3",  # 13
    "D4",  # 14
    "D5",  # 15
    "D6",  # 16
    "D7",  # 17
    "CE",  # 18 - Chip Enable (активный низкий)
    "A0",  # 19
    "OE",  # 20 - Output Enable (активный низкий)
    "WE",  # 21 - Write Enable (активный низкий)
    "A1",  # 22
    "A2",  # 23
    "VCC",  # 24
]

VCC_PIN = pin24[pins.index("VCC")]
GND_PIN = pin24[pins.index("GND")]

A0_PIN = pin24[pins.index("A0")]
A1_PIN = pin24[pins.index("A1")]
A2_PIN = pin24[pins.index("A2")]
A3_PIN = pin24[pins.index("A3")]
A4_PIN = pin24[pins.index("A4")]
A5_PIN = pin24[pins.index("A5")]
A6_PIN = pin24[pins.index("A6")]
A7_PIN = pin24[pins.index("A7")]
A8_PIN = pin24[pins.index("A8")]
A9_PIN = pin24[pins.index("A9")]
A10_PIN = pin24[pins.index("A10")]

D0_PIN = pin24[pins.index("D0")]
D1_PIN = pin24[pins.index("D1")]
D2_PIN = pin24[pins.index("D2")]
D3_PIN = pin24[pins.index("D3")]
D4_PIN = pin24[pins.index("D4")]
D5_PIN = pin24[pins.index("D5")]
D6_PIN = pin24[pins.index("D6")]
D7_PIN = pin24[pins.index("D7")]

CE_PIN = pin24[pins.index("CE")]
OE_PIN = pin24[pins.index("OE")]
WE_PIN = pin24[pins.index("WE")]


class TestK537RU10(TestSimplController):
    def __init__(self):
        super().__init__()
        # Питание
        self.send_command(f"{VCC_PIN}d{OUTPUT_MODE}1o" f"{GND_PIN}d{OUTPUT_MODE}0o")

        # Управляющие сигналы — все неактивны (высокий уровень)
        self.send_command(
            f"{CE_PIN}d{OUTPUT_MODE}1o"
            f"{OE_PIN}d{OUTPUT_MODE}1o"
            f"{WE_PIN}d{OUTPUT_MODE}1o"
        )

        # Адресные линии — выходы, начальное значение 0
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

        # Линии данных — входы (режим чтения по умолчанию)
        self.all_d_to_input()

    def all_d_to_input(self):
        """Переключить D0-D7 в режим входа (чтение из микросхемы)"""
        self.send_command(
            f"{D0_PIN}d{INPUT_PULLUP_MODE}"
            f"{D1_PIN}d{INPUT_PULLUP_MODE}"
            f"{D2_PIN}d{INPUT_PULLUP_MODE}"
            f"{D3_PIN}d{INPUT_PULLUP_MODE}"
            f"{D4_PIN}d{INPUT_PULLUP_MODE}"
            f"{D5_PIN}d{INPUT_PULLUP_MODE}"
            f"{D6_PIN}d{INPUT_PULLUP_MODE}"
            f"{D7_PIN}d{INPUT_PULLUP_MODE}"
        )

    def all_d_to_output(self):
        """Переключить D0-D7 в режим выхода (запись в микросхему)"""
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

    def set_address(self, addr):
        """Установить 11-битный адрес на A0-A10 (2К = 2048 адресов)"""
        a0, a1, a2, a3, a4, a5, a6, a7, a8, a9, a10, *_ = extract_bits_from_byte(addr)

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
            f"{A10_PIN}d{a10}o"
        )

    def set_data(self, data):
        """Установить байт данных на D0-D7 (перед записью)"""
        d0, d1, d2, d3, d4, d5, d6, d7, *_ = extract_bits_from_byte(data)

        self.send_command(
            f"{D0_PIN}d{d0}o"
            f"{D1_PIN}d{d1}o"
            f"{D2_PIN}d{d2}o"
            f"{D3_PIN}d{d3}o"
            f"{D4_PIN}d{d4}o"
            f"{D5_PIN}d{d5}o"
            f"{D6_PIN}d{d6}o"
            f"{D7_PIN}d{d7}o"
        )

    def read_data(self):
        """Прочитать байт данных с D0-D7 (после установки адреса и CE+OE)"""
        return self.send_command(
            f"{D0_PIN}d{INPUT_PULLUP_MODE}iq"
            f"{D1_PIN}d{INPUT_PULLUP_MODE}iq"
            f"{D2_PIN}d{INPUT_PULLUP_MODE}iq"
            f"{D3_PIN}d{INPUT_PULLUP_MODE}iq"
            f"{D4_PIN}d{INPUT_PULLUP_MODE}iq"
            f"{D5_PIN}d{INPUT_PULLUP_MODE}iq"
            f"{D6_PIN}d{INPUT_PULLUP_MODE}iq"
            f"{D7_PIN}d{INPUT_PULLUP_MODE}iq"
        )

    def __del__(self):
        self.send_command(
            f"{CE_PIN}d{INPUT_MODE}"
            f"{OE_PIN}d{INPUT_MODE}"
            f"{WE_PIN}d{INPUT_MODE}"
            f"{A0_PIN}d{INPUT_MODE}"
            f"{A1_PIN}d{INPUT_MODE}"
            f"{A2_PIN}d{INPUT_MODE}"
            f"{A3_PIN}d{INPUT_MODE}"
            f"{A4_PIN}d{INPUT_MODE}"
            f"{A5_PIN}d{INPUT_MODE}"
            f"{A6_PIN}d{INPUT_MODE}"
            f"{A7_PIN}d{INPUT_MODE}"
            f"{A8_PIN}d{INPUT_MODE}"
            f"{A9_PIN}d{INPUT_MODE}"
            f"{A10_PIN}d{INPUT_MODE}"
        )
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
        self.send_command(f"{VCC_PIN}d{INPUT_MODE}" f"{GND_PIN}d{INPUT_MODE}")


if __name__ == "__main__":
    uc = TestK537RU10()

    random.seed(int(time.time() * 1000) ^ os.getpid())

    # Тестовые паттерны — каждый по 2048 байт (весь объём 2К x 8)
    for pattern in [
        [random.randint(0, 0xFF) for _ in range(MEM_SIZE)],
        [0x00 for _ in range(MEM_SIZE)],
        [0xFF for _ in range(MEM_SIZE)],
        [0xAA for _ in range(MEM_SIZE)],
        [0x55 for _ in range(MEM_SIZE)],
        [0xCC for _ in range(MEM_SIZE)],
        [0x33 for _ in range(MEM_SIZE)],
        [0xF0 for _ in range(MEM_SIZE)],
        [0x0F for _ in range(MEM_SIZE)],
        [i % 256 for i in range(MEM_SIZE)],
        [(255 - i) % 256 for i in range(MEM_SIZE)],
        [0x01 for _ in range(MEM_SIZE)],
        [0x02 for _ in range(MEM_SIZE)],
        [0x04 for _ in range(MEM_SIZE)],
        [0x08 for _ in range(MEM_SIZE)],
        [0x10 for _ in range(MEM_SIZE)],
        [0x20 for _ in range(MEM_SIZE)],
        [0x40 for _ in range(MEM_SIZE)],
        [0x80 for _ in range(MEM_SIZE)],
    ]:
        # === ЗАПИСЬ ===
        for i in tqdm(
            range(MEM_SIZE),
            desc=f"Write pattern {pattern[0]:02X}h...",
            unit="addr",
        ):
            uc.set_address(i)
            uc.all_d_to_output()
            uc.set_data(pattern[i])

            # Цикл записи: CE=0, WE=0 (активные низкие)
            uc.send_command(
                f"{CE_PIN}d0o"
                f"{WE_PIN}d0o"
                f"10n"  # импульс записи ~10 мкс
                f"{WE_PIN}d1o"
                f"{CE_PIN}d1o"
            )

        # === ЧТЕНИЕ ===
        for i in tqdm(
            range(MEM_SIZE),
            desc=f"Read  pattern {pattern[0]:02X}h...",
            unit="addr",
        ):
            uc.set_address(i)
            uc.all_d_to_input()

            # Цикл чтения: CE=0, OE=0 (активные низкие)
            result = uc.send_command(
                f"{CE_PIN}d0o"
                f"{OE_PIN}d0o"
                f"100u"
                f"{D0_PIN}diq"
                f"{D1_PIN}diq"
                f"{D2_PIN}diq"
                f"{D3_PIN}diq"
                f"{D4_PIN}diq"
                f"{D5_PIN}diq"
                f"{D6_PIN}diq"
                f"{D7_PIN}diq"
                f"{CE_PIN}d1o"
                f"{OE_PIN}d1o"
            )

            # Формируем ожидаемый байт
            expected = bytes(
                [ord("1") if (pattern[i] >> bit) & 1 else ord("0") for bit in range(8)]
            )

            check(result, expected)

    print("ALL OK")
