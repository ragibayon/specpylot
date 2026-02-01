class AddLoop:
    @staticmethod
    def add_loop(x: int, y: int) -> int:
        sum: int = x
        if y > 0:
            n: int = y
            while n > 0:
                sum = sum + 1
                n = n - 1
        else:
            n: int = -y
            while n > 0:
                sum = sum - 1
                n = n - 1
        return sum
