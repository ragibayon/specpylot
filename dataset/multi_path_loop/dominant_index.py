from typing import List


class DominantIndex:
    @staticmethod
    def dominant_index(nums: List[int]) -> int:
        biggest_index: int = 0
        n: int = len(nums)

        i: int = 0
        while i < n:
            if nums[i] > nums[biggest_index]:
                biggest_index = i
            i = i + 1

        i = 0
        while i < n:
            if i != biggest_index and 2 * nums[i] > nums[biggest_index]:
                return -1
            i = i + 1

        return biggest_index
