"""
LinkedIn job search and data fetching module.

Provides functionality to interact with LinkedIn, search for jobs,
extract job details, and handle LinkedIn's rate limiting.
"""

import time
import logging
import re
import random
from typing import List, Dict, Any, Optional

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import NoSuchElementException, TimeoutException, ElementNotInteractableException, StaleElementReferenceException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains

from ..config import Config


def human_delay(min_seconds=0.5, max_seconds=1.5):
    """Add a randomized delay to simulate human interaction"""
    delay = random.uniform(min_seconds, max_seconds)
    time.sleep(delay)
    return delay


class JobListing:
    """Represents a job listing found on LinkedIn."""
    def __init__(self, title: str, company: str, location: str, url: str, description: Optional[str] = None, 
                 linkedin_job_id: Optional[str] = None, already_applied: bool = False, 
                 recruiter_name: Optional[str] = None, recruiter_title: Optional[str] = None):
        self.title = title
        self.company = company
        self.location = location
        self.url = url
        self.description = description
        self.linkedin_job_id = linkedin_job_id
        self.already_applied = already_applied
        self.recruiter_name = recruiter_name
        self.recruiter_title = recruiter_title
    
    def __repr__(self) -> str:
        applied_status = " (APPLIED)" if self.already_applied else ""
        return f"JobListing(title='{self.title}', company='{self.company}', url='{self.url}'{applied_status})"


class LinkedInFetcher:
    """
    Handles searching and fetching job listings from LinkedIn using Selenium.
    Includes anti-detection measures and rate limiting management.
    """
    BASE_URL = "https://www.linkedin.com"
    JOBS_URL = f"{BASE_URL}/jobs/search/"
    
    def __init__(self, config: Config):
        """
        Initialize the LinkedIn fetcher with configuration.
        
        Args:
            config: Application configuration containing LinkedIn credentials
        """
        self.config = config
        self.driver: Optional[webdriver.Chrome] = None
        self.logger = logging.getLogger(__name__)
        self.retry_count = 0
        self.max_retries = 5
        self.session_job_count = 0
        self.last_request_time = 0
        
        if not self.config.LINKEDIN_EMAIL or not self.config.LINKEDIN_PASSWORD:
            raise ValueError("LinkedIn credentials missing in configuration.")
    
    def _initialize_driver(self) -> None:
        """Initialize and configure the Selenium WebDriver with anti-detection measures."""
        self.logger.info("Initializing WebDriver...")
        options = webdriver.ChromeOptions()
        options.add_argument("--start-maximized")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        
        # Anti-detection configurations
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        
        # Random user agent to appear more human-like
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 OPR/107.0.0.0",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Mozilla/5.0 (iPad; CPU OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3.1 Mobile/15E148 Safari/604.1"
        ]
        options.add_argument(f"user-agent={random.choice(user_agents)}")
        
        # Browser preferences for evasion
        prefs = {
            "profile.default_content_setting_values.notifications": 2,
            "credentials_enable_service": False,
            "profile.password_manager_enabled": False,
            "useAutomationExtension": False,
            "excludeSwitches": ["enable-automation"]
        }
        options.add_experimental_option("prefs", prefs)
        
        try:
            service = ChromeService(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)
            
            # Execute JavaScript to hide automation
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            # Modify additional properties to evade detection
            self.driver.execute_script("""
                delete navigator.__proto__.webdriver;
                navigator.permissions.query = (parameters) => Promise.resolve({state: 'prompt'});
            """)
            
            self.logger.info("WebDriver initialized.")
            self.session_job_count = 0
            self.last_request_time = time.time()
        except Exception as e:
            self.logger.error(f"WebDriver initialization failed: {e}", exc_info=True)
            raise
    
    def _login(self) -> None:
        """Log in to LinkedIn using the configured credentials."""
        if not self.driver:
            self.logger.error("Driver not initialized.")
            raise RuntimeError("WebDriver not available.")
        
        self.logger.info("Navigating to login page...")
        self.driver.get(f"{self.BASE_URL}/login")
        human_delay(2, 4)
        
        try:
            email_field = WebDriverWait(self.driver, 15).until(
                EC.visibility_of_element_located((By.ID, "username"))
            )
            
            # Type email with human-like delays
            for char in self.config.LINKEDIN_EMAIL:
                email_field.send_keys(char)
                human_delay(0.05, 0.15)
            
            password_field = WebDriverWait(self.driver, 15).until(
                EC.visibility_of_element_located((By.ID, "password"))
            )
            
            # Type password with human-like delays
            for char in self.config.LINKEDIN_PASSWORD:
                password_field.send_keys(char)
                human_delay(0.05, 0.15)
            
            human_delay(0.5, 1.5)
            
            login_button_selector = "button[type='submit'][aria-label*='Sign in'], button[data-litms-control-urn*='login-submit']"
            login_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, login_button_selector))
            )
            login_button.click()
            self.logger.info("Login submitted.")
            
            logged_in_indicator_selector = "#global-nav, img[id*='profile-nav-item']"
            WebDriverWait(self.driver, 25).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, logged_in_indicator_selector))
            )
            self.logger.info("Login successful.")
            human_delay(2, 4)
        except TimeoutException as e:
            self.logger.error("Login timeout.", exc_info=True)
            self.driver.save_screenshot("error_login_timeout.png")
            raise ConnectionError("Login failed (Timeout).")
        except Exception as e:
            self.logger.error(f"Unexpected login error: {e}", exc_info=True)
            self.driver.save_screenshot("error_login_unexpected.png")
            raise

    def _apply_time_filter(self, filter_option: str = "week") -> bool:
        """
        Apply a time filter to job search results.
        
        Args:
            filter_option: Time filter option ('week', 'day', 'month')
            
        Returns:
            bool: True if filter was successfully applied
        """
        self.logger.info(f"Applying time filter: {filter_option}")
        
        # Map filter options to LinkedIn values
        filter_values = {
            "week": "r604800",    # Last week (7 days)
            "day": "r86400",      # Last 24 hours
            "month": "r2592000"   # Last month
        }
        
        filter_id = filter_values.get(filter_option, "r604800")
        
        try:
            # Find and click the date filter button
            time_filter_button_selectors = [
                "button[id='searchFilter_timePostedRange']", 
                "button[aria-label*='Fecha de publicación']",
                "button[aria-label*='Date posted']",
                "button.search-reusables__filter-binary-toggle:has(span:contains('Date posted'))",
                "button.search-reusables__filter-binary-toggle:has(span:contains('Fecha'))"
            ]
            
            time_filter_button = None
            for selector in time_filter_button_selectors:
                try:
                    if ":has" in selector or ":contains" in selector:
                        text_to_search = ""
                        if ":contains" in selector:
                            text_to_search = selector.split(":contains('")[1].split("')")[0]
                        
                        buttons = self.driver.find_elements(By.TAG_NAME, "button")
                        for btn in buttons:
                            try:
                                span = btn.find_element(By.TAG_NAME, "span")
                                if text_to_search.lower() in span.text.lower():
                                    time_filter_button = btn
                                    break
                            except:
                                continue
                    else:
                        time_filter_button = WebDriverWait(self.driver, 8).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                        )
                    
                    if time_filter_button and time_filter_button.is_displayed():
                        break
                except:
                    continue
            
            if not time_filter_button:
                # Try alternative XPath approach
                try:
                    xpath_patterns = [
                        "//button[.//span[contains(text(), 'Date posted')]]",
                        "//button[.//span[contains(text(), 'Fecha')]]",
                        "//button[contains(@aria-label, 'posted') or contains(@aria-label, 'Fecha')]"
                    ]
                    
                    for xpath in xpath_patterns:
                        try:
                            time_filter_button = WebDriverWait(self.driver, 5).until(
                                EC.element_to_be_clickable((By.XPATH, xpath))
                            )
                            if time_filter_button:
                                self.logger.info(f"Date filter button found with XPath: {xpath}")
                                break
                        except:
                            continue
                except Exception as e:
                    self.logger.warning(f"Error in alternative filter search: {e}")
            
            if not time_filter_button:
                self.logger.warning("Date filter button not found. Continuing without filter.")
                return False
                
            self.logger.info("Date filter button found. Clicking...")
            
            # Ensure button is visible
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", time_filter_button)
            human_delay(0.5, 1)
            
            # Try different click methods
            try:
                time_filter_button.click()
            except Exception as e:
                self.logger.warning(f"Normal click failed: {e}, trying JavaScript")
                self.driver.execute_script("arguments[0].click();", time_filter_button)
                
            human_delay(1, 2)  # Wait for dropdown to open
            
            # Select the correct option
            option_found = False
            
            # STRATEGY 1: Find by specific ID
            try:
                time_option_selector = f"input#timePostedRange-{filter_id}"
                time_option = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, time_option_selector))
                )
                time_option.click()
                option_found = True
                self.logger.info(f"Filter option selected by ID: {filter_id}")
            except:
                self.logger.info("Could not select by ID. Trying by text...")
            
            # STRATEGY 2: Find by text
            if not option_found:
                filter_texts = {
                    "week": ["Semana pasada", "Past week", "Last week", "última semana", "Última semana", "Past 7 days"],
                    "day": ["Últimas 24 horas", "Past 24 hours", "Last 24 hours", "últimas 24 horas"],
                    "month": ["Último mes", "Past month", "Last month", "último mes"]
                }
                
                texts_to_try = filter_texts.get(filter_option, ["Semana pasada", "Past week"])
                
                for text in texts_to_try:
                    try:
                        xpath = f"//label[contains(., '{text}')]"
                        option_label = WebDriverWait(self.driver, 3).until(
                            EC.element_to_be_clickable((By.XPATH, xpath))
                        )
                        option_label.click()
                        option_found = True
                        self.logger.info(f"Filter selected by text: '{text}'")
                        break
                    except:
                        try:
                            xpath = f"//*[contains(text(), '{text}')]"
                            text_element = WebDriverWait(self.driver, 2).until(
                                EC.element_to_be_clickable((By.XPATH, xpath))
                            )
                            text_element.click()
                            option_found = True
                            self.logger.info(f"Filter selected by generic text: '{text}'")
                            break
                        except:
                            continue
            
            # STRATEGY 3: Find any selectable element
            if not option_found:
                try:
                    self.logger.info("Trying strategy 3: find selectable elements")
                    selectable_elements = self.driver.find_elements(By.CSS_SELECTOR, 
                                                                   "input[type='radio'], li[role='radio'], li[role='option'], li.search-reusables__collection-values-item")
                    
                    matching_element = None
                    texts_to_match = filter_texts.get(filter_option, ["week", "semana"])
                    
                    for element in selectable_elements:
                        try:
                            element_text = element.text.lower() if hasattr(element, 'text') else ""
                            if not element_text:
                                element_text = element.get_attribute("aria-label") or ""
                                element_text = element_text.lower()
                                
                            if not element_text and element.tag_name == "li":
                                try:
                                    span = element.find_element(By.TAG_NAME, "span")
                                    element_text = span.text.lower()
                                except:
                                    pass
                            
                            if any(text.lower() in element_text for text in texts_to_match):
                                matching_element = element
                                self.logger.info(f"Found selectable element with text: '{element_text}'")
                                break
                        except Exception as e:
                            continue
                    
                    if matching_element:
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", matching_element)
                        human_delay(0.5, 1)
                        
                        try:
                            matching_element.click()
                            option_found = True
                            self.logger.info("Option selected via strategy 3")
                        except:
                            self.driver.execute_script("arguments[0].click();", matching_element)
                            option_found = True
                            self.logger.info("Option selected via strategy 3 (JS click)")
                except Exception as e:
                    self.logger.warning(f"Error in strategy 3: {e}")
            
            # Click "Show results" after selecting the option
            if option_found:
                human_delay(1, 2)
                
                # Find and click the "Show results" button - MULTIPLE STRATEGIES
                show_results_found = False
                
                # STRATEGY 1: Find button by aria-label, class and text
                try:
                    self.logger.info("Looking for 'Show results' button - Strategy 1")
                    show_results_xpaths = [
                        "//button[contains(@aria-label, 'Aplicar el filtro') or contains(@aria-label, 'Apply filter') or contains(@aria-label, 'mostrar') or contains(@aria-label, 'show results')]",
                        "//button[contains(@class, 'artdeco-button--primary')]//span[contains(text(), 'Mostrar') or contains(text(), 'resultados') or contains(text(), 'Show') or contains(text(), 'results')]/..",
                        "//footer//button[contains(@class, 'primary')]",
                        "//div[contains(@class, 'filter')]//button[contains(@class, 'primary')]"
                    ]
                    
                    for xpath in show_results_xpaths:
                        try:
                            buttons = self.driver.find_elements(By.XPATH, xpath)
                            self.logger.info(f"Found {len(buttons)} possible buttons with {xpath}")
                            
                            for button in buttons:
                                if button.is_displayed() and button.is_enabled():
                                    button_text = button.text.strip()
                                    if button_text:
                                        self.logger.info(f"Found visible button with text: '{button_text}'")
                                    else:
                                        self.logger.info("Found visible button without text")
                                    
                                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
                                    human_delay(0.5, 1)
                                    
                                    try:
                                        button.click()
                                        show_results_found = True
                                        self.logger.info("'Show results' button - Click successful (method 1)")
                                        break
                                    except Exception as click_err:
                                        self.logger.warning(f"Click error (method 1): {click_err}")
                                        try:
                                            self.driver.execute_script("arguments[0].click();", button)
                                            show_results_found = True
                                            self.logger.info("'Show results' button - JS click successful (method 1)")
                                            break
                                        except Exception as js_err:
                                            self.logger.warning(f"JS click error (method 1): {js_err}")
                            
                            if show_results_found:
                                break
                        except Exception as e:
                            self.logger.warning(f"Error with xpath {xpath}: {e}")
                except Exception as e:
                    self.logger.warning(f"General error in strategy 1: {e}")
                
                # STRATEGY 2: Use JavaScript to find the button by text or aria-label
                if not show_results_found:
                    try:
                        self.logger.info("Trying to find 'Show results' with JavaScript - Strategy 2")
                        js_script = """
                        return (function() {
                            const textPatterns = ['Mostrar', 'resultados', 'Show', 'results', 'Apply'];
                            const buttons = document.querySelectorAll('button');
                            
                            for (let i = 0; i < buttons.length; i++) {
                                const btn = buttons[i];
                                if (!btn.offsetParent) continue; // Skip hidden buttons
                                
                                // Check button text
                                let btnText = btn.innerText || '';
                                if (!btnText) {
                                    const span = btn.querySelector('span');
                                    btnText = span ? span.innerText : '';
                                }
                                
                                // Check aria-label
                                const ariaLabel = btn.getAttribute('aria-label') || '';
                                
                                // Check if this looks like our target button
                                const textContent = (btnText + ' ' + ariaLabel).toLowerCase();
                                if (textPatterns.some(pattern => textContent.includes(pattern.toLowerCase()))) {
                                    // Check if it has the primary button class
                                    if (btn.classList.contains('artdeco-button--primary')) {
                                        return btn;
                                    }
                                }
                            }
                            
                            // If no primary button with matching text, try any button with matching text
                            for (let i = 0; i < buttons.length; i++) {
                                const btn = buttons[i];
                                if (!btn.offsetParent) continue; // Skip hidden buttons
                                
                                let btnText = btn.innerText || '';
                                if (!btnText) {
                                    const span = btn.querySelector('span');
                                    btnText = span ? span.innerText : '';
                                }
                                
                                const ariaLabel = btn.getAttribute('aria-label') || '';
                                const textContent = (btnText + ' ' + ariaLabel).toLowerCase();
                                
                                if (textPatterns.some(pattern => textContent.includes(pattern.toLowerCase()))) {
                                    return btn;
                                }
                            }
                            
                            return null;
                        })();
                        """
                        
                        show_results_button = self.driver.execute_script(js_script)
                        
                        if show_results_button:
                            self.logger.info("'Show results' button found with JavaScript")
                            
                            self.driver.execute_script("arguments[0].click();", show_results_button)
                            show_results_found = True
                            self.logger.info("Click on 'Show results' successful with JavaScript (strategy 2)")
                    except Exception as e:
                        self.logger.warning(f"Error in JavaScript strategy for 'Show results': {e}")
                
                # STRATEGY 3: Find any visible button inside filter dropdowns
                if not show_results_found:
                    try:
                        self.logger.info("Trying last strategy for 'Show results' - Strategy 3")
                        
                        footer_selectors = [
                            "footer.search-reusables__filter-pill-footer",
                            "div.search-reusables__filter-pill-button-footers",
                            "div.artdeco-modal__actionbar",
                            "div.dialog-footer"
                        ]
                        
                        for selector in footer_selectors:
                            try:
                                footer = WebDriverWait(self.driver, 3).until(
                                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                                )
                                
                                buttons = footer.find_elements(By.TAG_NAME, "button")
                                self.logger.info(f"Found {len(buttons)} buttons in footer {selector}")
                                
                                for button in buttons:
                                    if button.is_displayed() and button.is_enabled():
                                        button_text = button.text.strip().lower()
                                        button_class = button.get_attribute("class") or ""
                                        
                                        is_primary = "primary" in button_class
                                        has_relevant_text = any(kw in button_text for kw in ["mostrar", "show", "apply", "aplicar", "result", "resultado"])
                                        
                                        if is_primary or has_relevant_text:
                                            self.logger.info(f"Found priority button: '{button_text}', Class: '{button_class}'")
                                            
                                            try:
                                                button.click()
                                                show_results_found = True
                                                self.logger.info(f"Successful click on button '{button_text}' (strategy 3)")
                                                break
                                            except:
                                                try:
                                                    self.driver.execute_script("arguments[0].click();", button)
                                                    show_results_found = True
                                                    self.logger.info(f"Successful JS click on button '{button_text}' (strategy 3)")
                                                    break
                                                except Exception as e:
                                                    self.logger.warning(f"Could not click button: {e}")
                                
                                if show_results_found:
                                    break
                            except:
                                continue
                    except Exception as e:
                        self.logger.warning(f"Error in strategy 3 for 'Show results': {e}")
                
                # If we found and clicked any button
                if show_results_found:
                    human_delay(3, 5)
                    
                    try:
                        self.driver.save_screenshot("after_filter_applied.png")
                        self.logger.info("Screenshot saved after applying filter")
                    except:
                        pass
                    
                    # Verify the filter was applied
                    try:
                        filter_indicators = [
                            ".search-reusables__filter-pill-button--selected",
                            "button[aria-expanded='true']",
                            ".filter-pill, .filter-pill-button"
                        ]
                        
                        filter_applied = False
                        for indicator in filter_indicators:
                            try:
                                indicator_elem = self.driver.find_element(By.CSS_SELECTOR, indicator)
                                if indicator_elem.is_displayed():
                                    self.logger.info(f"Filter indicator found: {indicator}")
                                    filter_applied = True
                                    break
                            except:
                                continue
                        
                        if filter_applied:
                            self.logger.info("Verified: Time filter successfully applied")
                            return True
                        else:
                            try:
                                result_count_selectors = [
                                    "h1.jobs-search-results-list__text",
                                    "span.jobs-search-results-list__text",
                                    "div.jobs-search-results-list__subtitle"
                                ]
                                
                                for selector in result_count_selectors:
                                    try:
                                        count_elem = self.driver.find_element(By.CSS_SELECTOR, selector)
                                        count_text = count_elem.text.strip()
                                        if count_text and any(kw in count_text.lower() for kw in ["result", "resultado"]):
                                            self.logger.info(f"Results count visible: '{count_text}'")
                                            return True
                                    except:
                                        continue
                            except:
                                pass
                            
                            self.logger.warning("Could not verify filter application, but click succeeded")
                            return True  # Return True anyway, assuming it worked
                    except Exception as e:
                        self.logger.warning(f"Error verifying filter application: {e}")
                        return True  # Assume it worked
                else:
                    self.logger.warning("'Show results' button not found")
                    try:
                        self.driver.save_screenshot("error_no_show_results_button.png")
                        
                        # As last resort, try pressing Escape to close dialogs and Enter to submit
                        ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()
                        human_delay(1, 2)
                        ActionChains(self.driver).send_keys(Keys.ENTER).perform()
                        human_delay(2, 3)
                    except:
                        pass
                    
                    return False
            else:
                self.logger.warning(f"Could not select any filter option for '{filter_option}'")
                return False
                
        except Exception as e:
            self.logger.error(f"Error applying time filter: {e}")
            try:
                self.driver.save_screenshot("error_filter_time.png")
            except:
                pass
            return False

    def _humanized_scroll_to_load_jobs(self) -> None:
        """
        Perform humanized scrolling to incrementally load more job listings.
        Includes verification of loaded content and natural pauses.
        """
        self.logger.info("Performing humanized scrolling to load more job results...")
        
        # Job list panel selectors
        job_list_panel_selectors = [
            "div.jobs-search-results-list",
            "div.scaffold-layout__list",
            "div.jobs-search__left-rail",
            "section.jobs-search__results-list",
            "ul.jobs-search-results__list",
            "div.jobs-search-two-pane__results",
            "div.jobs-search-results-list__infinite-scroll",
            "div.overflow-y-scroll",
            "div.overflow-y-auto"
        ]
        
        # Find the specific panel for scrolling
        panel_element = None
        for selector in job_list_panel_selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for elem in elements:
                    if elem.is_displayed():
                        try:
                            job_cards = elem.find_elements(By.CSS_SELECTOR, "li.jobs-search-results__list-item, div.job-card-container")
                            if job_cards and len(job_cards) > 0:
                                panel_element = elem
                                self.logger.info(f"Job panel found: {selector} with {len(job_cards)} initial cards")
                                break
                        except:
                            continue
                
                if panel_element:
                    break
            except Exception as e:
                self.logger.debug(f"Error searching selector {selector}: {e}")
                continue
        
        # If panel not found, try advanced JS methods
        if not panel_element:
            try:
                self.logger.info("Trying to find job panel via JavaScript")
                js_script = """
                return (function() {
                    // Find divs with overflow scroll/auto containing job cards
                    function isScrollable(element) {
                        const style = window.getComputedStyle(element);
                        return style.overflowY === 'scroll' || style.overflowY === 'auto';
                    }
                    
                    // First try known class selectors
                    const knownSelectors = [
                        '.jobs-search-results-list',
                        '.scaffold-layout__list',
                        '.jobs-search__left-rail',
                        '.jobs-search-two-pane__results'
                    ];
                    
                    for (const selector of knownSelectors) {
                        const elem = document.querySelector(selector);
                        if (elem && elem.offsetParent !== null) {
                            return elem;
                        }
                    }
                    
                    // Look for elements that appear to be result panels
                    const jobCardSelectors = [
                        '.job-card-container',
                        '.jobs-search-results__list-item',
                        '.jobs-search-two-pane__job-card'
                    ];
                    
                    // Find elements containing job cards
                    let jobContainers = [];
                    for (const selector of jobCardSelectors) {
                        const cards = document.querySelectorAll(selector);
                        if (cards.length > 0) {
                            // Find scrollable ancestor
                            let container = cards[0];
                            while (container && container !== document.body) {
                                if (isScrollable(container)) {
                                    jobContainers.push(container);
                                    break;
                                }
                                container = container.parentElement;
                            }
                        }
                    }
                    
                    // Return first container if found
                    if (jobContainers.length > 0) {
                        return jobContainers[0];
                    }
                    
                    // If still not found, find any large scrollable div
                    const allDivs = document.querySelectorAll('div');
                    for (const div of allDivs) {
                        if (isScrollable(div) && div.clientHeight > 300) {
                            return div;
                        }
                    }
                    
                    return null;
                })();
                """
                
                panel_element = self.driver.execute_script(js_script)
                if panel_element:
                    self.logger.info("Job panel found via JavaScript")
                else:
                    self.logger.warning("No specific panel found. Using document.body as fallback.")
                    panel_element = self.driver.find_element(By.TAG_NAME, "body")
            except Exception as e:
                self.logger.warning(f"Error finding panel with JS: {e}")
                panel_element = self.driver.find_element(By.TAG_NAME, "body")
        
        # Job card selectors
        job_card_selectors = [
            "li.jobs-search-results__list-item",
            "div.job-card-container",
            "li[data-occludable-job-id]",
            "div.jobs-search-two-pane__job-card"
        ]
        
        # Get initial job count
        initial_job_count = 0
        most_effective_selector = None
        for selector in job_card_selectors:
            try:
                jobs = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if len(jobs) > initial_job_count:
                    initial_job_count = len(jobs)
                    most_effective_selector = selector
            except:
                continue
        
        if initial_job_count == 0:
            self.logger.warning("No initial jobs found. Check selectors.")
            return
            
        self.logger.info(f"Initial count: {initial_job_count} jobs with selector {most_effective_selector}")
        
        # Scroll with incremental load verification
        max_scroll_attempts = 12
        scroll_without_new_content = 0
        max_consecutive_failures = 3
        
        for i in range(max_scroll_attempts):
            self.logger.info(f"Scroll attempt #{i+1}/{max_scroll_attempts}")
            
            # Save current count before scrolling
            current_count = 0
            try:
                current_count = len(self.driver.find_elements(By.CSS_SELECTOR, most_effective_selector))
            except:
                current_count = initial_job_count  # Fallback
            
            # Perform scrolling
            try:
                if panel_element.tag_name != "body":
                    # Scroll in specific panel
                    scroll_amount = random.randint(300, 700)
                    self.driver.execute_script(f"arguments[0].scrollTop += {scroll_amount};", panel_element)
                else:
                    # Scroll whole document as fallback
                    self.driver.execute_script(f"window.scrollBy(0, {random.randint(500, 1000)});")
                
                self.logger.info(f"Scroll performed in {panel_element.tag_name}")
                
                # Variable pause to load content
                pause_time = random.uniform(2.5, 4.5)
                time.sleep(pause_time)
                
                # Occasionally, simulate subtle mouse movement or scroll
                if random.random() < 0.3:
                    try:
                        small_scroll = random.randint(-50, 50)
                        if panel_element.tag_name != "body":
                            self.driver.execute_script(f"arguments[0].scrollTop += {small_scroll};", panel_element)
                        else:
                            self.driver.execute_script(f"window.scrollBy(0, {small_scroll});")
                        time.sleep(random.uniform(0.3, 0.8))
                    except:
                        pass
                
                # Check if new jobs were loaded
                try:
                    new_count = len(self.driver.find_elements(By.CSS_SELECTOR, most_effective_selector))
                    self.logger.info(f"Count after scroll: {new_count} (previous: {current_count})")
                    
                    if new_count > current_count:
                        scroll_without_new_content = 0  # Reset failure counter
                        self.logger.info(f"Loaded {new_count - current_count} new jobs!")
                        
                        # Extra time for many results
                        if new_count > 25:
                            extra_time = random.uniform(1, 3)
                            time.sleep(extra_time)
                            self.logger.info(f"Waiting {extra_time:.1f}s extra for {new_count} results")
                    else:
                        scroll_without_new_content += 1
                        self.logger.info(f"No new jobs detected. Attempt {scroll_without_new_content}/{max_consecutive_failures} without new results")
                        
                        # If several attempts without new results, we've probably reached the end
                        if scroll_without_new_content >= max_consecutive_failures:
                            self.logger.info(f"No new jobs detected after {max_consecutive_failures} attempts. Finishing scroll.")
                            break
                except Exception as e:
                    self.logger.warning(f"Error checking for new jobs: {e}")
                    scroll_without_new_content += 1
                
            except Exception as e:
                self.logger.warning(f"Error during humanized scroll #{i+1}: {e}")
                scroll_without_new_content += 1
        
        # Final verification
        try:
            final_count = len(self.driver.find_elements(By.CSS_SELECTOR, most_effective_selector))
            self.logger.info(f"Humanized scroll completed. Total jobs loaded: {final_count} (initial: {initial_job_count})")
            
            try:
                self.driver.save_screenshot("after_job_loading.png")
            except:
                pass
                
        except Exception as e:
            self.logger.warning(f"Error in final job verification: {e}")

    def search_jobs(self, search_criteria: Dict[str, Any]) -> List[JobListing]:
        """
        Search for jobs on LinkedIn using provided criteria.
        
        Args:
            search_criteria: Dictionary containing search parameters (keywords, location, filters)
            
        Returns:
            List of JobListing objects for the matching jobs
        """
        if not self.driver:
            self.logger.error("Driver not available.")
            return []
            
        keywords = search_criteria.get("keywords", "")
        location = search_criteria.get("location", "")
        time_filter = search_criteria.get("time_filter", "week")  # Default: last week
        
        self.logger.info(f"Starting search. Keywords:'{keywords}', Location:'{location}', Time filter: '{time_filter}'")
        
        try:
            # Navigate to the jobs page
            self.logger.info(f"Navigating to: {self.JOBS_URL}")
            self.driver.get(self.JOBS_URL)
            human_delay(2, 4)
            
            # Wait for search box container
            search_box_container_selectors = [
                ".jobs-search-box__container",
                ".jobs-search-box",
                ".jobs-search-two-pane__wrapper"
            ]
            
            container_found = False
            for selector in search_box_container_selectors:
                try:
                    WebDriverWait(self.driver, 15).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    self.logger.info(f"Search container found: {selector}")
                    container_found = True
                    break
                except TimeoutException:
                    continue
            
            if not container_found:
                self.logger.warning("Search container not found. Attempting to continue...")
                
            human_delay(1, 3)  # Wait for page to stabilize
            
            # Enter search criteria using multiple strategies
            self.logger.info("Attempting to complete search form...")
            search_success = False
            
            # STRATEGY 1: Use general input fields with various selectors
            try:
                kw_selectors = [
                    "input[id*='jobs-search-box-keyword-id']",
                    "input[aria-label*='Search jobs']",
                    "input[aria-label*='Buscar empleos']", 
                    "input[name='keywords']",
                    "input.jobs-search-box__text-input[placeholder*='Search']",
                    "input.jobs-search-box__keyboard-text-input"
                ]
                
                loc_selectors = [
                    "input[id*='jobs-search-box-location-id']",
                    "input[aria-label*='Location']",
                    "input[aria-label*='Ubicación']",
                    "input[name='location']",
                    "input.jobs-search-box__text-input[placeholder*='Location']",
                    "input.jobs-search-box__text-input[placeholder*='Ubicación']"
                ]
                
                # Find keyword input
                keyword_input = None
                for selector in kw_selectors:
                    try:
                        keyword_input = WebDriverWait(self.driver, 5).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                        )
                        self.logger.info(f"Keywords field found: {selector}")
                        break
                    except TimeoutException:
                        continue
                
                # Find location input
                location_input = None
                for selector in loc_selectors:
                    try:
                        location_input = WebDriverWait(self.driver, 5).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                        )
                        self.logger.info(f"Location field found: {selector}")
                        break
                    except TimeoutException:
                        continue
                
                if keyword_input and location_input:
                    # Clear and input search terms in a humanized way
                    keyword_input.clear()
                    human_delay(0.3, 0.8)
                    
                    # Type keywords with human-like delays
                    for char in keywords:
                        keyword_input.send_keys(char)
                        human_delay(0.05, 0.12)
                    
                    human_delay(0.5, 1.0)
                    
                    location_input.clear()
                    human_delay(0.3, 0.8)
                    
                    # Type location with human-like delays
                    for char in location:
                        location_input.send_keys(char)
                        human_delay(0.05, 0.12)
                    
                    human_delay(0.5, 1.0)
                    
                    # Submit search with Enter key
                    self.logger.info("Submitting search with ENTER key...")
                    location_input.send_keys(Keys.RETURN)
                    search_success = True
                    human_delay(3, 5)  # Wait for results to load
                else:
                    self.logger.warning("Could not find both search fields. Trying alternative strategy.")
            except Exception as e:
                self.logger.warning(f"Error in search strategy 1: {e}")
            
            # STRATEGY 2: If standard approach failed, try clicking search button directly
            if not search_success:
                try:
                    search_button_selectors = [
                        "button.jobs-search-box__submit-button",
                        "button[data-tracking-control-name='public_jobs_jobs-search-bar_base-search-bar-search-submit']",
                        "button[type='submit']"
                    ]
                    
                    for selector in search_button_selectors:
                        try:
                            search_button = WebDriverWait(self.driver, 5).until(
                                EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                            )
                            self.logger.info(f"Attempting to click search button: {selector}")
                            search_button.click()
                            search_success = True
                            human_delay(3, 5)  # Wait for results to load
                            break
                        except (TimeoutException, ElementNotInteractableException):
                            continue
                except Exception as e:
                    self.logger.warning(f"Error in search strategy 2: {e}")
            
            if not search_success:
                self.logger.error("Could not perform search. Attempting to capture results anyway.")
                self.driver.save_screenshot("error_search_strategy_failed.png")
            
            # Apply time filter
            if time_filter:
                time_filter_success = self._apply_time_filter(time_filter)
                if time_filter_success:
                    self.logger.info(f"Time filter '{time_filter}' successfully applied")
                else:
                    self.logger.warning(f"Could not apply time filter '{time_filter}'")
                
                # Wait for results to update with filter
                human_delay(3, 5)
            
            # Wait for search results to load
            self.logger.info("Waiting for search results...")
            
            # First wait for any job container
            job_container_selectors = [
                "div.jobs-search-results-list",
                "div.scaffold-layout__list",
                "div[data-view-name='job-search-results-list']",
                "section.jobs-search__results-list",
                "ul.jobs-search-results__list"
            ]
            
            container_found = False
            container_element = None
            
            for selector in job_container_selectors:
                try:
                    self.logger.info(f"Waiting for container: {selector}")
                    container_element = WebDriverWait(self.driver, 15).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    self.logger.info(f"Results container found: {selector}")
                    container_found = True
                    break
                except TimeoutException:
                    continue
            
            if not container_found:
                self.logger.warning("No specific results container found. Using body for search.")
                container_element = self.driver.find_element(By.TAG_NAME, "body")
            
            # Scroll to load content with humanized pauses
            self._humanized_scroll_to_load_jobs()
            job_listings: List[JobListing] = []
            
            # JOB SCRAPER STRATEGY: Find job listings and check if already applied
            self.logger.info("Searching for job listings...")
            
            job_card_selectors = [
                "li.jobs-search-results__list-item",
                "li.jobs-search-results__job-card-search-result",
                "div.job-search-card",
                "div.jobs-search-results__list-item",
                "li[data-occludable-job-id]",
                "div.base-card",
                "div.base-search-card--link"
            ]
            
            for selector in job_card_selectors:
                try:
                    self.logger.info(f"Trying selector: {selector}")
                    job_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    
                    if job_elements and len(job_elements) > 0:
                        self.logger.info(f"SUCCESS! Found {len(job_elements)} elements with {selector}")
                        
                        for i, elem in enumerate(job_elements):
                            if i >= 40:  # Limit to first 40 jobs
                                self.logger.info("Extraction limit reached (40 jobs).")
                                break
                                
                            try:
                                # Brief pause between elements for human-like behavior
                                if i > 0 and i % 5 == 0:
                                    human_delay(0.5, 1.5)
                                
                                # Initialize variables
                                title = None
                                company = None
                                location = None
                                url = None
                                job_id = None
                                already_applied = False
                                
                                # Check if job has already been applied to
                                try:
                                    applied_indicators = [
                                        ".//li[contains(text(), 'Solicitado')]",
                                        ".//span[contains(text(), 'Solicitado')]",
                                        ".//li[contains(text(), 'Solicitud vista')]",
                                        ".//span[contains(text(), 'Solicitud enviada')]",
                                        ".//span[contains(text(), 'Applied')]",
                                        ".//li[contains(@class, 'applied')]",
                                        ".//div[contains(@class, 'applied')]"
                                    ]
                                    
                                    for indicator in applied_indicators:
                                        try:
                                            applied_elem = elem.find_element(By.XPATH, indicator)
                                            if applied_elem:
                                                already_applied = True
                                                self.logger.info(f"Job #{i+1} already applied: '{indicator}'")
                                                break
                                        except NoSuchElementException:
                                            continue
                                except Exception as e:
                                    self.logger.debug(f"Error checking if job #{i+1} was already applied: {e}")
                                
                                # Extract job title
                                title_selectors = [
                                    ".job-card-list__title", 
                                    ".base-search-card__title",
                                    "h3", 
                                    "[class*='job-card-list__title']", 
                                    "[class*='base-search-card__title']",
                                    "a[data-control-name='job_card_title']",
                                    "a[href*='/jobs/view/'] strong"
                                ]
                                
                                for selector in title_selectors:
                                    try:
                                        title_elem = elem.find_element(By.CSS_SELECTOR, selector)
                                        title = title_elem.text.strip()
                                        if title:
                                            break
                                    except:
                                        continue
                                
                                # Extract company name
                                company_selectors = [
                                    ".job-card-container__primary-description", 
                                    ".base-search-card__subtitle", 
                                    ".artdeco-entity-lockup__subtitle", 
                                    "[class*='job-card-container__company-name']",
                                    "h4"
                                ]
                                
                                for selector in company_selectors:
                                    try:
                                        company_elem = elem.find_element(By.CSS_SELECTOR, selector)
                                        company = company_elem.text.strip()
                                        if company:
                                            break
                                    except:
                                        continue
                                
                                # Extract location
                                location_selectors = [
                                    ".job-card-container__metadata-item", 
                                    ".job-search-card__location",
                                    "span[class*='job-search-card__location']",
                                    "[class*='job-card-container__metadata-item']"
                                ]
                                
                                for selector in location_selectors:
                                    try:
                                        location_elem = elem.find_element(By.CSS_SELECTOR, selector)
                                        location = location_elem.text.strip()
                                        if location:
                                            break
                                    except:
                                        continue
                                
                                # Extract job URL
                                url_selectors = [
                                    "a[href*='/jobs/view/']", 
                                    "a.base-card__full-link", 
                                    "a.job-card-container__link",
                                    "a[data-control-name='job_card_title']"
                                ]
                                
                                for selector in url_selectors:
                                    try:
                                        link_elem = elem.find_element(By.CSS_SELECTOR, selector)
                                        url_raw = link_elem.get_attribute('href')
                                        if url_raw and 'linkedin.com/jobs/view/' in url_raw:
                                            url = url_raw.split('?')[0]  # Remove query parameters
                                            # Extract job ID from URL
                                            job_id = url.split('/view/')[1].split('/')[0] if '/view/' in url else None
                                            break
                                    except:
                                        continue
                                
                                # If URL extraction failed, try element itself
                                if not url:
                                    try:
                                        url_raw = elem.get_attribute('href')
                                        if url_raw and 'linkedin.com/jobs/view/' in url_raw:
                                            url = url_raw.split('?')[0]
                                            job_id = url.split('/view/')[1].split('/')[0] if '/view/' in url else None
                                    except:
                                        pass
                                
                                # Create JobListing if we have at least title and URL
                                if title and url:
                                    job_listings.append(JobListing(
                                        title=title,
                                        company=company if company else "Unknown Company", 
                                        location=location if location else "Unknown Location",
                                        url=url,
                                        linkedin_job_id=job_id,
                                        already_applied=already_applied
                                    ))
                                    self.logger.debug(f"Scraped: T={title}, C={company}, L={location}, U={url}, ID={job_id}, Applied={already_applied}")
                                else:
                                    self.logger.warning(f"Incomplete data #{i+1}. T:'{title}', U:'{url}'. Skipping.")
                            except Exception as e:
                                self.logger.warning(f"Error processing element #{i+1}: {e}")
                                continue
                        
                        if job_listings:
                            self.logger.info(f"Success with selector '{selector}'. {len(job_listings)} job listings extracted.")
                            return job_listings
                    else:
                        self.logger.info(f"No elements found with selector: {selector}")
                except Exception as e:
                    self.logger.warning(f"Error trying selector {selector}: {e}")
            
            # If main scraper failed, try alternative methods...
            
            # If we've reached here with no results, return empty list
            if not job_listings:
                self.logger.warning("No data extracted (scraping failed/no valid results).")
                
                # Check for 429 error (Too Many Requests)
                if "429" in self.driver.page_source or "too many requests" in self.driver.page_source.lower():
                    self.logger.error("ERROR 429 DETECTED: LinkedIn is blocking requests due to rate limiting.")
                    self.driver.save_screenshot("error_429_rate_limit.png")
                    
                    # Implement waiting strategy
                    if self.retry_count < self.max_retries:
                        self.retry_count += 1
                        wait_time = 60 * self.retry_count  # Exponential backoff strategy
                        self.logger.info(f"Waiting {wait_time} seconds before retrying (attempt {self.retry_count}/{self.max_retries})...")
                        time.sleep(wait_time)
                        
                        # Restart the WebDriver
                        self.close()
                        self._initialize_driver()
                        self._login()
                        
                        # Retry the search
                        self.logger.info("Retrying search...")
                        return self.search_jobs(search_criteria)
            else:
                self.logger.info(f"Scraping complete. {len(job_listings)} job listings extracted.")
                
            # Reset retry count on success
            self.retry_count = 0
            return job_listings
            
        except Exception as e:
            self.logger.error(f"Unexpected search/scraping error: {e}", exc_info=True)
            self.driver.save_screenshot("error_search_unexpected.png")
            return []

    def get_job_details(self, job_url: str) -> Optional[str]:
        """
        Get detailed job description from a job listing page.
        
        Args:
            job_url: URL of the job listing page
            
        Returns:
            Job description text or None if not found
        """
        if not self.driver:
            self.logger.error("Driver not available.")
            return None
            
        self.logger.info(f"Navigating to job URL: {job_url}")
        
        # Avoid infinite recursion with local attempt counter
        max_attempts = 2
        attempt = 0
        
        while attempt < max_attempts:
            attempt += 1
            try:
                # Add random headers to reduce detection
                self.driver.execute_script("""
                    Object.defineProperty(navigator, 'platform', {
                        get: function() { return ['Win32', 'MacIntel', 'Linux x86_64'][Math.floor(Math.random() * 3)]; }
                    });
                """)
                
                time.sleep(random.uniform(0.5, 1.5))
                
                self.driver.get(job_url)
                time.sleep(random.uniform(0.5, 1.0))
                
                # Check for 429 error
                if "429" in self.driver.page_source or "too many requests" in self.driver.page_source.lower():
                    self.logger.error(f"ERROR 429 DETECTED loading {job_url}")
                    
                    if attempt < max_attempts:
                        wait_time = 30 if attempt == 1 else 60
                        self.logger.info(f"Waiting {wait_time}s before retry {attempt+1}/{max_attempts}")
                        time.sleep(wait_time)
                        continue
                    else:
                        return "Could not get description due to 429 error"
                
                # Try multiple selectors for job description with reduced timeout
                desc_selectors = [
                    ".jobs-description-content__text",
                    ".show-more-less-html__markup",
                    "#job-details",
                    ".jobs-description__content",
                    "div[class*='description__text']",
                    "div.jobs-box__html-content"
                ]
                
                desc_elem = None
                
                # Try each selector with reduced timeout
                for selector in desc_selectors:
                    try:
                        desc_elem = WebDriverWait(self.driver, 8).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                        )
                        self.logger.info(f"Description element found: {selector}")
                        break
                    except TimeoutException:
                        continue
                        
                if not desc_elem:
                    if attempt < max_attempts:
                        wait_time = 10
                        self.logger.info(f"No description found, retrying in {wait_time}s")
                        time.sleep(wait_time)
                        continue
                    else:
                        return "Could not find job description"
                
                # Scroll to see description content
                try:
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", desc_elem)
                    time.sleep(0.5)
                except:
                    pass
                
                # Try to expand the description with "See more" button
                try:
                    see_more_xpath = "//button[contains(@class, 'jobs-description__footer-button') or contains(@class, 'artdeco-button') or contains(@class, 'show-more-less-html__button--more')]//span[contains(text(), 'Ver más')]/.. | //button[contains(@aria-label, 'ver más descripción')]"
                    
                    try:
                        show_more_btn = WebDriverWait(self.driver, 3).until(
                            EC.element_to_be_clickable((By.XPATH, see_more_xpath))
                        )
                        self.logger.info("'See more' button found by XPath")
                        
                        # Scroll to button
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", show_more_btn)
                        time.sleep(0.5)
                        
                        # Try multiple click methods
                        try:
                            show_more_btn.click()
                            self.logger.info("Normal click on 'See more' successful")
                        except:
                            try:
                                self.driver.execute_script("arguments[0].click();", show_more_btn)
                                self.logger.info("JS click on 'See more' successful")
                            except:
                                # Last attempt with specific JavaScript
                                self.driver.execute_script("""
                                    Array.from(document.querySelectorAll('button')).forEach(btn => {
                                        if ((btn.innerText || '').toLowerCase().includes('ver más')) {
                                            btn.click();
                                        }
                                    });
                                """)
                        
                        time.sleep(1)  # Wait for expansion
                    except Exception as e:
                        self.logger.debug(f"Could not expand 'See more': {e}")
                except Exception as e:
                    self.logger.debug(f"Error expanding description: {e}")
                
                # Get text content after possible expansion
                time.sleep(0.5)
                
                # Get text and return
                result = desc_elem.get_attribute('textContent').strip()
                if result:
                    return result
                else:
                    return "Empty description"
                    
            except Exception as e:
                self.logger.error(f"Error getting description: {e}")
                if attempt < max_attempts:
                    time.sleep(5)
                else:
                    return "Error loading description. LinkedIn may be rate-limiting requests."
        
        return None  # Only reaches here if all attempts fail
    
    def get_recruiter_info(self, job_url: Optional[str] = None) -> Dict[str, str]:
        """
        Get recruiter information from the job details page.
        
        Args:
            job_url: URL of the job listing page (optional, uses current page if None)
            
        Returns:
            Dictionary with recruiter information (name, title, etc.)
        """
        recruiter_info = {
            "name": None,
            "title": None,
            "company": None
        }
        
        if not self.driver:
            self.logger.error("Driver not available.")
            return recruiter_info
        
        if job_url and self.driver.current_url != job_url:
            self.logger.info(f"Navigating to URL for recruiter info: {job_url}")
            try:
                self.driver.get(job_url)
                human_delay(2, 3)
            except:
                self.logger.warning(f"Error navigating to {job_url}")
                return recruiter_info
        
        try:
            # Find the "Meet the hiring team" section
            hiring_team_selectors = [
                "h2.text-heading-medium:contains('Conoce al equipo de contratación')",
                "h2[class*='text-heading']:contains('Conoce al equipo')",
                "h2:contains('hiring team')",
                "h2:contains('Conoce al equipo')",
                "div.job-details-people-who-can-help__section",
                ".job-details-people-who-can-help"
            ]
            
            hiring_section = None
            for selector in hiring_team_selectors:
                try:
                    if ":contains(" in selector:
                        text = selector.split(":contains(")[1].strip("'\")")
                        xpath = f"//h2[contains(text(), '{text}')]"
                        hiring_section = self.driver.find_element(By.XPATH, xpath)
                    else:
                        hiring_section = self.driver.find_element(By.CSS_SELECTOR, selector)
                    
                    self.logger.info(f"'Meet the team' section found")
                    break
                except NoSuchElementException:
                    continue
            
            if not hiring_section:
                # Try other methods to find the section
                alternative_xpath = "//h2[contains(text(), 'Conoce') and contains(text(), 'equipo')] | //h2[contains(text(), 'hiring team')]"
                try:
                    hiring_section = self.driver.find_element(By.XPATH, alternative_xpath)
                    self.logger.info("'Meet the team' section found with alternative XPath")
                except:
                    self.logger.info("'Meet the team' section not found")
                    return recruiter_info
            
            # Scroll to section for visibility
            try:
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", hiring_section)
                human_delay(1, 2)
            except:
                pass
            
            # Find the first recruiter
            try:
                # First try to find section by class
                recruiter_section = self.driver.find_element(By.CSS_SELECTOR, ".hirer-card")
                self.logger.info("Recruiter card found")
            except:
                # If fails, try to find after the heading
                try:
                    recruiter_section = hiring_section.find_element(By.XPATH, "./following-sibling::div[1]")
                except:
                    self.logger.warning("Could not find recruiter card")
                    return recruiter_info
            
            # Extract recruiter name
            try:
                name_selectors = [
                    ".jobs-poster__name",
                    "a[data-test-app-aware-link] strong",
                    "strong",
                    "span.t-bold"
                ]
                
                for selector in name_selectors:
                    try:
                        name_elem = recruiter_section.find_element(By.CSS_SELECTOR, selector)
                        recruiter_info["name"] = name_elem.text.strip()
                        self.logger.info(f"Recruiter name found: {recruiter_info['name']}")
                        break
                    except:
                        continue
            except Exception as e:
                self.logger.warning(f"Error finding recruiter name: {e}")
            
            # Extract recruiter title
            try:
                title_selectors = [
                    ".tvm-text",
                    ".t-black--light",
                    "span.t-14"
                ]
                
                for selector in title_selectors:
                    try:
                        title_elem = recruiter_section.find_element(By.CSS_SELECTOR, selector)
                        recruiter_info["title"] = title_elem.text.strip()
                        self.logger.info(f"Recruiter title found: {recruiter_info['title']}")
                        break
                    except:
                        continue
            except Exception as e:
                self.logger.warning(f"Error finding recruiter title: {e}")
            
            return recruiter_info
            
        except Exception as e:
            self.logger.warning(f"Error getting recruiter info: {e}")
            return recruiter_info

    def close(self) -> None:
        """Close the WebDriver session."""
        if self.driver:
            self.logger.info("Closing WebDriver.")
            try:
                self.driver.quit()
            except Exception as e:
                self.logger.error(f"Error closing WebDriver: {e}")
            finally:
                self.driver = None