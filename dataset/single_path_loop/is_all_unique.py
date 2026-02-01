class IsAllUnique:
    def is_all_unique(self, s: str) -> bool:
        length: int = len(s)

        if length > 26:
            return False

        num: int = 0
        i: int = 0

        while i < length:
            c: str = s[i]
            index: int = ord(c) - ord("a")

            if (num & (1 << index)) != 0:
                return False
            else:
                num = num | (1 << index)

            i = i + 1

        return True
