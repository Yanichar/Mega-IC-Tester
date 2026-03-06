def generate_memory_patterns():
    patterns = [
        bytes([0] * 32),
        bytes([0xFF] * 32),
        bytes([0xAA] * 32),
        bytes([0x55] * 32),
        bytes([0xCC] * 32),
        bytes([0x33] * 32),
        bytes([0xF0] * 32),
        bytes([0x0F] * 32),
        bytes([i % 256 for i in range(32)]),
        bytes([(255 - i) % 256 for i in range(32)]),
    ]

    chess = []
    for i in range(32):
        chess.append(0xAA if i % 2 == 0 else 0x55)
    patterns.append(bytes(chess))

    # 12. Inverse checkerboard pattern
    chess_inv = []
    for i in range(32):
        chess_inv.append(0x55 if i % 2 == 0 else 0xAA)
    patterns.append(bytes(chess_inv))

    # 13. Random pattern 1 (fixed for reproducibility)
    import random

    random.seed(42)
    patterns.append(bytes([random.randint(0, 255) for _ in range(32)]))

    # 14. Random pattern 2
    random.seed(123)
    patterns.append(bytes([random.randint(0, 255) for _ in range(32)]))

    # 15. Gradient from 0 to 255
    gradient = []
    for i in range(32):
        gradient.append(int(i * 255 / 31))
    patterns.append(bytes(gradient))

    # 16. Reverse gradient
    patterns.append(bytes(reversed(gradient)))

    # 17. All bits except LSB = 1
    patterns.append(bytes([0xFE] * 32))

    # 18. Only LSB = 1
    patterns.append(bytes([0x01] * 32))

    # 19. Only MSB = 1
    patterns.append(bytes([0x80] * 32))

    # 20. All bits except MSB = 1
    patterns.append(bytes([0x7F] * 32))

    # 21. Alternating 0x3C (00111100)
    patterns.append(bytes([0x3C] * 32))

    # 22. Alternating 0xC3 (11000011)
    patterns.append(bytes([0xC3] * 32))

    # 23. "Knight's move" pattern (0x88, 0x44, 0x22, 0x11)
    knight = []
    for i in range(32):
        if i % 4 == 0:
            knight.append(0x88)
        elif i % 4 == 1:
            knight.append(0x44)
        elif i % 4 == 2:
            knight.append(0x22)
        else:
            knight.append(0x11)
    patterns.append(bytes(knight))

    # 24. Sine wave pattern
    import math

    sine = []
    for i in range(32):
        value = int(127.5 + 127.5 * math.sin(2 * math.pi * i / 32))
        sine.append(value)
    patterns.append(bytes(sine))

    # 25. Cosine wave pattern
    cosine = []
    for i in range(32):
        value = int(127.5 + 127.5 * math.cos(2 * math.pi * i / 32))
        cosine.append(value)
    patterns.append(bytes(cosine))

    # 26. Bit shift pattern
    shift = []
    for i in range(32):
        shift.append((1 << (i % 8)) - 1)
    patterns.append(bytes(shift))

    # 27. Inverse bit shift pattern
    shift_inv = []
    for i in range(32):
        shift_inv.append(0xFF ^ ((1 << (i % 8)) - 1))
    patterns.append(bytes(shift_inv))

    # 28. Prime numbers pattern (modulo 256)
    primes = [
        2,
        3,
        5,
        7,
        11,
        13,
        17,
        19,
        23,
        29,
        31,
        37,
        41,
        43,
        47,
        53,
        59,
        61,
        67,
        71,
        73,
        79,
        83,
        89,
        97,
        101,
        103,
        107,
        109,
        113,
        127,
        131,
    ]
    patterns.append(bytes([p % 256 for p in primes[:32]]))

    # 29. Fibonacci pattern (modulo 256)
    fib = [1, 1]
    for i in range(30):
        fib.append((fib[-1] + fib[-2]) % 256)
    patterns.append(bytes(fib[:32]))

    # 30. Powers of two pattern
    powers = []
    for i in range(32):
        powers.append(1 << (i % 8))
    patterns.append(bytes(powers))

    # 31. Left-to-right fill pattern
    fill = []
    for i in range(32):
        fill.append(0xFF if i < 16 else 0x00)
    patterns.append(bytes(fill))

    # 32. Right-to-left fill pattern
    fill_rev = []
    for i in range(32):
        fill_rev.append(0x00 if i < 16 else 0xFF)
    patterns.append(bytes(fill_rev))

    return patterns


def get_bit_from_pattern(pattern, bit_index):
    if bit_index < 0 or bit_index > 65535:
        raise ValueError(f"bit_index must be between 0 and 255, got {bit_index}")

    byte_index = bit_index // 8
    bit_in_byte = bit_index % 8

    data_byte = pattern[byte_index]
    return (data_byte >> bit_in_byte) & 1
