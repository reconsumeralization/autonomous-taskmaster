# region Add Numbers Function

# INPUT: a (int | float | bool): The first number.
# INPUT: b (int | float | bool): The second number.
# OUTPUT: (int | float): The sum of a and b.
def add_numbers(a, b):
    """
    Adds two numbers together.
    Raises TypeError if either argument is not int, float, or bool.
    """
    valid_types = (int, float, bool)
    if not isinstance(a, valid_types) or not isinstance(b, valid_types):
        raise TypeError("Both arguments must be int, float, or bool.")
    return a + b

# endregion Add Numbers Function 