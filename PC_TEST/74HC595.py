import os
import random
import time

from arduino_to_pins import pin16
from base_test import TestSimplController, check
from simpl_macros import OUTPUT_MODE, INPUT_PULLUP_MODE, INPUT_MODE

"""
74HC595 — 8-битный сдвиговый регистр с последовательным входом,
параллельным выходом и выходным регистром-защёлкой (DIP-16).

Распиновка:
 1 - Q1 (QB)          9 - Q7S (QH', послед. выход)
 2 - Q2 (QC)         10 - ~MR (SRCLR, сброс, актив. низкий)
 3 - Q3 (QD)         11 - SHCP (SRCLK, такт сдвига)
 4 - Q4 (QE)         12 - STCP (RCLK, такт защёлки)
 5 - Q5 (QF)         13 - ~OE  (Output Enable, актив. низкий)
 6 - Q6 (QG)         14 - DS   (SER, послед. вход данных)
 7 - Q7 (QH)         15 - Q0   (QA)
 8 - GND             16 - VCC (+5V)

Логика работы:
  * По переднему фронту SHCP бит с DS вдвигается в QA, а содержимое
    сдвигается QA->QB->...->QH (QH — последняя ступень).
  * По переднему фронту STCP содержимое сдвигового регистра
    защёлкивается в выходной регистр (Q0..Q7).
  * ~OE=0 — выходы активны, ~OE=1 — выходы в Z-состоянии.
  * ~MR=0 — сброс сдвигового регистра в 0.

Соглашение по битам: вдвигаем старшим битом вперёд (bit7 первым),
тогда после 8 тактов QA=bit0, QB=bit1, ..., QH=bit7.
"""

pins = [
    "Q1",  # 1  (QB)
    "Q2",  # 2  (QC)
    "Q3",  # 3  (QD)
    "Q4",  # 4  (QE)
    "Q5",  # 5  (QF)
    "Q6",  # 6  (QG)
    "Q7",  # 7  (QH)
    "GND",  # 8
    "Q7S",  # 9  (QH', послед. выход)
    "~MR",  # 10 (сброс, актив. низкий)
    "SHCP",  # 11 (такт сдвига)
    "STCP",  # 12 (такт защёлки)
    "~OE",  # 13 (Output Enable, актив. низкий)
    "DS",  # 14 (послед. вход)
    "Q0",  # 15 (QA)
    "VCC",  # 16
]

VCC_PIN = pin16[pins.index("VCC")]
GND_PIN = pin16[pins.index("GND")]

DS_PIN = pin16[pins.index("DS")]
SHCP_PIN = pin16[pins.index("SHCP")]
STCP_PIN = pin16[pins.index("STCP")]
OE_PIN = pin16[pins.index("~OE")]
MR_PIN = pin16[pins.index("~MR")]
Q7S_PIN = pin16[pins.index("Q7S")]

# Выходы Q0..Q7 в порядке от младшего к старшему (QA..QH)
Q_PINS = [pin16[pins.index(name)] for name in ["Q0", "Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7"]]


class Test74HC595(TestSimplController):
    def __init__(self):
        super().__init__()
        # Питание
        self.send_command(f"{VCC_PIN}d{OUTPUT_MODE}1o" f"{GND_PIN}d{OUTPUT_MODE}0o")

        # Управляющие сигналы
        self.send_command(
            f"{OE_PIN}d{OUTPUT_MODE}0o"  # выходы активны
            f"{MR_PIN}d{OUTPUT_MODE}1o"  # без сброса
            f"{SHCP_PIN}d{OUTPUT_MODE}0o"  # такт сдвига в 0
            f"{STCP_PIN}d{OUTPUT_MODE}0o"  # такт защёлки в 0
            f"{DS_PIN}d{OUTPUT_MODE}0o"  # данные в 0
        )

        # Выходы Q0..Q7 и Q7S — входы с подтяжкой (в Z-состоянии читаются как 1)
        cmd = "".join(f"{p}d{INPUT_PULLUP_MODE}" for p in Q_PINS)
        cmd += f"{Q7S_PIN}d{INPUT_PULLUP_MODE}"
        self.send_command(cmd)

    def reset(self):
        """Аппаратный сброс сдвигового регистра импульсом ~MR."""
        self.send_command(f"{MR_PIN}d0o" f"{MR_PIN}d1o")

    def shift_byte(self, value):
        """Вдвинуть байт в сдвиговый регистр (старшим битом вперёд)."""
        cmd = ""
        for bit in range(7, -1, -1):
            b = (value >> bit) & 1
            cmd += f"{DS_PIN}d{b}o" f"{SHCP_PIN}h" f"{SHCP_PIN}l"
        self.send_command(cmd)

    def latch(self):
        """Защёлкнуть содержимое сдвигового регистра в выходной регистр."""
        self.send_command(f"{STCP_PIN}h" f"{STCP_PIN}l")

    def read_outputs(self):
        """Прочитать Q0..Q7. Возвращает строку из 8 символов '0'/'1'."""
        cmd = "".join(f"{p}d{INPUT_PULLUP_MODE}iq" for p in Q_PINS)
        return self.send_command(cmd)

    def read_q7s(self):
        """Прочитать последовательный выход QH' (Q7S)."""
        return self.send_command(f"{Q7S_PIN}d{INPUT_PULLUP_MODE}iq")

    def write_byte(self, value):
        """Полный цикл: вдвинуть байт и защёлкнуть его на выходы."""
        self.shift_byte(value)
        self.latch()

    def __del__(self):
        # Безопасное состояние — все выводы на вход
        all_pins = [
            VCC_PIN, GND_PIN, DS_PIN, SHCP_PIN, STCP_PIN,
            OE_PIN, MR_PIN, Q7S_PIN, *Q_PINS,
        ]
        cmd = "".join(f"{p}d{INPUT_MODE}" for p in all_pins)
        self.send_command(cmd)
        super().__del__()


def expected_bits(value):
    """Ожидаемая строка Q0..Q7 для защёлкнутого байта."""
    return bytes([ord("1") if (value >> bit) & 1 else ord("0") for bit in range(8)])


if __name__ == "__main__":
    uc = Test74HC595()

    random.seed(int(time.time() * 1000) ^ os.getpid())

    # === Тест 1: запись и чтение параллельных выходов ===
    scenarios = [
        # Бегущая единица: от младшего разряда (Q0) к старшему (Q7)
        ("Walking 1", [1 << i for i in range(8)]),
        # Бегущий ноль: от младшего разряда к старшему
        ("Walking 0", [0xFF ^ (1 << i) for i in range(8)]),
        # Шахматный код 0xAA
        ("0xAA", [0xAA]),
        # Шахматный код 0x55
        ("0x55", [0x55]),
        # Полный перебор 0..0xFF
        ("0..0xFF", list(range(256))),
    ]

    for name, values in scenarios:
        print(f"--- {name} ---")
        for value in values:
            uc.write_byte(value)
            result = uc.read_outputs()
            expected = expected_bits(value)
            print(f"Write {value:02X}h -> Q0..Q7 = {result}")
            check(result, expected)

    # === Тест 2: сброс ~MR очищает регистр ===
    print("Check ~MR reset")
    uc.write_byte(0xFF)
    check(uc.read_outputs(), expected_bits(0xFF))
    uc.reset()
    uc.latch()  # защёлкнуть очищенный регистр
    check(uc.read_outputs(), expected_bits(0x00))

    # === Тест 3: ~OE переводит выходы в Z-состояние ===
    print("Check ~OE (Hi-Z)")
    uc.write_byte(0x00)
    check(uc.read_outputs(), expected_bits(0x00))
    # Отключаем выходы — подтяжки должны дать все единицы
    uc.send_command(f"{OE_PIN}d1o")
    check(uc.read_outputs(), expected_bits(0xFF))
    # Возвращаем выходы в активное состояние
    uc.send_command(f"{OE_PIN}d0o")
    check(uc.read_outputs(), expected_bits(0x00))

    # === Тест 4: последовательный выход QH' (Q7S) ===
    # После вдвигания байта QH' повторяет старшую ступень QH (=bit0 байта,
    # т.к. первый вдвинутый бит доходит до QH).
    print("Check Q7S serial output")
    uc.reset()
    for value in [0x01, 0x00, 0xFF, 0xAA, 0x55]:
        uc.shift_byte(value)
        q7s = uc.read_q7s()
        # первый вдвинутый бит (bit7) оказывается на QH == QH'
        expected_q7s = bytes([ord("1") if (value >> 7) & 1 else ord("0")])
        print(f"Shift {value:02X}h -> QH' = {q7s}")
        check(q7s, expected_q7s)

    print("ALL OK")
