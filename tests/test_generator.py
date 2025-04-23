# tests/test_generator.py
"""
Unit tests for the CoverLetterGenerator class.

Uses pytest and pytest-mock to test the generator functionality,
mocking the OpenAI API client and its responses.
"""

import pytest
from unittest.mock import patch, MagicMock

# Assuming your project structure allows this import:
from src.config import Config
from src.generator.cover_letter import CoverLetterGenerator
# Import JobListing if CoverLetterGenerator expects it as input type
# from src.fetcher.linkedin_fetcher import JobListing # Or from models.py

# --- Fixtures ---

@pytest.fixture
def mock_config_with_api_key() -> Config:
    """Provides a mock Config object with an OpenAI API key."""
    mock = MagicMock(spec=Config)
    mock.OPENAI_API_KEY = "fake-api-key"
    # Add other necessary config attributes if needed
    return mock

@pytest.fixture
def mock_config_without_api_key() -> Config:
    """Provides a mock Config object without an OpenAI API key."""
    mock = MagicMock(spec=Config)
    mock.OPENAI_API_KEY = None
    return mock

@pytest.fixture
def mock_job_details() -> MagicMock:
    """Provides mock job details."""
    job = MagicMock()
    job.title = "Software Engineer"
    job.company = "TestCorp"
    job.description = "Looking for a skilled engineer."
    return job

@pytest.fixture
def mock_openai_client() -> MagicMock:
    """Provides a mock OpenAI client object."""
    client_mock = MagicMock()
    # Mock the response structure based on openai library v1.0+
    completion_mock = MagicMock()
    message_mock = MagicMock()
    message_mock.content = "This is a generated cover letter."
    completion_mock.choices = [MagicMock(message=message_mock)]
    client_mock.chat.completions.create.return_value = completion_mock
    return client_mock

# --- Test Cases ---

@patch('src.generator.cover_letter.openai.OpenAI') # Patch the client class
def test_generator_initialization_with_key(
    mock_openai_constructor: MagicMock,
    mock_config_with_api_key: Config,
    mock_openai_client: MagicMock
) -> None:
    """Tests generator initialization when API key is present."""
    mock_openai_constructor.return_value = mock_openai_client # Ensure constructor returns our mock client
    generator = CoverLetterGenerator(config=mock_config_with_api_key)

    assert generator.config == mock_config_with_api_key
    assert generator.client is not None
    mock_openai_constructor.assert_called_once_with(api_key="fake-api-key")

@patch('src.generator.cover_letter.openai.OpenAI')
def test_generator_initialization_without_key(
    mock_openai_constructor: MagicMock,
    mock_config_without_api_key: Config
) -> None:
    """Tests generator initialization when API key is missing."""
    generator = CoverLetterGenerator(config=mock_config_without_api_key)
    assert generator.config == mock_config_without_api_key
    assert generator.client is None
    mock_openai_constructor.assert_not_called() # Client shouldn't be instantiated

@patch('src.generator.cover_letter.openai.OpenAI')
def test_generate_success(
    mock_openai_constructor: MagicMock,
    mock_config_with_api_key: Config,
    mock_openai_client: MagicMock,
    mock_job_details: MagicMock
) -> None:
    """Tests successful cover letter generation."""
    mock_openai_constructor.return_value = mock_openai_client
    generator = CoverLetterGenerator(config=mock_config_with_api_key)

    cover_letter = generator.generate(job_details=mock_job_details)

    assert cover_letter == "This is a generated cover letter."
    mock_openai_client.chat.completions.create.assert_called_once()
    # Optionally, inspect the prompt passed to the create call:
    call_args, call_kwargs = mock_openai_client.chat.completions.create.call_args
    assert "Write a personalized cover letter" in call_kwargs['messages'][1]['content']
    assert mock_job_details.title in call_kwargs['messages'][1]['content']

@patch('src.generator.cover_letter.openai.OpenAI')
def test_generate_without_api_key(
    mock_openai_constructor: MagicMock,
    mock_config_without_api_key: Config,
    mock_job_details: MagicMock
) -> None:
    """Tests generate() when the client wasn't initialized (no API key)."""
    generator = CoverLetterGenerator(config=mock_config_without_api_key)
    cover_letter = generator.generate(job_details=mock_job_details)

    assert cover_letter is None
    mock_openai_constructor.assert_not_called() # Constructor wasn't called
    # Ensure the API call method wasn't called either
    # (Accessing generator.client.chat... would raise AttributeError if client is None)

@patch('src.generator.cover_letter.openai.OpenAI')
def test_generate_api_error(
    mock_openai_constructor: MagicMock,
    mock_config_with_api_key: Config,
    mock_openai_client: MagicMock,
    mock_job_details: MagicMock
) -> None:
    """Tests cover letter generation when the OpenAI API call fails."""
    # Import the specific exception class expected
    from openai import APIError

    mock_openai_constructor.return_value = mock_openai_client
    # Configure the mock client's method to raise an APIError
    mock_openai_client.chat.completions.create.side_effect = APIError(
        "API connection failed", request=MagicMock(), body=None
    )

    generator = CoverLetterGenerator(config=mock_config_with_api_key)
    cover_letter = generator.generate(job_details=mock_job_details)

    assert cover_letter is None
    mock_openai_client.chat.completions.create.assert_called_once() # Ensure it was called

# Add more tests:
# - Test generation with user_profile data included in the prompt.
# - Test edge cases like empty job details.
# - Test different OpenAI API response scenarios (e.g., no choices returned).