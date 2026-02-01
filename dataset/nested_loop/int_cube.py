class IntCube:
    @staticmethod
    def cube_of(x: int) -> int:
        neg: bool = False

        if x < 0:
            neg = True
            x = -x

        res: int = 0

        i: int = 0
        while i < x:
            j: int = 0
            while j < x:
                k: int = 0
                while k < x:
                    res = res + 1
                    k = k + 1
                j = j + 1
            i = i + 1

        return -res if neg else res
