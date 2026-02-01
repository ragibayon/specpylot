from typing import List


class TwoSum:
    def two_sum(self, nums: List[int], target: int) -> List[int]:
        n: int = len(nums)

        i: int = 0
        while i < n:
            j: int = i + 1
            while j < n:
                if nums[i] + nums[j] == target:
                    return [i, j]
                j = j + 1
            i = i + 1

        return []
