from typing import List


class Biggest:
    @staticmethod
    def biggest(a: List[int]) -> int:
        if len(a) == 0:
            return -1

        index: int = 0
        biggest: int = 0

        while len(a) - index > 0:
            if a[index] > a[biggest]:
                biggest = index
            index = index + 1

        return biggest
