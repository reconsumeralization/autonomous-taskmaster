import pytest
from src.greeting import say_hello


def test_say_hello():
    """Tests the say_hello function."""
    assert say_hello() == "Hello, World!"
