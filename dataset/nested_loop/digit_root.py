class DigitRoot:
    def digit_root(self, num: int) -> int:
        while num >= 10:
            sum_: int = 0
            while num > 0:
                sum_ = sum_ + (num % 10)
                num = num // 10  # integer digit removal
            num = sum_
        return num
