class MySqrt:
    def my_sqrt(self, x: int) -> int:
        l: int = 0
        r: int = x
        ans: int = -1

        while l <= r:
            mid: int = l + (r - l) // 2
            if mid * mid <= x:
                ans = mid
                l = mid + 1
            else:
                r = mid - 1

        return ans
