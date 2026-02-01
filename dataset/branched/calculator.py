class Calculator:
    def calculate(self, num1: int, num2: int, operator: str) -> float:
        output: float

        if operator == "+":
            output = num1 + num2
        elif operator == "-":
            output = num1 - num2
        elif operator == "*":
            output = num1 * num2
        elif operator == "/":
            output = num1 / num2  # Python semantics → float
        elif operator == "%":
            output = num1 % num2
        else:
            return -1.0

        return output
