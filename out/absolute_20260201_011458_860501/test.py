# --- CrossHair cover target: absolute.py:6 (def absolute) ---
from absolute import Absolute

def test_Absolute_absolute():
    assert Absolute.absolute(Absolute(), -1) == 1

def test_Absolute_absolute_2():
    assert Absolute.absolute(Absolute(), 0) == 0
