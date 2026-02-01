from typing import List


class CompareArray:
    @staticmethod
    def arrcmp(a: List[int], b: List[int]) -> bool:
        if len(a) != len(b):
            return False

        i: int = 0
        while i < len(a):
            if a[i] != b[i]:
                return False
            i = i + 1

        return True
