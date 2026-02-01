class JewelsInStones:
    def num_jewels_in_stones(self, jewels: str, stones: str) -> int:
        jewels_count: int = 0
        jewels_length: int = len(jewels)
        stones_length: int = len(stones)

        i: int = 0
        while i < stones_length:
            stone: str = stones[i]

            j: int = 0
            while j < jewels_length:
                jewel: str = jewels[j]
                if stone == jewel:
                    jewels_count = jewels_count + 1
                    break
                j = j + 1

            i = i + 1

        return jewels_count
