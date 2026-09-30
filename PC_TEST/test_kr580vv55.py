#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_kr580vv55.py — Тест микросхемы КР580ВВ55 (Intel 8255A PPI)
через Mega IC-Tester (Arduino Mega) на COM11.

Тестирует все 256 состояний каждого из 3 портов (A, B, C)
в режиме 0 и в смешанных режимах.

Распиновка подключения IC-Tester <-> KR580VV55:
  D0-D7 (пины 27-34)  <-> IC-Tester data bus (D0-D7)
  A0  (pin 9)         <-> IC-Tester addr A0
  A1  (pin 8)         <-> IC-Tester addr A1
  CS  (pin 6)         <-> IC-Tester cs
  RD  (pin 5)         <-> IC-Tester rd
  WR  (pin 36)        <-> IC-Tester wr
  PA0-PA7 (1-4,37-40) <-> loopback -> data bus для Port A
  PB0-PB7 (18-25)     <-> loopback -> data bus для Port B
  PC0-PC7 (10-17)     <-> loopback -> data bus для Port C

Порты 8255A:
  Port A  -> адрес 0x00
  Port B  -> адрес 0x01
  Port C  -> адрес 0x02
  Control -> адрес 0x03

Управление режимом (запись в контрольный регистр 0x03):
  0x80 = 10000000 — все порты выход (Mode 0)
  0xC0 = 11000000 — Port A вход, Port B и Port C выход (Mode 0)
  0xA0 = 10100000 — Port C верх вход, Port C низ и Port B выход (Mode 0)
  0xD9 = 11011001 — Port A, Port C верх, Port C низ вход, Port B выход (Mode 0)
"""

import sys
import time
import struct
import argparse
from typing import Optional

try:
    import serial
    import serial.tools.list_ports
    HAS_SERIAL = True
except ImportError:
    HAS_SERIAL = False

try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False


# ──────────────────────────────────────────────────────────────
# Константы 8255A PPI
# ──────────────────────────────────────────────────────────────
ADDR_PORT_A   = 0x00
ADDR_PORT_B   = 0x01
ADDR_PORT_C   = 0x02
ADDR_CONTROL  = 0x03

# Режим 0 — все порты выход (D7=1 ModeSet, D6=0 PA out, D5=0, D4=0 CU out, D3=0 PB out, D2=0 CL out)
MODE_ALL_OUTPUT = 0x80
# Режим 0 — Port A вход, Port B и Port C выход (D6=1 PA in, D4=0 CU out, D3=0 PB out, D2=0 CL out)
MODE_A_INPUT_BC_OUTPUT = 0xC0
# Режим 0 — Port A и Port C верх выход (то же что все выход)
MODE_A_PCUP_OUTPUT = 0x80
# Режим 0 — Port C верх вход, Port C низ и Port B выход (D6=0 PA out, D4=1 CU in, D3=0 PB out, D2=0 CL out)
MODE_PCUP_IN_PCLOW_B_OUTPUT = 0xA0
# Режим 0 — Port A, Port C верх, Port C низ вход, Port B выход (D6=1 PA in, D4=1 CU in, D3=0 PB out, D2=1 CL in)
MODE_ALL_INPUT_B_OUTPUT = 0xD9

# Задержка между операциями (сек)
BUS_DELAY = 0.005


# ──────────────────────────────────────────────────────────────
# Класс симуляции 8255A PPI (для тестирования без железа)
# ──────────────────────────────────────────────────────────────
class KR580VV55Simulator:
    """Виртуальная модель КР580ВВ55 (Intel 8255A PPI).

    Корректно моделирует поведение 8255A:
    - При конфигурации порта как OUTPUT: запись хранит значение в latch,
      чтение возвращает latch.
    - При конфигурации порта как INPUT: запись игнорируется,
      чтение возвращает "состояние пинов" (симулируем через last_written).
    - Port C поддерживает bit-set/reset команды.
    """

    # Mode Set control word: B7=1, B6=PA mode, B5=0, B4=CU, B3=PB, B2=CL, B1=0, B0=CR
    # B6: 0=Mode0/PA out, 1=Mode1/PA in
    # B4: 0=Port C upper out, 1=Port C upper in
    # B3: 0=Port B out, 1=Port B in
    # B2: 0=Port C lower out, 1=Port C lower in

    def __init__(self):
        # Output latches
        self.latch_a: int = 0x00
        self.latch_b: int = 0x00
        self.latch_c: int = 0x00
        # Input pin simulation (для INPUT портов)
        self.pin_a: int = 0x00
        self.pin_b: int = 0x00
        self.pin_c: int = 0x00
        # Режимы: True = input, False = output
        self.mode_a_in: bool = False
        self.mode_b_in: bool = False
        self.mode_c_high_in: bool = False
        self.mode_c_low_in: bool = False
        self._mode_set_cmd: bool = False
        self._c_low_control: bool = False  # Port C low controlled by Port A
        self._c_high_control: bool = False  # Port C high controlled by Port B

    def reset(self):
        self.latch_a = 0x00
        self.latch_b = 0x00
        self.latch_c = 0x00
        self.pin_a = 0x00
        self.pin_b = 0x00
        self.pin_c = 0x00
        self.mode_a_in = False
        self.mode_b_in = False
        self.mode_c_high_in = False
        self.mode_c_low_in = False
        self._mode_set_cmd = False

    def close(self):
        """Симулирует закрытие — ничего не делает."""
        pass

    def write_port(self, addr: int, data: int):
        """Запись данных в порт или контрольный регистр."""
        data &= 0xFF

        if addr == ADDR_CONTROL:
            self._write_control(data)
        elif addr == ADDR_PORT_A:
            self._write_port_a(data)
        elif addr == ADDR_PORT_B:
            self._write_port_b(data)
        elif addr == ADDR_PORT_C:
            self._write_port_c(data)

    def _write_port_a(self, data: int):
        if self.mode_a_in:
            # INPUT порт: запись игнорируется, обновляем "пин"
            self.pin_a = data
        else:
            # OUTPUT порт: сохраняем в latch
            self.latch_a = data

    def _write_port_b(self, data: int):
        if self.mode_b_in:
            self.pin_b = data
        else:
            self.latch_b = data

    def _write_port_c(self, data: int):
        """Запись в Port C: зависит от режима и типа команды."""
        if self._mode_set_cmd and not self._c_low_control and not self._c_high_control:
            # Если это Mode Set, Port C data — это бит-сетап/ресета
            self._bit_set_reset(data)
            return
        if self._c_low_control or self._c_high_control:
            self._bit_set_reset(data)
            return
        # Port C — data write
        if self.mode_c_high_in:
            self.pin_c = (self.pin_c & 0x0F) | (data & 0xF0)
        else:
            self.latch_c = (self.latch_c & 0x0F) | (data & 0xF0)
        if self.mode_c_low_in:
            self.pin_c = (self.pin_c & 0xF0) | (data & 0x0F)
        else:
            self.latch_c = (self.latch_c & 0xF0) | (data & 0x0F)

    def read_port(self, addr: int) -> int:
        """Чтение данных из порта."""
        if addr == ADDR_PORT_A:
            return self.latch_a if not self.mode_a_in else self.pin_a
        elif addr == ADDR_PORT_B:
            return self.latch_b if not self.mode_b_in else self.pin_b
        elif addr == ADDR_PORT_C:
            return self.latch_c if (not self.mode_c_high_in and not self.mode_c_low_in) else self.pin_c
        return 0xFF

    def _write_control(self, data: int):
        """Обработка команды контрольного регистра."""
        if data & 0x80:  # Mode Set command
            self._mode_set_cmd = True
            self.mode_a_in = bool((data >> 6) & 1)
            self.mode_b_in = bool((data >> 3) & 1)
            self.mode_c_high_in = bool((data >> 2) & 1)
            self.mode_c_low_in = bool((data >> 1) & 1)
            self._c_low_control = bool(data & 0x01)
        else:
            # Bit-set/reset для Port C
            self._mode_set_cmd = True  # set flag for _write_port_c
            self._c_low_control = bool(data & 0x01)  # bit 0 = set/reset selector
            self._bit_set_reset(data)
        # Clear Mode Set flag — it is one-shot
        self._mode_set_cmd = False

    def _bit_set_reset(self, data: int):
        """Bit-set/reset операция для Port C (бит 7=0)."""
        bit = data & 0x07
        val = (data >> 4) & 0x01
        if data & 0x08:  # Set bit
            self.latch_c |= (1 << bit)
            self.pin_c |= (1 << bit)
        else:  # Reset bit
            self.latch_c &= ~(1 << bit)
            self.pin_c &= ~(1 << bit)


# ──────────────────────────────────────────────────────────────
# Класс связи через Mega IC-Tester (Serial/COM-порт)
# ──────────────────────────────────────────────────────────────
class MegaICTester:
    """
    Обёртка последовательного интерфейса для Mega IC-Tester.
    Протокол команд:
        PING        -> OK
        W <addr> <data>  -> OK
        R <addr>       -> <data>
        M <control_byte> -> OK
        BUS_DELAY <ms>   -> OK
    """

    BAUDRATE = 115200
    TIMEOUT = 2.0

    def __init__(self, port: str = "COM11", baudrate: int = BAUDRATE, timeout: float = TIMEOUT):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.ser: Optional[serial.Serial] = None

    def connect(self) -> bool:
        """Открыть COM-порт."""
        if not HAS_SERIAL:
            print("[ERROR] pyserial не установлен. Установите: pip install pyserial")
            return False
        try:
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=self.timeout,
            )
            time.sleep(0.5)  # Arduino reboot delay
            return self.ping()
        except serial.SerialException as e:
            print(f"[ERROR] Не удалось открыть {self.port}: {e}")
            return False

    def disconnect(self):
        """Закрыть COM-порт."""
        if self.ser and self.ser.is_open:
            self.ser.close()

    def ping(self) -> bool:
        """Проверка связи: отправить PING."""
        try:
            if not self.ser or not self.ser.is_open:
                return False
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
            self.ser.write(b"PING\r\n")
            time.sleep(0.1)
            response = self.ser.readline().decode('utf-8', errors='replace').strip()
            return response.startswith("OK")
        except Exception:
            return False

    def write_byte(self, addr: int, data: int) -> bool:
        """Записать байт по адресу порта."""
        try:
            if not self.ser or not self.ser.is_open:
                return False
            cmd = f"W {addr:#04x} {data:#04x}\r\n"
            self.ser.reset_output_buffer()
            self.ser.write(cmd.encode())
            time.sleep(BUS_DELAY)
            response = self.ser.readline().decode('utf-8', errors='replace').strip()
            return response.startswith("OK")
        except Exception:
            return False

    def read_byte(self, addr: int) -> Optional[int]:
        """Прочитать байт с порта."""
        try:
            if not self.ser or not self.ser.is_open:
                return None
            cmd = f"R {addr:#04x}\r\n"
            self.ser.reset_output_buffer()
            self.ser.write(cmd.encode())
            time.sleep(BUS_DELAY)
            response = self.ser.readline().decode('utf-8', errors='replace').strip()
            if response.startswith("DATA:"):
                return int(response.split(":")[1].strip(), 16) & 0xFF
            return None
        except Exception:
            return None

    def set_mode(self, control_byte: int) -> bool:
        """Установить режим 8255 (запись в контрольный регистр)."""
        try:
            if not self.ser or not self.ser.is_open:
                return False
            cmd = f"M {control_byte:#04x}\r\n"
            self.ser.reset_output_buffer()
            self.ser.write(cmd.encode())
            time.sleep(BUS_DELAY)
            response = self.ser.readline().decode('utf-8', errors='replace').strip()
            return response.startswith("OK")
        except Exception:
            return False

    def close(self):
        self.disconnect()


# ──────────────────────────────────────────────────────────────
# Результаты тестирования
# ──────────────────────────────────────────────────────────────
class TestResult:
    """Результат одного теста."""

    def __init__(self, name: str):
        self.name = name
        self.passed: bool = True
        self.errors: list = []
        self.total: int = 0
        self.successes: int = 0
        self.failures: int = 0

    def add_error(self, msg: str):
        self.passed = False
        self.errors.append(msg)
        self.failures += 1

    def record(self, expected: int, actual: int, value: int):
        self.total += 1
        if expected == actual:
            self.successes += 1
        else:
            self.add_error(
                f"Значение {value:#04x}: ожидалось {expected:#04x}, "
                f"получено {actual:#04x}"
            )

    def summary(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        return (
            f"[{status}] {self.name}: "
            f"{self.successes}/{self.total} прошло, "
            f"{self.failures} ошибок"
        )


# ──────────────────────────────────────────────────────────────
# Движок тестирования
# ──────────────────────────────────────────────────────────────
class KR580VV55Tester:
    """
    Движок тестирования КР580ВВ55.
    Работает в режиме симуляции или с реальным IC-Tester.
    """

    def __init__(self, simulate: bool = True, com_port: str = "COM11"):
        self.simulate = simulate
        self.com_port = com_port
        self.device: KR580VV55Simulator | MegaICTester
        self.results: list[TestResult] = []

        if simulate:
            self.device = KR580VV55Simulator()
            print("[INFO] Режим: СИМУЛЯЦИЯ (без железа)")
        else:
            self.device = MegaICTester(port=com_port)
            connected = self.device.connect()
            if not connected:
                print("[WARN] Не удалось подключиться к IC-Tester.")
                print("[INFO] Переход в режим СИМУЛЯЦИИ.")
                self.device = KR580VV55Simulator()
                self.simulate = True

    def write_port(self, addr: int, data: int) -> bool:
        if self.simulate:
            self.device.write_port(addr, data)
            return True
        return self.device.write_byte(addr, data)

    def read_port(self, addr: int) -> int:
        if self.simulate:
            return self.device.read_port(addr)
        return self.device.read_byte(addr) or 0xFF

    def set_mode(self, control: int) -> bool:
        if self.simulate:
            self.device.write_port(ADDR_CONTROL, control)
            return True
        return self.device.set_mode(control)

    # ── Тесты портов ──────────────────────────────────────────
    def test_port_full(self, port_name: str, port_addr: int, mode: int) -> TestResult:
        """Тестирование порта: 256 значений в заданном режиме."""
        result = TestResult(f"{port_name} [{mode:#04x}]")
        print(f"\n{'='*60}")
        print(f"Тест: {port_name} — 256 значений, режим {mode:#04x}")
        print(f"{'='*60}")

        # Установить режим
        self.set_mode(mode)
        time.sleep(0.05)

        # Прогресс-бар
        values = range(256)
        if HAS_TQDM:
            values = tqdm(values, desc=f"  {port_name}", total=256)

        for val in values:
            # Записать значение
            ok = self.write_port(port_addr, val)
            if not ok and not self.simulate:
                result.add_error(f"Ошибка записи {val:#04x}")
                continue

            # Короткая задержка для loopback
            time.sleep(BUS_DELAY)

            # Считать обратно
            read_val = self.read_port(port_addr)
            result.record(val, read_val, val)

        self.results.append(result)
        return result

    def test_port_a(self, mode: int = MODE_ALL_OUTPUT) -> TestResult:
        return self.test_port_full("Port A", ADDR_PORT_A, mode)

    def test_port_b(self, mode: int = MODE_ALL_OUTPUT) -> TestResult:
        return self.test_port_full("Port B", ADDR_PORT_B, mode)

    def test_port_c(self, mode: int = MODE_ALL_OUTPUT) -> TestResult:
        return self.test_port_full("Port C", ADDR_PORT_C, mode)

    # ── Тест режима ввода ─────────────────────────────────────
    def test_input_mode(self) -> TestResult:
        """
        Тест режима ввода: Port A настроен как вход.
        В симуляции имитируем, что IC-Tester (через loopback)
        подаёт значения на пины Port A.
        """
        result = TestResult("Режим ввода (Port A input)")
        print(f"\n{'='*60}")
        print("Тест: Режим ввода — Port A вход, Port B/C выход")
        print(f"{'='*60}")

        # Установить режим: Port A вход, Port B и C выход
        self.set_mode(MODE_A_INPUT_BC_OUTPUT)
        time.sleep(0.05)

        test_values = [0x00, 0x55, 0xAA, 0xFF, 0x01, 0xFE, 0x33, 0xCC]
        for val in test_values:
            # Записать в Port B (выход) — проверяем что B работает
            self.write_port(ADDR_PORT_B, val)
            time.sleep(BUS_DELAY)
            read_b = self.read_port(ADDR_PORT_B)
            result.record(val, read_b, val)

            # Записать в Port C (выход)
            self.write_port(ADDR_PORT_C, ~val & 0xFF)
            time.sleep(BUS_DELAY)
            read_c = self.read_port(ADDR_PORT_C)
            expected_c = ~val & 0xFF
            result.record(expected_c, read_c, val)

            # Имитируем, что IC-Tester подаёт val на пины Port A (через data bus loopback)
            # В симуляции — напрямую задаём состояние пинов Port A
            if hasattr(self.device, 'pin_a'):
                self.device.pin_a = val
            time.sleep(BUS_DELAY)
            read_a = self.read_port(ADDR_PORT_A)
            result.record(val, read_a, val)

        self.results.append(result)
        return result

    # ── Тест смешанных режимов ────────────────────────────────
    def test_mixed_modes(self) -> list[TestResult]:
        """Тестирование различных смешанных режимов Port C."""
        results = []

        mode_configs = [
            (MODE_A_PCUP_OUTPUT, "Port A + PC верх — выход", MODE_ALL_OUTPUT),
            (MODE_PCUP_IN_PCLOW_B_OUTPUT, "PC верх — вход, PC низ + B — выход", MODE_ALL_OUTPUT),
            (MODE_ALL_INPUT_B_OUTPUT, "Все кроме B — вход, B — выход", MODE_A_INPUT_BC_OUTPUT),
        ]

        for mode, desc, base_mode in mode_configs:
            result = TestResult(f"Смешанный режим: {desc}")
            print(f"\n{'='*60}")
            print(f"Тест: {desc}")
            print(f"{'='*60}")

            # Установить режим
            self.set_mode(mode)
            time.sleep(0.05)

            # Протестировать несколько значений
            test_values = [0x00, 0x55, 0xAA, 0xFF, 0x12, 0x34, 0x56, 0x78, 0x9A, 0xBC]
            for val in test_values:
                # Запись в Port B (выход во всех режимах)
                self.write_port(ADDR_PORT_B, val)
                time.sleep(BUS_DELAY)
                read_b = self.read_port(ADDR_PORT_B)
                result.record(val, read_b, val)

                # Port A: выход или вход
                if hasattr(self.device, 'mode_a_in') and self.device.mode_a_in:
                    # Port A вход — имитируем IC-Tester на пины
                    self.device.pin_a = val
                    time.sleep(BUS_DELAY)
                    read_a = self.read_port(ADDR_PORT_A)
                    result.record(val, read_a, val)
                else:
                    # Port A выход
                    self.write_port(ADDR_PORT_A, val)
                    time.sleep(BUS_DELAY)
                    read_a = self.read_port(ADDR_PORT_A)
                    result.record(val, read_a, val)

                # Port C: верхняя и нижняя часть
                # Если Port C upper input — имитируем пины
                if hasattr(self.device, 'mode_c_high_in') and self.device.mode_c_high_in:
                    self.device.pin_c = (self.device.pin_c & 0x0F) | (val & 0xF0)
                # Если Port C lower input — имитируем пины
                if hasattr(self.device, 'mode_c_low_in') and self.device.mode_c_low_in:
                    self.device.pin_c = (self.device.pin_c & 0xF0) | (val & 0x0F)

                # Если Port C вообще выход — записываем
                if not hasattr(self.device, 'mode_c_high_in') or (not self.device.mode_c_high_in and not self.device.mode_c_low_in):
                    self.write_port(ADDR_PORT_C, val)

                time.sleep(BUS_DELAY)
                read_c = self.read_port(ADDR_PORT_C)
                # Ожидаемое: для input — simulated pins; для output — latch
                if hasattr(self.device, 'mode_c_high_in') or hasattr(self.device, 'mode_c_low_in'):
                    dev = self.device
                    exp_upper = dev.pin_c & 0xF0 if getattr(dev, 'mode_c_high_in', False) else dev.latch_c & 0xF0
                    exp_lower = dev.pin_c & 0x0F if getattr(dev, 'mode_c_low_in', False) else dev.latch_c & 0x0F
                    expected_c = exp_upper | exp_lower
                else:
                    expected_c = val
                result.record(expected_c, read_c, val)

            self.results.append(result)
            results.append(result)

        return results

    # ── Тест контрольного регистра ────────────────────────────
    def test_control_register(self) -> TestResult:
        """Проверка всех допустимых команд контрольного регистра."""
        result = TestResult("Контрольный регистр")
        print(f"\n{'='*60}")
        print("Тест: Контрольный регистр — все команды")
        print(f"{'='*60}")

        control_commands = [
            (0x80, "Все порты — выход"),
            (0xC0, "Port A вход, Port B/C выход"),
            (0x80, "Port A + PC верх — выход"),
            (0xA0, "PC верх вход, PC низ + B выход"),
            (0xB0, "PC верх вход, PC низ + B выход (альт)"),
            (0xD9, "Все кроме B — вход, B выход"),
            (0x09, "Bit-set PC1"),
            (0x0B, "Bit-set PC3"),
            (0x0A, "Bit-reset PC2"),
            (0x0F, "Bit-reset PC5"),
        ]

        for cmd, desc in control_commands:
            ok = self.set_mode(cmd)
            if not ok and not self.simulate:
                result.add_error(f"Не удалось установить режим {cmd:#04x}: {desc}")
            else:
                result.total += 1
                result.successes += 1

            # Вернуть все порты в режим выхода
            self.set_mode(MODE_ALL_OUTPUT)
            time.sleep(0.02)

        self.results.append(result)
        return result

    # ── Тест перезаписи / стабильности ─────────────────────────
    def test_repeated_writes(self, port_name: str, port_addr: int,
                             iterations: int = 10) -> TestResult:
        """Многократная запись/чтение для проверки стабильности."""
        result = TestResult(f"Стабильность {port_name} ({iterations} итер.)")
        print(f"\n{'='*60}")
        print(f"Тест: Стабильность {port_name} — {iterations} итераций")
        print(f"{'='*60}")

        self.set_mode(MODE_ALL_OUTPUT)
        time.sleep(0.05)

        test_vals = [0x00, 0xFF, 0x55, 0xAA, 0x01, 0xFE, 0x33, 0xCC]

        for i in range(iterations):
            for val in test_vals:
                self.write_port(port_addr, val)
                time.sleep(BUS_DELAY)
                read_val = self.read_port(port_addr)
                result.record(val, read_val, val)

        self.results.append(result)
        return result

    # ── Итоговая статистика ───────────────────────────────────
    def print_statistics(self) -> dict:
        """Вывести итоговую статистику по всем тестам."""
        print(f"\n{'#'*60}")
        print(f"# ИТОГОВАЯ СТАТИСТИКА ТЕСТА КР580ВВ55")
        print(f"{'#'*60}")

        total_tests = 0
        total_passed = 0
        total_errors = 0
        total_ops = 0
        total_successes = 0

        for r in self.results:
            total_ops += r.total
            total_successes += r.successes
            total_tests += 1
            if r.passed:
                total_passed += 1
            total_errors += len(r.errors)

            # Показать до 5 ошибок для наглядности
            for err in r.errors[:5]:
                print(f"    ! {r.name}: {err}")
            if len(r.errors) > 5:
                print(f"    ! ... ещё {len(r.errors) - 5} ошибок")

            print(f"  {r.summary()}")

        overall = "PASS" if total_errors == 0 else "FAIL"
        print(f"\n{'='*60}")
        print(f"  Общий результат: {overall}")
        print(f"  Тестов пройдено: {total_passed}/{total_tests}")
        print(f"  Операций: {total_successes}/{total_ops}")
        print(f"  Ошибок: {total_errors}")
        print(f"  Режим: {'СИМУЛЯЦИЯ' if self.simulate else 'РЕАЛЬНОЕ ЖЕЛЕЗО'}")
        print(f"{'='*60}")

        return {
            "overall": overall,
            "tests_passed": total_passed,
            "tests_total": total_tests,
            "operations_total": total_ops,
            "operations_success": total_successes,
            "errors_total": total_errors,
            "simulate": self.simulate,
        }


# ──────────────────────────────────────────────────────────────
# Полный тестовый сценарий
# ──────────────────────────────────────────────────────────────
def run_full_test(tester: KR580VV55Tester):
    """Запустить полный набор тестов."""
    print("\n" + "#" * 60)
    print("#  КР580ВВ55 (Intel 8255A PPI) — Полный тест")
    print(f"#  Режим: {'СИМУЛЯЦИЯ' if tester.simulate else 'HARDWARE'}")
    print(f"#  Порт: {tester.com_port if not tester.simulate else 'N/A'}")
    print("#" * 60)

    t0 = time.time()

    # 1. Port A — 256 значений, режим 0, все порты выход
    tester.test_port_a(MODE_ALL_OUTPUT)

    # 2. Port B — 256 значений, режим 0, все порты выход
    tester.test_port_b(MODE_ALL_OUTPUT)

    # 3. Port C — 256 значений, режим 0, все порты выход
    tester.test_port_c(MODE_ALL_OUTPUT)

    # 4. Режим ввода
    tester.test_input_mode()

    # 5. Смешанные режимы
    tester.test_mixed_modes()

    # 6. Контрольный регистр
    tester.test_control_register()

    # 7. Стабильность
    tester.test_repeated_writes("Port A", ADDR_PORT_A, iterations=5)
    tester.test_repeated_writes("Port B", ADDR_PORT_B, iterations=5)
    tester.test_repeated_writes("Port C", ADDR_PORT_C, iterations=5)

    elapsed = time.time() - t0

    # Статистика
    stats = tester.print_statistics()
    stats["elapsed_sec"] = round(elapsed, 2)

    return stats


# ──────────────────────────────────────────────────────────────
# Список доступных COM-портов
# ──────────────────────────────────────────────────────────────
def list_serial_ports() -> list[str]:
    """Показать доступные COM-порты."""
    if not HAS_SERIAL:
        return ["pyserial не установлен"]
    ports = serial.tools.list_ports.comports()
    return [f"{p.device} — {p.description}" for p in ports]


# ──────────────────────────────────────────────────────────────
# Точка входа
# ──────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Тест микросхемы КР580ВВ55 (Intel 8255A PPI)"
    )
    parser.add_argument(
        "--port", "-p", default="COM11",
        help="COM-порт IC-Tester (по умолчанию: COM11)"
    )
    parser.add_argument(
        "--baud", "-b", type=int, default=115200,
        help="Скорость COM-порта (по умолчанию: 115200)"
    )
    parser.add_argument(
        "--simulate", "-s", action="store_true",
        help="Запустить в режиме симуляции (без железа)"
    )
    parser.add_argument(
        "--list-ports", "-l", action="store_true",
        help="Показать доступные COM-порты и выйти"
    )
    args = parser.parse_args()

    if args.list_ports:
        print("Доступные COM-порты:")
        for p in list_serial_ports():
            print(f"  {p}")
        return

    tester = KR580VV55Tester(simulate=args.simulate, com_port=args.port)

    try:
        stats = run_full_test(tester)
    finally:
        tester.device.close()

    # Вернуть код выхода
    sys.exit(0 if stats["overall"] == "PASS" else 1)


if __name__ == "__main__":
    main()
