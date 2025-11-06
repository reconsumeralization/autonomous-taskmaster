import pytest
import importlib

from src.adder import add_numbers

# region Test Add Numbers Functionality
# INPUT: None
# OUTPUT: None
def test_add_numbers_positive():
    """Test adding two positive integers."""
    assert add_numbers(2, 3) == 5

def test_add_numbers_negative():
    """Test adding two negative integers."""
    assert add_numbers(-2, -3) == -5

def test_add_numbers_mixed():
    """Test adding a positive and a negative integer."""
    assert add_numbers(5, -3) == 2

def test_add_numbers_zero():
    """Test adding zero."""
    assert add_numbers(10, 0) == 10
    assert add_numbers(0, -7) == -7
    assert add_numbers(0, 0) == 0

def test_add_positive_floats():
    """Test adding two positive floats."""
    assert add_numbers(2.5, 3.5) == pytest.approx(6.0)

def test_add_positive_and_negative_floats():
    """Test adding positive and negative floats."""
    assert add_numbers(5.5, -3.2) == pytest.approx(2.3)

def test_add_negative_floats():
    """Test adding two negative floats."""
    assert add_numbers(-5.1, -3.2) == pytest.approx(-8.3)

def test_add_integer_and_float():
    """Test adding an integer and a float."""
    assert add_numbers(5, 3.5) == pytest.approx(8.5)

def test_add_float_and_integer():
    """Test adding a float and an integer."""
    assert add_numbers(3.5, 5) == pytest.approx(8.5)

def test_add_large_numbers():
    """Test adding very large numbers."""
    assert add_numbers(1e18, 1e18) == pytest.approx(2e18)

def test_add_small_numbers():
    """Test adding very small numbers."""
    assert add_numbers(1e-10, 2e-10) == pytest.approx(3e-10)

@pytest.mark.parametrize("a,b", [
    ("2", 3),
    (2, "3"),
    ("2", "3"),
])
def test_add_string_input_raises_typeerror(a, b):
    """Test adding with string input should raise TypeError."""
    with pytest.raises(TypeError):
        add_numbers(a, b)

@pytest.mark.parametrize("a,b", [
    (None, 3),
    (2, None),
    (None, None),
])
def test_add_none_input_raises_typeerror(a, b):
    """Test adding with None input should raise TypeError."""
    with pytest.raises(TypeError):
        add_numbers(a, b)

@pytest.mark.parametrize("a,b,expected", [
    (True, False, 1),
    (False, False, 0),
    (True, True, 2),
])
def test_add_boolean_values(a, b, expected):
    """Test adding with boolean values (should treat as integers)."""
    assert add_numbers(a, b) == expected
# endregion Test Add Numbers Functionality

# region MCP Integration Tests

# INPUT: None
# OUTPUT: None
def test_mcp_tool_registration_exists_and_valid():
    """Test MCP tool registration exists and is correct."""
    image_gen = importlib.import_module("src.image_generator")
    assert hasattr(image_gen, "MCP_TOOL")
    tool = image_gen.MCP_TOOL
    assert tool.get("name") == "generate_image"
    assert "parameters" in tool
    assert "prompt" in tool["parameters"]

def test_mcp_entry_generate_image_exists_and_callable():
    """Test MCP tool entrypoint exists and is callable."""
    image_gen = importlib.import_module("src.image_generator")
    assert hasattr(image_gen, "mcp_entry_generate_image")
    assert callable(image_gen.mcp_entry_generate_image)

def test_mcp_entry_generate_image_no_api_key_raises(monkeypatch):
    """Test MCP tool entrypoint raises ValueError if no API key."""
    image_gen = importlib.import_module("src.image_generator")
    params = {"prompt": "cat", "model": "imagen3"}
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ValueError):
        image_gen.mcp_entry_generate_image(params)

def test_mcp_entry_generate_image_unknown_model(monkeypatch):
    """Test MCP tool entrypoint raises ValueError for unknown model."""
    image_gen = importlib.import_module("src.image_generator")
    monkeypatch.setenv("GEMINI_API_KEY", "dummy")
    params = {"prompt": "cat", "model": "unknownmodel"}
    with pytest.raises(ValueError):
        image_gen.mcp_entry_generate_image(params)

def test_mcp_entry_generate_image_returns_list(monkeypatch):
    """Test MCP tool entrypoint returns list of file paths (mocked)."""
    image_gen = importlib.import_module("src.image_generator")
    monkeypatch.setenv("GEMINI_API_KEY", "dummy")

    class DummyResp:
        def __init__(self, ok=True, json_data=None, status_code=200, text="OK"):
            self.ok = ok
            self._json = json_data or {}
            self.status_code = status_code
            self.text = text
        def json(self):
            return self._json

    def dummy_post(url, headers=None, json=None):
        if "imagen-3.0" in url:
            return DummyResp(json_data={
                "predictions": [
                    {"bytesBase64": "iVBORw0KGgoAAAANSUhEUgAAAAUA"}
                ]
            })
        elif "gemini-2.0" in url:
            return DummyResp(json_data={
                "candidates": [
                    {"content": {"parts": [
                        {"inline_data": {"mime_type": "image/png", "data": "iVBORw0KGgoAAAANSUhEUgAAAAUA"}}
                    ]}}
                ]
            })
        return DummyResp(ok=False, status_code=400, text="Bad Request")

    monkeypatch.setattr("src.image_generator.requests.post", dummy_post)

    import builtins
    class DummyFile:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def write(self, data): pass

    monkeypatch.setattr(builtins, "open", lambda *a, **k: DummyFile())
    params = {"prompt": "cat", "model": "imagen3"}
    result = image_gen.mcp_entry_generate_image(params)
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0].startswith("generated_image_")

def test_mcp_entry_generate_image_gemini(monkeypatch):
    """Test MCP tool entrypoint with Gemini model returns list (mocked)."""
    image_gen = importlib.import_module("src.image_generator")
    monkeypatch.setenv("GEMINI_API_KEY", "dummy")

    class DummyResp:
        def __init__(self, ok=True, json_data=None, status_code=200, text="OK"):
            self.ok = ok
            self._json = json_data or {}
            self.status_code = status_code
            self.text = text
        def json(self):
            return self._json

    def dummy_post(url, headers=None, json=None):
        return DummyResp(json_data={
            "candidates": [
                {"content": {"parts": [
                    {"inline_data": {"mime_type": "image/png", "data": "iVBORw0KGgoAAAANSUhEUgAAAAUA"}}
                ]}}
            ]
        })

    monkeypatch.setattr("src.image_generator.requests.post", dummy_post)

    import builtins
    class DummyFile:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def write(self, data): pass

    monkeypatch.setattr(builtins, "open", lambda *a, **k: DummyFile())
    params = {"prompt": "dog", "model": "gemini"}
    result = image_gen.mcp_entry_generate_image(params)
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0].startswith("generated_image_")
# endregion MCP Integration Tests