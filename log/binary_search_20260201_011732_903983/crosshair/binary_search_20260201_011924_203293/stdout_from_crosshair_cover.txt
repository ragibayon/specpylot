# --- CrossHair cover target: binary_search.py:15 (def binary) ---
from binary_search import BinarySearch

def test_BinarySearch_binary():
    assert BinarySearch.binary(('', 0, -1, 0, 1), 0) == 3

def test_BinarySearch_binary_2():
    assert BinarySearch.binary((), '') == -1

def test_BinarySearch_binary_3():
    assert BinarySearch.binary((1), 0) == -1
