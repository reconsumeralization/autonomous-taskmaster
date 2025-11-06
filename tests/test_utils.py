# region Smoke test for utils.py
# INPUT: None
# OUTPUT: None (asserts import)
def test_import_utils():
    import sys
    sys.path.append('autotype_mcp_server/src')
    import utils
    assert utils is not None
# endregion 

import pytest
import os
import json
import logging
from unittest.mock import patch, mock_open
import sys

# Ensure src is in path - This is now handled by conftest.py
# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

# Correct import using the package structure
from autotype_mcp_server.src.utils import setup_logging, load_json_file, save_json_file, move_file, load_yaml_from_string # Import the function to test

# ================== Test load_json_file ==================

@pytest.fixture
def temp_json_file(tmp_path):
    """Pytest fixture to create a temporary JSON file."""
    def _create_file(content: dict, filename: str = "test.json"):
        file_path = tmp_path / filename
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(content, f)
        return file_path
    return _create_file

def test_load_json_file_success(temp_json_file):
    """Test loading a valid JSON file."""
    test_data = {"key": "value", "number": 123}
    file_path = temp_json_file(test_data)
    loaded_data = load_json_file(str(file_path), default_value=None)
    assert loaded_data == test_data

def test_load_json_file_not_found():
    """Test loading a non-existent file returns default value."""
    default = {"default": True}
    loaded_data = load_json_file("non_existent_file.json", default_value=default)
    assert loaded_data == default

def test_load_json_file_invalid_json(tmp_path):
    """Test loading an invalid JSON file returns default value."""
    file_path = tmp_path / "invalid.json"
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write("this is not json{")
    default = [1, 2, 3]
    loaded_data = load_json_file(str(file_path), default_value=default)
    assert loaded_data == default

def test_load_json_file_empty_file(tmp_path):
    """Test loading an empty file (which is invalid JSON) returns default."""
    file_path = tmp_path / "empty.json"
    file_path.touch()
    default = "empty_default"
    loaded_data = load_json_file(str(file_path), default_value=default)
    assert loaded_data == default

def test_load_json_file_os_error():
    """Test handling of unexpected OS errors during file open."""
    default = {"error": True}
    # Mock open to raise an OSError
    with patch("builtins.open", mock_open()) as mocked_open:
        mocked_open.side_effect = OSError("Permission denied")
        loaded_data = load_json_file("any_file.json", default_value=default)
    assert loaded_data == default

# ================== Test save_json_file ==================

def test_save_json_file_success(tmp_path):
    """Test saving valid data to a JSON file."""
    test_data = {"save": "me", "list": [1, "a", None]}
    file_path = tmp_path / "save_test.json"
    
    success = save_json_file(test_data, str(file_path))
    assert success is True
    assert file_path.exists()
    
    # Verify content
    with open(file_path, 'r', encoding='utf-8') as f:
        loaded_data = json.load(f)
    assert loaded_data == test_data

def test_save_json_creates_directory(tmp_path):
    """Test that save_json_file creates the target directory if it doesn't exist."""
    test_data = {"nested": "data"}
    nested_dir = tmp_path / "nested_dir"
    file_path = nested_dir / "save_nested.json"
    
    assert not nested_dir.exists()
    success = save_json_file(test_data, str(file_path))
    assert success is True
    assert nested_dir.exists()
    assert nested_dir.is_dir()
    assert file_path.exists()

def test_save_json_file_type_error():
    """Test saving non-serializable data returns False."""
    # A set is not directly JSON serializable
    non_serializable_data = {1, 2, 3}
    file_path = "save_type_error.json" # Doesn't need to exist
    
    success = save_json_file(non_serializable_data, file_path)
    assert success is False
    # Ideally, check logs for TypeError, but that's harder in tests

def test_save_json_file_os_error():
    """Test handling of OS errors during file writing."""
    test_data = {"data": "ok"}
    # Mock open to raise an OSError on write
    with patch("builtins.open", mock_open()) as mocked_open:
        mocked_open.side_effect = OSError("Disk full")
        success = save_json_file(test_data, "os_error_save.json")
    assert success is False

# ================== Test move_file ==================

@pytest.fixture
def temp_files(tmp_path):
    """Pytest fixture to create temporary source files/dirs for move tests."""
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    file1 = source_dir / "file1.txt"
    file1.write_text("content1")
    file2 = source_dir / "file2.log"
    file2.write_text("content2")
    
    dest_dir = tmp_path / "destination"
    # dest_dir is NOT created initially
    
    return {"source_dir": source_dir, "dest_dir": dest_dir, "file1": file1, "file2": file2}

def test_move_file_success(temp_files):
    """Test successfully moving a file."""
    source_file = temp_files["file1"]
    dest_path = temp_files["dest_dir"] / source_file.name
    
    assert source_file.exists()
    assert not temp_files["dest_dir"].exists()
    assert not dest_path.exists()
    
    success = move_file(str(source_file), str(dest_path))
    
    assert success is True
    assert not source_file.exists() # Original is gone
    assert temp_files["dest_dir"].exists() # Dest dir created
    assert dest_path.exists()
    assert dest_path.read_text() == "content1"

def test_move_file_to_directory(temp_files):
    """Test moving a file *into* an existing directory."""
    source_file = temp_files["file2"]
    dest_dir = temp_files["dest_dir"]
    dest_dir.mkdir() # Create destination directory beforehand
    final_dest_path = dest_dir / source_file.name
    
    assert source_file.exists()
    assert dest_dir.exists()
    assert not final_dest_path.exists()
    
    # Pass the destination directory path to move_file
    success = move_file(str(source_file), str(dest_dir))
    
    assert success is True
    assert not source_file.exists()
    assert final_dest_path.exists()
    assert final_dest_path.read_text() == "content2"

def test_move_file_source_not_found(temp_files):
    """Test moving a non-existent source file returns False."""
    non_existent_source = temp_files["source_dir"] / "nope.txt"
    dest_path = temp_files["dest_dir"] / "nope.txt"
    
    assert not non_existent_source.exists()
    success = move_file(str(non_existent_source), str(dest_path))
    assert success is False
    assert not temp_files["dest_dir"].exists() # Dest dir not created if source fails

def test_move_file_os_error(temp_files):
    """Test handling OS errors during the move operation."""
    source_file = temp_files["file1"]
    dest_path = temp_files["dest_dir"] / source_file.name
    
    # Mock shutil.move to raise an error
    with patch("shutil.move", side_effect=OSError("Permission denied")):
        success = move_file(str(source_file), str(dest_path))
        
    assert success is False
    assert source_file.exists() # Source should still exist if move failed
    # Destination dir might exist if created before shutil.move error, check specifically
    # assert not temp_files["dest_dir"].exists() # This might fail depending on timing

# ================== Test load_yaml_from_string ==================

def test_load_yaml_from_string_success():
    """Test loading valid YAML from a string."""
    yaml_string = "key: value\nnumber: 123\nlist:\n  - item1\n  - item2"
    expected_data = {"key": "value", "number": 123, "list": ["item1", "item2"]}
    loaded_data = load_yaml_from_string(yaml_string, default_value=None)
    assert loaded_data == expected_data

def test_load_yaml_from_string_invalid():
    """Test loading invalid YAML string returns default."""
    invalid_yaml = "key: value\n  bad_indent: fail"
    default = {"default": True}
    loaded_data = load_yaml_from_string(invalid_yaml, default_value=default)
    assert loaded_data == default

def test_load_yaml_from_string_empty():
    """Test loading empty string (valid YAML, loads as None)."""
    loaded_data = load_yaml_from_string("", default_value="DEFAULT")
    # Empty string is valid YAML and parses to None
    assert loaded_data is None 

def test_load_yaml_from_string_not_dict():
    """Test loading valid YAML that isn't a dictionary."""
    yaml_string = "- item1\n- item2" # A list
    expected_data = ["item1", "item2"]
    loaded_data = load_yaml_from_string(yaml_string, default_value=None)
    assert loaded_data == expected_data

# TODO: Add tests for save_yaml_file
# TODO: Add tests for setup_logging (might be complex)
# TODO: Add tests for send_desktop_notification (might need mocking) 