class GCD:
    @staticmethod
    def gcd(num1: int, num2: int) -> int:
        result: int = 1

        # make inputs non-negative
        num1 = num1 if 0 <= num1 else -num1
        num2 = num2 if 0 <= num2 else -num2

        if num1 == 0 and num2 == 0:
            return -1

        if num1 == 0 or num2 == 0:
            return num1 if num1 > num2 else num2

        i: int = 1
        while i <= num1 and i <= num2:
            if num1 % i == 0 and num2 % i == 0:
                result = i
            i = i + 1

        return result
