from __future__ import annotations

from typing import Any, Sequence


class BinarySearch:
    @staticmethod
    def binary(arr: Sequence[Any], key: Any) -> int:
        if len(arr) == 0:
            return -1
        else:
            low = 0
            high = len(arr)
            mid = high // 2

            while low < high and arr[mid] != key:
                if arr[mid] < key:
                    low = mid + 1
                else:
                    high = mid
                mid = low + (high - low) // 2

            if low >= high:
                return -1
            return mid
