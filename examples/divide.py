from __future__ import annotations


def divide(a: float, b: float) -> float:
    if b == 0:
        raise ZeroDivisionError("b must not be zero")
    return a / b


if __name__ == "__main__":
    print(divide(10, 2))  # 5.0
