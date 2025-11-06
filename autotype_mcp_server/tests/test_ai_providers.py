import os
import pytest
from unittest.mock import patch, MagicMock
# Assuming ai_providers is importable from src (adjust path if needed)
from src import ai_providers 
import requests # <<< ADDED IMPORT
# TODO: Figure out correct import path based on pytest execution context - RESOLVED

def test_placeholder_ai(): # Keep one placeholder for now
    pass 

# Example for extract_code (simpler case)
def test_extract_code_finds_blocks():
    text_with_code = """
    Some text here
    ```python
    print("Hello")
    ```
    More text.
    ```javascript
    console.log("Hi");
    ```
    """
    extracted = ai_providers.extract_code(text_with_code)
    assert len(extracted) == 2
    assert extracted[0]['language'] == 'python'
    # Ensure newline is preserved if present
    assert extracted[0]['code'] == 'print("Hello")' 
    assert extracted[1]['language'] == 'javascript'
    assert extracted[1]['code'] == 'console.log("Hi");'
    # assert True # Placeholder - REMOVED

def test_extract_code_no_blocks():
    text_without_code = "Just plain text."
    extracted = ai_providers.extract_code(text_without_code)
    assert extracted == []
    # assert True # Placeholder - REMOVED

def test_extract_code_no_language_tag():
    """Tests code blocks with no language specified."""
    text = "```\nNo language here\n```"
    extracted = ai_providers.extract_code(text)
    assert len(extracted) == 1
    assert extracted[0]['language'] == '' # Defaults to empty string
    assert extracted[0]['code'] == 'No language here'

def test_extract_code_mixed_case_language():
    """Tests if language tag is lowercased."""
    text = "```PyThOn\ncode\n```"
    extracted = ai_providers.extract_code(text)
    assert len(extracted) == 1
    assert extracted[0]['language'] == 'python'
    assert extracted[0]['code'] == 'code'

def test_extract_code_empty_block():
    """Tests an empty code block."""
    text = "```python\n```"
    extracted = ai_providers.extract_code(text)
    assert len(extracted) == 1
    assert extracted[0]['language'] == 'python'
    assert extracted[0]['code'] == '' # Empty code string

def test_extract_code_adjacent_blocks():
    """Tests code blocks immediately following each other."""
    text = "```python\nblock1\n``````javascript\nblock2\n```"
    extracted = ai_providers.extract_code(text)
    assert len(extracted) == 2
    assert extracted[0]['language'] == 'python'
    assert extracted[0]['code'] == 'block1'
    assert extracted[1]['language'] == 'javascript'
    assert extracted[1]['code'] == 'block2'

# Example for ai_generate_code (requires mocking external API calls)
# @patch('src.ai_providers.some_llm_client') # Patch the actual client used
# def test_ai_generate_code_mocked(mock_llm_client):
# ... rest of placeholder ... 

@patch('src.ai_providers.requests.post')
@patch('src.ai_providers.os.environ.get')
def test_ai_generate_code_success(mock_os_get, mock_requests_post):
    """Test successful code generation path with mocked API call."""
    # --- Mock Setup ---
    # Mock os.environ.get to return dummy values
    mock_os_get.side_effect = lambda key, default=None: {
        "XAI_API_KEY": "dummy_key",
        "XAI_API_URL": "http://dummy.url/api"
    }.get(key, default)

    # Mock the response object from requests.post
    mock_response = MagicMock()
    mock_response.status_code = 200
    # Define the .json() return value mimicking the API structure
    mock_api_content = "```python\n# Mocked code\nprint('Success!')\n```"
    mock_response.json.return_value = {
        "choices": [
            {"message": {"content": mock_api_content}}
        ]
    }
    # Make requests.post return our mock response
    mock_requests_post.return_value = mock_response

    # --- Test Data ---
    test_desc = "Generate simple success code"
    test_config = {
        "GROK_API_KEY_ENV": "XAI_API_KEY",
        "GROK_API_URL_ENV": "XAI_API_URL",
        "AI_MODEL": "test-model",
        "AI_MAX_TOKENS": 100,
        "AI_TEMPERATURE": 0.5,
        "AI_TIMEOUT": 30
    }
    expected_code = "# Mocked code\nprint('Success!')"

    # --- Call Function ---
    generated_code = ai_providers.ai_generate_code(test_desc, None, test_config)

    # --- Assertions ---
    mock_os_get.assert_any_call("XAI_API_KEY") # Check it tries to get the key
    mock_os_get.assert_any_call("XAI_API_URL") # Check it tries to get the URL
    mock_requests_post.assert_called_once() # Check API was called
    assert generated_code == expected_code # Check extracted code is correct
    mock_response.raise_for_status.assert_called_once() # Ensure status check was performed

# === Failure Tests for ai_generate_code ===

@patch('src.ai_providers.os.environ')
def test_ai_generate_code_missing_api_key(mock_environ):
    """Test ai_generate_code when XAI_API_KEY is not set."""
    # Simulate os.environ.get returning None for the key
    mock_environ.get.side_effect = lambda key, default=None: {
        "XAI_API_URL": "http://fake-url.com"
    }.get(key, default) # Return URL, but None for KEY
    
    config = {}
    result = ai_providers.ai_generate_code("Generate something", None, config)
    
    assert result.startswith("# ERROR: API Key environment variable") 
    assert "'XAI_API_KEY' not set" in result
    mock_environ.get.assert_any_call("XAI_API_KEY") 

@patch('src.ai_providers.os.environ')
def test_ai_generate_code_missing_api_url(mock_environ):
    """Test ai_generate_code when XAI_API_URL is not set."""
    # Simulate os.environ.get returning None for the URL
    mock_environ.get.side_effect = lambda key, default=None: {
        "XAI_API_KEY": "fake-key"
    }.get(key, default) # Return Key, but None for URL
    
    config = {}
    result = ai_providers.ai_generate_code("Generate something", None, config)
    
    assert result.startswith("# ERROR: API URL environment variable")
    assert "'XAI_API_URL' not set" in result
    mock_environ.get.assert_any_call("XAI_API_URL") 

@patch('src.ai_providers.requests.post')
@patch('src.ai_providers.os.environ')
def test_ai_generate_code_request_exception(mock_environ, mock_requests_post):
    """Test ai_generate_code when requests.post raises an exception."""
    mock_environ.get.side_effect = lambda key, default=None: {
        "XAI_API_KEY": "fake-key",
        "XAI_API_URL": "http://fake-url.com"
    }.get(key, default)
    mock_requests_post.side_effect = requests.exceptions.RequestException("Connection failed")
    
    config = {}
    result = ai_providers.ai_generate_code("Generate something", None, config)
    
    assert result.startswith("# ERROR: AI request failed. Status: N/A. Error:") 
    mock_requests_post.assert_called_once()

@patch('src.ai_providers.requests.post')
@patch('src.ai_providers.os.environ')
def test_ai_generate_code_api_error_status(mock_environ, mock_requests_post):
    """Test ai_generate_code when the API returns a non-200 status code."""
    mock_environ.get.side_effect = lambda key, default=None: {
        "XAI_API_KEY": "fake-key",
        "XAI_API_URL": "http://fake-url.com"
    }.get(key, default)
    
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("Unauthorized")
    mock_requests_post.return_value = mock_response
    
    config = {}
    result = ai_providers.ai_generate_code("Generate something", None, config)
    
    assert result.startswith("# ERROR: AI request failed. Status: N/A. Error:") 
    mock_requests_post.assert_called_once()

@patch('src.ai_providers.requests.post')
@patch('src.ai_providers.os.environ')
def test_ai_generate_code_malformed_response(mock_environ, mock_requests_post):
    """Test ai_generate_code with a 200 OK but malformed/empty JSON response."""
    mock_environ.get.side_effect = lambda key, default=None: {
        "XAI_API_KEY": "fake-key",
        "XAI_API_URL": "http://fake-url.com"
    }.get(key, default)
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status.return_value = None # No exception on 200
    # Simulate response JSON that is empty or lacks the expected keys
    mock_response.json.return_value = {}
    # Or: mock_response.json.return_value = {"choices": []} 
    # Or: mock_response.json.return_value = {"choices": [{"message": {}}]}
    mock_requests_post.return_value = mock_response
    
    config = {}
    result = ai_providers.ai_generate_code("Generate something", None, config)
    
    assert result.startswith("# ERROR: AI response from") 
    assert "missing expected content" in result 
    mock_requests_post.assert_called_once()
    mock_response.raise_for_status.assert_called_once()
    mock_response.json.assert_called_once()

@patch('src.ai_providers.requests.post')
@patch('src.ai_providers.os.environ')
def test_ai_generate_code_no_code_blocks(mock_environ, mock_requests_post):
    """Test ai_generate_code when the AI response has no code blocks."""
    mock_environ.get.side_effect = lambda key, default=None: {
        "XAI_API_KEY": "fake-key",
        "XAI_API_URL": "http://fake-url.com"
    }.get(key, default)

    # Simulate a valid API response structure, but content has no ``` blocks
    ai_response_content = "This is a text response without any code."
    mock_response_data = {
        "choices": [
            {"message": {"content": ai_response_content}}
        ]
    }
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = mock_response_data
    mock_requests_post.return_value = mock_response

    config = {}
    result = ai_providers.ai_generate_code("Generate something", None, config)

    assert result.startswith("# ERROR: AI response contained no recognizable code blocks")
    mock_requests_post.assert_called_once()
    mock_response.raise_for_status.assert_called_once()
    mock_response.json.assert_called_once()