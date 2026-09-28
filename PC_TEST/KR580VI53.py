#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR580VI53.py — функциональный тестер программируемого таймера КР580ВИ53 (DIP-24)
на базе Mega-IC-Tester (режим PC, язык SIMPL).

Идея
====
Тестер не имеет собственной памяти и тактирования: хост-ПК **и есть шина**.
Выводы ZIF-40 дёргаются по одному через Arduino, поэтому ПК выступает в роли
генератора тактовых импульсов, источника данных и измерителя:

  * CLK0..CLK2 — генерируются вручную; один «такт» = импульс
    высокий->низкий, счётчик КР580ВИ53 считает по спаду такта;
  * D0..D7     — выдаются в микросхему при записи и читаются при чтении;
  * A0, A1     — выбирают счётчик 0..2 либо регистр управляющего слова;
  * ~CS, ~RD, ~WR — стробируют обмен;
  * OUT0..OUT2 — читаются после каждого такта, что даёт осциллограмму выхода
    прямо в Python без осциллографа.

Тактовая частота получается порядка 30 кГц (полный период ~33 мкс), что на
три порядка ниже предельных 2 МГц, поэтому микросхема работает как полностью
статическое устройство и успевает отработать каждый такт.

Распиновка (корпус 2120.24-3, DIP-24)
=====================================
  1..8   D7 D6 D5 D4 D3 D2 D1 D0   — двунаправленная шина данных
  9      C0   (CLK0)               — тактовый вход счётчика 0
  10     OUT0                      — выход счётчика 0
  11     CE0  (GATE0)              — разрешение счёта счётчика 0
  12     GND                       — общий
  13     OUT1                      — выход счётчика 1
  14     CE1  (GATE1)              — разрешение счёта счётчика 1
  15     C1   (CLK1)               — тактовый вход счётчика 1
  16     CE2  (GATE2)              — разрешение счёта счётчика 2
  17     OUT2                      — выход счётчика 2
  18     C2   (CLK2)               — тактовый вход счётчика 2
  19     A0                      20  A1
  21     ~CS                     22  ~RD                    23  ~WR
  24     Ucc (+5 В)

ВНИМАНИЕ, отличие от Intel i8253!
--------------------------------
У i8253 выводы 13/14/15 = CLK1/OUT1/GATE1. У КР580ВИ53 по официальному
документу (см. refs/k580vi53_eandc) 13 = OUT1, 14 = CE1, 15 = C1, то есть
тройка выводов 13-15 «провёрнута». Выводы счётчиков 0 и 2 у обеих микросхем
совпадают. Тесты счётчика 1 поэтому параметризованы вариантом
(--variant vi53|i8253), а ключ --detect определяет раскладку по самой
микросхеме.

Посадка в ZIF-40
================
Микросхема DIP-24 ставится в верхнюю часть ZIF-40: вывод 1 — в позицию 1 ZIF.
Правая сторона корпуса ложится в позиции 29..40, поэтому вывод 13 оказывается
в позиции 29, а вывод 24 (Ucc) — в позиции 40. Именно этот порядок задаёт
таблица arduino_to_pins.pin24 (её последние 12 значений — позиции 29..40).

Проверяемые свойства
====================
  * шина данных переходит в третье состояние при ~CS=1 и при ~RD=1;
  * запись управляющего слова и константы счёта;
  * режим 0 (прерывание по конечному счёту): OUT=0 после УС, OUT=1 после N тактов;
  * режим 2 (делитель частоты): один нулевой импульс длиной в такт за период;
  * режим 3 (генератор меандра): период N, половина периода высокий уровень;
  * режим 4 (программируемый строб): один нулевой такт по достижении нуля;
  * «чтение на лету» (latch): счётчик читается, не прерывая счёт, и
    убывает ровно на 1 за такт;
  * вход CE0: при CE0=0 счёт приостанавливается, при CE0=1 продолжается.

Использование
=============
    python KR580VI53.py                    # весь набор тестов
    python KR580VI53.py --port COM11
    python KR580VI53.py --monitor          # только состояние шины/присутствие ИС
    python KR580VI53.py --detect           # определить раскладку выводов 13-15
    python KR580VI53.py --variant i8253    # если в корпусе клон i8253
    python KR580VI53.py --test mode0 --test mode3

Проектные файлы (base_test / arduino_to_pins / simpl_macros) не изменяются.
"""

import argparse
import sys

import base_test
from arduino_to_pins import pin24, pin40
from base_test import TestSimplController
from simpl_macros import INPUT_MODE, INPUT_PULLUP_MODE, OUTPUT_MODE

DEFAULT_PORT = "COM11"

# ---------------------------------------------------------------------------
# Распиновка: индекс элемента = номер вывода микросхемы (1..24).
# ---------------------------------------------------------------------------
VI53_PINS = [
    "D7", "D6", "D5", "D4", "D3", "D2", "D1", "D0",   # 1..8
    "C0", "OUT0", "CE0", "GND",                        # 9..12
    "OUT1", "CE1", "C1", "CE2", "OUT2", "C2",          # 13..18
    "A0", "A1", "~CS", "~RD", "~WR", "VCC",            # 19..24
]

# Контрольная таблица — защита от опечатки в списке выше.
_PIN_CHECK = {
    1: "D7", 2: "D6", 3: "D5", 4: "D4", 5: "D3", 6: "D2", 7: "D1", 8: "D0",
    9: "C0", 10: "OUT0", 11: "CE0", 12: "GND",
    13: "OUT1", 14: "CE1", 15: "C1", 16: "CE2", 17: "OUT2", 18: "C2",
    19: "A0", 20: "A1", 21: "~CS", 22: "~RD", 23: "~WR", 24: "VCC",
}

if len(VI53_PINS) != 24:
    raise RuntimeError("VI53_PINS must contain 24 pins")
if len(set(VI53_PINS)) != 24:
    raise RuntimeError("VI53_PINS contains duplicates")
for _pin, _name in _PIN_CHECK.items():
    if VI53_PINS[_pin - 1] != _name:
        raise RuntimeError(
            f"pinout: pin {_pin} = {VI53_PINS[_pin - 1]!r}, expected {_name!r}"
        )

# Имя вывода -> номер вывода Arduino (позиция ZIF-40 через pin24).
P = {name: pin24[i] for i, name in enumerate(VI53_PINS)}

D_PINS = [P[f"D{i}"] for i in range(8)]          # D_PINS[0] = D0
A0_PIN, A1_PIN = P["A0"], P["A1"]
CS_PIN, RD_PIN, WR_PIN = P["~CS"], P["~RD"], P["~WR"]
VCC_PIN, GND_PIN = P["VCC"], P["GND"]

# Счётчик -> (такт, выход, разрешение) в номерах выводов микросхемы.
# Для счётчиков 0 и 2 раскладка у КР580ВИ53 и i8253 совпадает.
COUNTER_PINS = {
    0: {"clk": 9, "out": 10, "gate": 11},
    2: {"clk": 18, "out": 17, "gate": 16},
}

# Счётчик 1 — две несовместимые раскладки выводов 13/14/15.
CH1_VARIANTS = {
    "vi53": {"clk": 15, "out": 13, "gate": 14},    # КР580ВИ53 (официальный документ)
    "i8253": {"clk": 13, "out": 14, "gate": 15},   # клон/аналог Intel i8253
}

# Адреса регистров (A1 A0).
ADDR_COUNTER = {0: 0b00, 1: 0b01, 2: 0b10}
ADDR_CONTROL = 0b11

# Режимы.
MODE0, MODE1, MODE2, MODE3, MODE4, MODE5 = 0, 1, 2, 3, 4, 5

# Ограничение протокола SIMPL: txtRead(buf, 255) -> максимум 254 символа.
CMD_LIMIT = 240

COUNTER_NAMES = {0: "счётчик 0", 1: "счётчик 1", 2: "счётчик 2"}


class CheckFailed(AssertionError):
    """Ошибка проверки: тест помечается как проваленный, прогон продолжается."""


# ---------------------------------------------------------------------------
# Тестер
# ---------------------------------------------------------------------------
class TestKR580VI53(TestSimplController):
    def __init__(self, port=DEFAULT_PORT, variant="vi53"):
        base_test.COM_PORT = port
        self.variant = variant
        super().__init__()

        if not self.ping():
            raise RuntimeError(
                f"нет связи с тестером на {port}: SIMPL не ответил на 7p"
            )
        # Длинные тактовые пакеты (65536 тактов ≈ 0.7 с) должны успеть ответить.
        self._ser.timeout = 3.0

        # Раскладка выводов счётчиков с учётом варианта корпуса.
        self.counter_pins = {c: dict(COUNTER_PINS[c]) for c in COUNTER_PINS}
        self.counter_pins[1] = dict(CH1_VARIANTS[variant])

        # Питание. Если на ZIF-40 уже поданы внешние +5 В и GND, выводы всё
        # равно остаются выходами — это безопасно, уровни совпадают.
        self.cmd(f"{GND_PIN}d{OUTPUT_MODE}0o{VCC_PIN}d{OUTPUT_MODE}1o")

        # Управляющие входы в исходное состояние: микросхема не выбрана,
        # чтение и запись запрещены, CE0..CE2 = 1 (счёт разрешён).
        self.cmd(
            f"{A0_PIN}d{OUTPUT_MODE}0o"
            f"{A1_PIN}d{OUTPUT_MODE}0o"
            f"{CS_PIN}d{OUTPUT_MODE}1o"
            f"{RD_PIN}d{OUTPUT_MODE}1o"
            f"{WR_PIN}d{OUTPUT_MODE}1o"
        )
        for c in (0, 1, 2):
            self.gate(c, 1)
            self.clk_level(c, 0)

        # Шина данных — на вход с подтяжкой (третье состояние).
        self.release_bus()

    # -- низкий уровень ----------------------------------------------------
    def send_command(self, cmd: str):
        """Своя версия обмена вместо base_test.send_command.

        Прошивка печатает CR-LF в конце ответов `p`/`b`/`c`, а SIMPL_run
        добавляет ещё один '\\n' после каждой команды. read_until(b'\\n')
        останавливается на первом переводе строки, и «хвост» остаётся во
        входном буфере: ответы начинают отставать на одну команду.
        Поэтому перед отправкой входной буфер очищается — тогда ответ всегда
        принадлежит отправленной команде.
        """
        if not cmd.endswith("\n"):
            cmd += "\n"
        self._ser.reset_input_buffer()
        self._ser.write(cmd.encode("ascii"))
        self._ser.flush()
        income = self._ser.read_until(b"\n")
        return income.strip(b"\r\n").strip(b"\r\n") or None

    def cmd(self, command):
        """Отправить команду SIMPL (с контролем длины) и вернуть ответ.

        SIMPL отвечает переводом строки на каждую команду, поэтому «тихие»
        команды (установка выводов, тактовые пакеты) возвращают b"".
        """
        if len(command) > CMD_LIMIT:
            raise RuntimeError(f"команда длиннее {CMD_LIMIT} символов: {len(command)}")
        response = self.send_command(command)
        return response if response is not None else b""

    def ping(self):
        """Проверить, что микроконтроллер отвечает (7p печатает 7)."""
        return b"7" in self.cmd("7p")

    def pin(self, name):
        return P[name]

    # -- питание -----------------------------------------------------------
    def power_off(self):
        """Снять питание с микросхемы (выводы в высокоимпедансное состояние)."""
        self.release_bus()
        self.cmd(
            f"{VCC_PIN}d{INPUT_MODE}"
            f"{GND_PIN}d{INPUT_MODE}"
            f"{A0_PIN}d{INPUT_MODE}"
            f"{A1_PIN}d{INPUT_MODE}"
            f"{CS_PIN}d{INPUT_MODE}"
            f"{RD_PIN}d{INPUT_MODE}"
            f"{WR_PIN}d{INPUT_MODE}"
        )
        for c in (0, 1, 2):
            for key in ("clk", "out", "gate"):
                self.cmd(f"{P[VI53_PINS[self.counter_pins[c][key] - 1]]}d{INPUT_MODE}")

    # -- шина данных -------------------------------------------------------
    def release_bus(self):
        self.cmd("".join(f"{p}d{INPUT_PULLUP_MODE}" for p in D_PINS))

    def drive_byte(self, value):
        self.cmd(
            "".join(
                f"{D_PINS[i]}d{OUTPUT_MODE}{(value >> i) & 1}o" for i in range(8)
            )
        )

    def read_byte(self):
        """Прочитать D0..D7 (при отпущенной шине подтяжки дают 0xFF)."""
        response = self.cmd(
            "".join(f"{p}d{INPUT_PULLUP_MODE}iq" for p in D_PINS)
        )
        text = response.decode("ascii", "replace")
        if len(text) < 8:
            raise RuntimeError(f"короткий ответ при чтении шины: {text!r}")
        value = 0
        for i, ch in enumerate(text[:8]):
            if ch == "1":
                value |= 1 << i
        return value

    # -- адрес и обмен -----------------------------------------------------
    def set_address(self, address):
        self.cmd(
            f"{A0_PIN}d{OUTPUT_MODE}{address & 1}o"
            f"{A1_PIN}d{OUTPUT_MODE}{(address >> 1) & 1}o"
        )

    def write_register(self, address, value):
        """Полный цикл записи: адрес + данные + ~CS/~WR."""
        self.set_address(address)
        self.drive_byte(value)
        self.cmd(f"{CS_PIN}d0o")
        self.cmd(f"{WR_PIN}d0o10u{WR_PIN}d1o")
        self.cmd(f"{CS_PIN}d1o")

    def read_register(self, address):
        """Полный цикл чтения: адрес + ~CS/~RD, после — отпустить шину."""
        self.set_address(address)
        self.cmd(f"{CS_PIN}d0o")
        self.cmd(f"{RD_PIN}d0o")
        value = self.read_byte()
        self.cmd(f"{RD_PIN}d1o")
        self.cmd(f"{CS_PIN}d1o")
        self.release_bus()
        return value

    # -- счётчики ----------------------------------------------------------
    def pin_of(self, counter, key):
        return P[VI53_PINS[self.counter_pins[counter][key] - 1]]

    def gate(self, counter, level):
        self.cmd(f"{self.pin_of(counter, 'gate')}d{OUTPUT_MODE}{1 if level else 0}o")

    def clk_level(self, counter, level):
        self.cmd(f"{self.pin_of(counter, 'clk')}d{OUTPUT_MODE}{1 if level else 0}o")

    def release_out(self, counter):
        self.cmd(f"{self.pin_of(counter, 'out')}d{INPUT_PULLUP_MODE}")

    def read_out(self, counter):
        response = self.cmd(f"{self.pin_of(counter, 'out')}d{INPUT_PULLUP_MODE}iq")
        if not response[:1]:
            raise RuntimeError("нет ответа при чтении выхода")
        return 1 if response[:1] == b"1" else 0

    def clock(self, counter, count=1):
        """Подать `count` тактовых импульсов одним пакетом."""
        if count <= 0:
            return
        pin = self.pin_of(counter, "clk")
        self.cmd(f"{pin}d{OUTPUT_MODE}0o")
        self.cmd(f"{count}{{{pin}h{pin}l}}")

    def clock_and_read(self, counter, count=1):
        """`count` тактов, после каждого — чтение выхода. Возвращает строку 0/1."""
        pin = self.pin_of(counter, "clk")
        out = self.pin_of(counter, "out")
        self.cmd(f"{pin}d{OUTPUT_MODE}0o")
        body = f"{pin}h{pin}l{out}d{INPUT_PULLUP_MODE}iq"
        response = self.cmd(f"{count}{{{body}}}")
        samples = response.decode("ascii", "replace")
        if len(samples) < count:
            raise RuntimeError(
                f"получено {len(samples)} выборок вместо {count}: {samples!r}"
            )
        return samples[:count]

    def capture(self, counter, samples):
        """Осциллограмма выхода: по одному такту между выборками."""
        return self.clock_and_read(counter, samples)

    # -- программирование --------------------------------------------------
    @staticmethod
    def control_word(counter, mode, rw=3, bcd=False):
        return ((counter & 3) << 6) | ((rw & 3) << 4) | ((mode & 7) << 1) | (1 if bcd else 0)

    def load_count(self, counter, count, rw=3):
        value = count & 0xFFFF
        if rw & 1:
            self.write_register(ADDR_COUNTER[counter], value & 0xFF)
        if rw & 2:
            self.write_register(ADDR_COUNTER[counter], (value >> 8) & 0xFF)

    def program(self, counter, mode, count, rw=3, bcd=False):
        """Управляющее слово + константа счёта."""
        self.write_register(ADDR_CONTROL, self.control_word(counter, mode, rw, bcd))
        self.load_count(counter, count, rw)

    def latch_and_read(self, counter, rw=3):
        """«Чтение на лету»: защёлкнуть текущий счёт и прочитать его."""
        self.write_register(ADDR_CONTROL, self.control_word(counter, 0, rw=0))
        low = 0
        high = 0
        if rw & 1:
            low = self.read_register(ADDR_COUNTER[counter])
        if rw & 2:
            high = self.read_register(ADDR_COUNTER[counter])
        return (high << 8) | low

    # -- присутствие микросхемы -------------------------------------------
    def chip_present(self):
        """Грубая проверка: управляет ли хоть что-то шиной данных.

        Признак исправной микросхемы — шина заметно меняет состояние между
        ~CS/~RD активными и неактивными, а читаемые значения воспроизводимы.
        """
        report = {"deselected": None, "selected": [], "stable": False}
        self.set_address(ADDR_COUNTER[0])
        self.cmd(f"{RD_PIN}d1o{CS_PIN}d1o")
        report["deselected"] = self.read_byte()
        for _ in range(4):
            report["selected"].append(self.read_register(ADDR_COUNTER[0]))
        report["stable"] = len(set(report["selected"])) == 1
        return report


# ---------------------------------------------------------------------------
# Инфраструктура тестов
# ---------------------------------------------------------------------------
class Runner:
    def __init__(self):
        self.results = []

    def run(self, name, function, *args):
        print(f"\n=== {name} ===")
        try:
            function(*args)
        except CheckFailed as error:
            self.results.append((name, False, str(error)))
            print(f"  ПРОВАЛ: {error}")
        except Exception as error:  # noqa: BLE001 — тестер обязан продолжать
            self.results.append((name, False, f"{type(error).__name__}: {error}"))
            print(f"  ОШИБКА: {type(error).__name__}: {error}")
        else:
            self.results.append((name, True, ""))
            print("  OK")

    def summary(self):
        passed = sum(1 for _, ok, _ in self.results if ok)
        total = len(self.results)
        print("\n" + "=" * 60)
        for name, ok, message in self.results:
            mark = "PASS" if ok else "FAIL"
            line = f"{mark}  {name}"
            if message:
                line += f"   ({message})"
            print(line)
        print("=" * 60)
        print(f"Итог: {passed}/{total} тестов пройдено")
        return passed == total


def check(condition, message):
    if not condition:
        raise CheckFailed(message)


# ---------------------------------------------------------------------------
# Тесты
# ---------------------------------------------------------------------------
def test_power(tester):
    """Косвенная проверка питания микросхемы.

    У обесточенной КМОП-микросхемы выводы связаны с шиной питания защитными
    диодами: подтяжки тестера постепенно заряжают эту шину, поэтому сразу после
    подачи подтяжек часть выводов читается как 0, а через секунду — как 1.
    У нормально питаемой микросхемы картина стабильна с первого чтения.
    """
    watched = list(D_PINS) + [tester.pin_of(c, "out") for c in (0, 1, 2)]
    set_pullups = "".join(f"{p}d{INPUT_PULLUP_MODE}" for p in watched)
    read_all = "".join(f"{p}d{INPUT_PULLUP_MODE}iq" for p in watched)

    tester.cmd(set_pullups)
    first = tester.cmd(read_all).decode()
    tester.cmd("1500m")
    tester.cmd(set_pullups)
    second = tester.cmd(read_all).decode()
    print(f"  сразу после подтяжек: {first}")
    print(f"  через 1.5 с:          {second}")

    check(
        first == second,
        "уровни на выводах «всплывают» со временем — похоже, микросхема не "
        "питается: проверьте +5 В на выводе 24 (позиция ZIF-40) и общий на "
        "выводе 12 (позиция ZIF-12), а также контакт выводов в панели",
    )


def _report_low_bits(value):
    """Какие разряды шины прижаты к нулю (полезно знать заранее)."""
    names = [f"D{i}" for i in range(8) if not (value >> i) & 1]
    return ", ".join(names) if names else "нет"


def test_chip_present(tester):
    report = tester.chip_present()
    print(f"  шина отпущена (~CS=1/~RD=1): 0x{report['deselected']:02X}"
          f"  (прижаты к нулю: {_report_low_bits(report['deselected'])})")
    print("  шина при чтении счётчика 0: "
          + " ".join(f"0x{v:02X}" for v in report["selected"]))
    check(report["stable"], "значения шины при чтении не воспроизводимы")
    check(
        report["selected"][0] != report["deselected"],
        "микросхема не управляет шиной данных: при ~CS=0 и ~RD=0 уровни такие же, "
        "как при отпущенной шине (нет питания, нет контакта или ИС неисправна)",
    )


def test_bus_float(tester):
    """Третье состояние шины при ~CS=1 и при ~RD=1.

    Когда шина отпущена, её уровни задаются только внешними нагрузками
    тестера, поэтому все три «отпущенных» сочетания обязаны совпасть.
    """
    readings = {}
    for cs, rd in ((1, 1), (0, 1), (1, 0), (0, 0)):
        tester.cmd(f"{CS_PIN}d{OUTPUT_MODE}{cs}o{RD_PIN}d{OUTPUT_MODE}{rd}o")
        values = [tester.read_byte() for _ in range(3)]
        readings[(cs, rd)] = tuple(values)
        print(f"  ~CS={cs} ~RD={rd}: "
              + " ".join(f"0x{v:02X}" for v in values)
              + f"   прижаты к нулю: {_report_low_bits(values[0])}")
    tester.cmd(f"{RD_PIN}d{OUTPUT_MODE}1o{CS_PIN}d{OUTPUT_MODE}1o")

    released = {readings[key] for key in ((1, 1), (0, 1), (1, 0))}
    check(
        len(released) == 1,
        "при отпущенной шине уровни должны совпадать для ~CS=1 и ~RD=1, "
        f"получено {[list(v) for v in released]}",
    )
    check(
        readings[(0, 0)] != readings[(1, 1)],
        "шина не реагирует на выбор микросхемы: при ~CS=0 и ~RD=0 микросхема "
        "обязана выставить данные",
    )


def test_mode0(tester, counter):
    """Режим 0: OUT=0 после УС, OUT=1 по достижении нуля."""
    count = 16
    tester.gate(counter, 1)
    tester.clk_level(counter, 0)
    tester.release_out(counter)
    tester.program(counter, MODE0, count)

    out = tester.read_out(counter)
    check(out == 0, f"режим 0: сразу после УС OUT должен быть 0, прочитано {out}")

    tester.clock(counter, count - 3)
    out = tester.read_out(counter)
    check(out == 0, f"режим 0: после {count - 3} тактов OUT ещё 0, прочитано {out}")

    tester.clock(counter, 5)
    out = tester.read_out(counter)
    check(out == 1, f"режим 0: после {count + 2} тактов OUT должен быть 1, прочитано {out}")


def test_mode0_edges(tester, counter):
    """Точное место фронта в режиме 0 измеряется по одному такту."""
    count = 12
    tester.gate(counter, 1)
    tester.clk_level(counter, 0)
    tester.release_out(counter)
    tester.program(counter, MODE0, count)
    samples = tester.capture(counter, count + 6)
    print(f"  осциллограмма: {samples}")
    check("1" in samples, "режим 0: выход так и не поднялся")
    first_high = samples.index("1")
    check(
        count - 3 <= first_high <= count + 3,
        f"режим 0: фронт на {first_high}-м такте, ожидалось около {count}",
    )


def test_mode2(tester, counter):
    """Режим 2: период равен константе, один нулевой такт за период."""
    count = 8
    tester.gate(counter, 1)
    tester.clk_level(counter, 0)
    tester.release_out(counter)
    tester.program(counter, MODE2, count)

    samples = tester.capture(counter, count * 3)
    print(f"  осциллограмма: {samples}")
    body = samples[2:]                       # первые такты — загрузка счётчика
    per_period = body.count("0")
    check(per_period >= 1, "режим 2: не найдено ни одного нулевого импульса")
    check(
        body.count("0") * 4 <= len(body),
        f"режим 2: слишком много нулей ({body.count('0')} из {len(body)})",
    )


def test_mode3(tester, counter):
    """Режим 3: меандр, период равен константе."""
    count = 16
    tester.gate(counter, 1)
    tester.clk_level(counter, 0)
    tester.release_out(counter)
    tester.program(counter, MODE3, count)

    samples = tester.capture(counter, count * 2)
    print(f"  осциллограмма: {samples}")
    body = samples[2:]
    high = body.count("1")
    low = body.count("0")
    check(high > 0 and low > 0, "режим 3: выход не переключается")
    check(
        abs(high - low) <= 4,
        f"режим 3: скважность не 2 (высокий {high}, низкий {low})",
    )


def test_mode4(tester, counter):
    """Режим 4: программно запускаемый строб, один нулевой такт."""
    count = 10
    tester.gate(counter, 1)
    tester.clk_level(counter, 0)
    tester.release_out(counter)
    tester.program(counter, MODE4, count)

    samples = tester.capture(counter, count + 6)
    print(f"  осциллограмма: {samples}")
    check(samples[0:1] == "1", "режим 4: после УС выход должен быть 1")
    check("0" in samples, "режим 4: стробирующий импульс не сформирован")
    check(
        samples.count("0") <= 2,
        f"режим 4: строб длиннее одного такта ({samples.count('0')})",
    )


def test_latch(tester, counter):
    """«Чтение на лету»: счёт читается и убывает ровно на 1 за такт."""
    count = 40
    tester.gate(counter, 1)
    tester.clk_level(counter, 0)
    tester.release_out(counter)
    tester.program(counter, MODE2, count)      # режим 2 не меняет OUT при чтении

    tester.clock(counter, 10)
    readings = [tester.latch_and_read(counter) for _ in range(5)]
    while_clocking = []
    for _ in range(4):
        tester.clock(counter, 1)
        while_clocking.append(tester.latch_and_read(counter))

    print(f"  прочитано подряд:      {readings}")
    print(f"  после каждого такта:   {while_clocking}")
    check(
        len(set(readings)) == 1,
        "чтение на лету: без тактов значение должно быть неизменным",
    )
    steps = [a - b for a, b in zip(while_clocking, while_clocking[1:])]
    check(
        all(step == 1 for step in steps),
        f"счётчик должен убывать на 1 за такт, получено {steps}",
    )


def test_gate(tester, counter):
    """CE=0 приостанавливает счёт в режиме 0."""
    count = 20
    tester.gate(counter, 1)
    tester.clk_level(counter, 0)
    tester.release_out(counter)
    tester.program(counter, MODE0, count)

    tester.clock(counter, 5)
    tester.gate(counter, 0)
    tester.clock(counter, 30)
    out = tester.read_out(counter)
    check(out == 0, "режим 0: при CE=0 счёт должен быть приостановлен")

    tester.gate(counter, 1)
    tester.clock(counter, count)
    out = tester.read_out(counter)
    check(out == 1, "режим 0: после CE=1 счёт должен продолжиться")


def test_mode1(tester, counter):
    """Режим 1: ждущий мультивибратор, запуск по фронту CE."""
    count = 10
    tester.gate(counter, 0)
    tester.clk_level(counter, 0)
    tester.release_out(counter)
    tester.program(counter, MODE1, count)
    tester.clock(counter, 2)

    out = tester.read_out(counter)
    check(out == 1, f"режим 1: до запуска OUT должен быть 1, прочитано {out}")

    tester.gate(counter, 1)                    # фронт CE запускает одновибратор
    tester.clock(counter, 2)
    out = tester.read_out(counter)
    check(out == 0, "режим 1: после запуска OUT должен опуститься в 0")

    tester.clock(counter, count + 2)
    out = tester.read_out(counter)
    check(out == 1, "режим 1: после конца импульса OUT должен вернуться в 1")


def test_detect_variant(tester):
    """Определить раскладку выводов 13/14/15 по самой микросхеме."""
    print("  проверяются два варианта: КР580ВИ53 (13=OUT1,14=CE1,15=C1) "
          "и i8253 (13=CLK1,14=OUT1,15=GATE1)")
    found = []
    for name, pins in CH1_VARIANTS.items():
        candidate = dict(pins)
        pin_clk = P[VI53_PINS[candidate["clk"] - 1]]
        pin_out = P[VI53_PINS[candidate["out"] - 1]]
        pin_gate = P[VI53_PINS[candidate["gate"] - 1]]

        # Все три вывода сначала отпускаем: иначе выход микросхемы может
        # оказаться под встречным драйвером.
        for number in (13, 14, 15):
            tester.cmd(f"{P[VI53_PINS[number - 1]]}d{INPUT_PULLUP_MODE}")

        # Режим 0 принудительно держит OUT в нуле — конфликта не будет.
        tester.write_register(ADDR_CONTROL, tester.control_word(1, MODE0, rw=3))
        tester.write_register(ADDR_COUNTER[1], 2)
        tester.write_register(ADDR_COUNTER[1], 0)

        tester.cmd(
            f"{pin_gate}d{OUTPUT_MODE}1o"
            f"{pin_clk}d{OUTPUT_MODE}0o"
            f"{pin_out}d{INPUT_PULLUP_MODE}"
        )
        before = tester.cmd(f"{pin_out}d{INPUT_PULLUP_MODE}iq")[:1]

        tester.counter_pins[1] = candidate
        tester.clock(1, 4)
        after = tester.cmd(f"{pin_out}d{INPUT_PULLUP_MODE}iq")[:1]

        print(f"  {name:6s}: вывод {candidate['out']} до тактов {before.decode()}, "
              f"после {after.decode()}")
        if before == b"0" and after == b"1":
            found.append(name)

    check(len(found) == 1, f"раскладка не определена однозначно: {found}")
    print(f"  определён вариант: {found[0]}")
    tester.counter_pins[1] = dict(CH1_VARIANTS[found[0]])


def test_address_decode(tester):
    """Выборка регистров по A0/A1.

    При ~CS=0 и ~RD=0 микросхема выставляет на шину содержимое выбранного
    счётчика. Чтение по адресу A1A0=11 — операция «нет», шина уходит в третье
    состояние. Если все четыре адреса читаются одинаково, значит выводы A0/A1
    (19/20 — позиции ZIF-35/36) до микросхемы не доходят.
    """
    tester.cmd(
        f"{CS_PIN}d{OUTPUT_MODE}1o{RD_PIN}d{OUTPUT_MODE}1o{WR_PIN}d{OUTPUT_MODE}1o"
    )
    tester.cmd(f"{CS_PIN}d0o")
    tester.cmd(f"{RD_PIN}d0o")
    readings = {}
    for address in range(4):
        tester.set_address(address)
        readings[address] = [tester.read_byte() for _ in range(3)]
    tester.cmd(f"{RD_PIN}d1o")
    tester.cmd(f"{CS_PIN}d1o")

    for address, values in readings.items():
        print(f"  A1A0={address:02b}: " + " ".join(f"0x{v:02X}" for v in values))

    check(
        len({tuple(v) for v in readings.values()}) > 1,
        "все адреса читаются одинаково: выводы A0/A1 (19/20, позиции ZIF-35/36) "
        "не управляют микросхемой — проверьте их контакт",
    )
    check(
        readings[3][0] == 0xFF,
        f"чтение по A1A0=11 должно уводить шину в третье состояние, "
        f"прочитано 0x{readings[3][0]:02X}",
    )


def test_socket(tester):
    """Диагностика панели: жёсткие посадки и подтяжки на выводах.

    Полезно, когда микросхема «не отвечает»: позволяет отличить непропай /
    незащёлкнутый ZIF / отсутствие питания от неисправной ИС.
    """
    held_low, held_high = [], []
    for position, arduino_pin in enumerate(pin40, start=1):
        high = tester.cmd(f"{arduino_pin}d1e1oiq")
        low = tester.cmd(f"{arduino_pin}d1e0oiq")
        tester.cmd(f"{arduino_pin}d0e")
        if high[:1] != b"1":
            held_low.append(position)
        if low[:1] != b"0":
            held_high.append(position)
    print(f"  не удаётся выставить 1 (притянуто к GND): позиции {held_low}")
    print(f"  не удаётся выставить 0 (притянуто к Ucc): позиции {held_high}")

    print("  выводы 1..24 микросхемы (float / с подтяжкой):")
    for name, arduino_pin in zip(VI53_PINS, pin24):
        floating = tester.cmd(f"{arduino_pin}d0eiq").decode()
        pulled = tester.cmd(f"{arduino_pin}d2eiq").decode()
        note = ""
        if pulled == "0" and name not in ("GND",):
            note = "  <- притянут к нулю или микросхема управляет шиной"
        print(f"    {name:5s} (Arduino {arduino_pin:2d}): {floating} / {pulled}{note}")


def test_monitor(tester):
    """Информационный дамп: питание, такты, состояния выходов."""
    print(f"  VCC = вывод 24 -> Arduino {VCC_PIN}, GND = вывод 12 -> Arduino {GND_PIN}")
    for c in (0, 1, 2):
        pins = tester.counter_pins[c]
        print(
            f"  {COUNTER_NAMES[c]}: такт = вывод {pins['clk']}, "
            f"выход = вывод {pins['out']}, разрешение = вывод {pins['gate']}"
        )
    for c in (0, 1, 2):
        tester.gate(c, 1)
        tester.clk_level(c, 0)
        tester.release_out(c)
    for c in (0, 1, 2):
        print(f"  {COUNTER_NAMES[c]}: исходный уровень OUT = {tester.read_out(c)}")

    report = tester.chip_present()
    print(f"  шина при отпущенном ~CS/~RD: 0x{report['deselected']:02X}")
    print("  чтение счётчика 0: " + " ".join(f"0x{v:02X}" for v in report["selected"]))
    print(f"  значения воспроизводимы: {report['stable']}")


# ---------------------------------------------------------------------------
ORDER = ["power", "present", "bus", "address", "socket", "mode0", "edges",
         "mode2", "mode3", "mode4", "latch", "gate", "mode1"]


def main(argv=None):
    parser = argparse.ArgumentParser(description="Тестер КР580ВИ53 (DIP-24)")
    parser.add_argument("--port", default=DEFAULT_PORT, help="порт Arduino (COM11)")
    parser.add_argument("--variant", default="vi53", choices=sorted(CH1_VARIANTS),
                        help="раскладка выводов 13/14/15 у счётчика 1")
    parser.add_argument("--monitor", action="store_true",
                        help="только дамп состояния и проверка присутствия ИС")
    parser.add_argument("--detect", action="store_true",
                        help="определить раскладку выводов 13/14/15 по микросхеме")
    parser.add_argument("--test", action="append", choices=ORDER + ["detect"],
                        help="выполнить только указанные тесты")
    parser.add_argument("--counter", action="append", type=int, choices=[0, 1, 2],
                        default=None, help="ограничить тесты одним счётчиком")
    args = parser.parse_args(argv)

    tester = TestKR580VI53(port=args.port, variant=args.variant)
    counters = args.counter or [0, 1, 2]
    runner = Runner()
    try:
        if args.monitor:
            runner.run("monitor", test_monitor, tester)
            runner.run("socket", test_socket, tester)
            return 0 if runner.summary() else 1

        if args.detect:
            runner.run("detect", test_detect_variant, tester)

        selected = set(args.test) if args.test else set(ORDER)
        if not args.detect and "detect" in selected:
            runner.run("detect", test_detect_variant, tester)
        if "power" in selected:
            runner.run("power", test_power, tester)
        if "present" in selected:
            runner.run("chip_present", test_chip_present, tester)
        if "bus" in selected:
            runner.run("bus_float", test_bus_float, tester)
        if "address" in selected:
            runner.run("address_decode", test_address_decode, tester)
        if "socket" in selected:
            runner.run("socket", test_socket, tester)
        for counter in counters:
            if "mode0" in selected:
                runner.run(f"mode0/{counter}", test_mode0, tester, counter)
            if "edges" in selected:
                runner.run(f"mode0_edges/{counter}", test_mode0_edges, tester, counter)
            if "mode2" in selected:
                runner.run(f"mode2/{counter}", test_mode2, tester, counter)
            if "mode3" in selected:
                runner.run(f"mode3/{counter}", test_mode3, tester, counter)
            if "mode4" in selected:
                runner.run(f"mode4/{counter}", test_mode4, tester, counter)
            if "latch" in selected:
                runner.run(f"latch/{counter}", test_latch, tester, counter)
            if "gate" in selected:
                runner.run(f"gate/{counter}", test_gate, tester, counter)
            if "mode1" in selected:
                runner.run(f"mode1/{counter}", test_mode1, tester, counter)
    finally:
        try:
            tester.power_off()
        except Exception:  # noqa: BLE001 — безопасное состояние важнее ошибки
            pass

    return 0 if runner.summary() else 1


if __name__ == "__main__":
    sys.exit(main())
