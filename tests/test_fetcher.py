# tests/test_fetcher.py
"""
Unit tests for the LinkedInFetcher class.

Uses pytest and pytest-mock to test the fetcher functionality,
mocking external dependencies like Selenium WebDriver.
"""

import pytest
from unittest.mock import patch, MagicMock # For mocking WebDriver

# Assuming your project structure allows this import:
from src.config import Config
from src.fetcher.linkedin_fetcher import LinkedInFetcher, JobListing

# --- Fixtures ---

@pytest.fixture
def mock_config() -> Config:
    """Provides a mock Config object for tests."""
    mock = MagicMock(spec=Config)
    mock.LINKEDIN_EMAIL = "test@example.com"
    mock.LINKEDIN_PASSWORD = "password"
    mock.DATABASE_URL = "sqlite:///:memory:" # Example, not directly used by fetcher
    mock.LOG_LEVEL = "DEBUG"
    return mock

@pytest.fixture
def mock_webdriver() -> MagicMock:
    """Provides a mock Selenium WebDriver object."""
    driver = MagicMock()
    # Mock common methods used in LinkedInFetcher
    driver.get = MagicMock()
    driver.find_element = MagicMock()
    driver.find_elements = MagicMock()
    driver.quit = MagicMock()
    # Mock WebDriverWait and expected_conditions if needed for more complex tests
    return driver

# --- Test Cases ---

def test_linkedin_fetcher_initialization(mock_config: Config) -> None:
    """Tests if LinkedInFetcher initializes correctly."""
    fetcher = LinkedInFetcher(config=mock_config)
    assert fetcher.config == mock_config
    assert fetcher.driver is None # Driver shouldn't be initialized yet
    assert fetcher.config.LINKEDIN_EMAIL == "test@example.com"

def test_linkedin_fetcher_initialization_missing_credentials() -> None:
    """Tests if LinkedInFetcher raises ValueError if credentials are missing."""
    config_no_creds = MagicMock(spec=Config)
    config_no_creds.LINKEDIN_EMAIL = None
    config_no_creds.LINKEDIN_PASSWORD = None
    with pytest.raises(ValueError, match="LinkedIn email and password must be set"):
        LinkedInFetcher(config=config_no_creds)

# Use patch to mock WebDriver initialization and methods
@patch('src.fetcher.linkedin_fetcher.webdriver.Chrome')
@patch('src.fetcher.linkedin_fetcher.ChromeDriverManager')
@patch('src.fetcher.linkedin_fetcher.WebDriverWait') # Mock WebDriverWait if used in login/search
def test_linkedin_fetcher_login_success(
    mock_wait: MagicMock,
    mock_driver_manager: MagicMock,
    mock_chrome: MagicMock,
    mock_config: Config,
    mock_webdriver: MagicMock
) -> None:
    """
    Tests the login sequence with mocked WebDriver interactions.
    Assumes login is successful.
    """
    # Configure mocks
    mock_driver_manager.return_value.install.return_value = "/path/to/chromedriver"
    mock_chrome.return_value = mock_webdriver # Return our pre-configured mock driver

    # Mock WebDriverWait().until() to return mock elements
    mock_email_field = MagicMock()
    mock_password_field = MagicMock()
    mock_nav_bar = MagicMock() # Element indicating successful login

    # Configure WebDriverWait side effects or return values
    # This simulates finding elements needed for login
    mock_wait.return_value.until.side_effect = [
        mock_email_field,     # Find username field
        mock_password_field,  # Find password field
        mock_nav_bar          # Find element confirming login success
    ]

    fetcher = LinkedInFetcher(config=mock_config)

    # Patch time.sleep to speed up test
    with patch('src.fetcher.linkedin_fetcher.time.sleep', return_value=None):
         # Call _initialize_driver and _login which are called internally by search_jobs
         # Or test them directly if needed (making them non-private might help testing)
         try:
             fetcher._initialize_driver() # Call protected method for testing
             fetcher._login() # Call protected method for testing
         except ConnectionError:
             pytest.fail("Login raised ConnectionError unexpectedly.")
         except Exception as e:
             pytest.fail(f"Login raised unexpected exception: {e}")


    # Assertions
    mock_webdriver.get.assert_called_with("https://www.linkedin.com/login")
    mock_email_field.send_keys.assert_called_with(mock_config.LINKEDIN_EMAIL)
    mock_password_field.send_keys.assert_any_call(mock_config.LINKEDIN_PASSWORD)
    # Check if Keys.RETURN was sent (usually the last call to send_keys on password field)
    mock_password_field.send_keys.assert_called_with('\ue007') # Keys.RETURN value

    assert fetcher.driver is not None # Driver should be assigned

# Add more tests:
# - test_linkedin_fetcher_login_failure (mocking exceptions during find_element or timeout)
# - test_search_jobs_success (mocking find_elements to return mock job elements)
# - test_search_jobs_no_results
# - test_search_jobs_api_error (if applicable)
# - test_close_driver

# Example test for closing the driver
@patch('src.fetcher.linkedin_fetcher.webdriver.Chrome')
@patch('src.fetcher.linkedin_fetcher.ChromeDriverManager')
def test_linkedin_fetcher_close(
    mock_driver_manager: MagicMock,
    mock_chrome: MagicMock,
    mock_config: Config,
    mock_webdriver: MagicMock
) -> None:
    """Tests the close method."""
    mock_driver_manager.return_value.install.return_value = "/path/to/chromedriver"
    mock_chrome.return_value = mock_webdriver
    fetcher = LinkedInFetcher(config=mock_config)
    fetcher.driver = mock_webdriver # Manually assign mock driver

    fetcher.close()

    mock_webdriver.quit.assert_called_once()
    assert fetcher.driver is None