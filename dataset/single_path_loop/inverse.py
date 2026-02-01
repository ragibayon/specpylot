from typing import List


class Inverse:
    @staticmethod
    def inverse(x: List[int], y: List[int]) -> bool:
        if len(x) != len(y):
            return False

        index: int = 0
        while index < len(x):
            if x[index] != y[len(x) - 1 - index]:
                return False
            else:
                index = index + 1

        return True
