"""
Browser automation module for LinkedIn job applications.

Provides functionality to interact with job application interfaces,
handle application forms, and automate the "Easy Apply" process.
"""

import time
import logging
import os
import re
import random
from typing import Optional, List, Tuple, Any, Dict

from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.common.exceptions import NoSuchElementException, TimeoutException, ElementClickInterceptedException, StaleElementReferenceException, ElementNotInteractableException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains

from ..config import Config

class BrowserAutomator:
    """
    Handles the automation of applying to jobs via LinkedIn's browser interface.
    Includes specialized methods for handling "Easy Apply" forms.
    """

    def __init__(self, driver: WebDriver, config: Config):
        """
        Initialize the browser automator.
        
        Args:
            driver: Selenium WebDriver instance
            config: Application configuration
        """
        self.driver = driver
        self.config = config
        self.logger = logging.getLogger(__name__)
        # Create directory for screenshots if it doesn't exist
        self.screenshots_dir = "debug_screenshots"
        if not os.path.exists(self.screenshots_dir):
            os.makedirs(self.screenshots_dir)
        # Track whether cover letter is needed
        self.cover_letter_needed = False

    def _take_debug_screenshot(self, name: str) -> str:
        """
        Take a screenshot and save it with a descriptive name.
        
        Args:
            name: Base name for the screenshot
            
        Returns:
            Path to the saved screenshot file
        """
        timestamp = int(time.time())
        filename = f"{self.screenshots_dir}/{name}_{timestamp}.png"
        try:
            self.driver.save_screenshot(filename)
            self.logger.info(f"Screenshot saved: {filename}")
            return filename
        except Exception as e:
            self.logger.error(f"Error saving screenshot {name}: {e}")
            return ""

    def _wait_for_page_load(self, timeout=10):
        """
        Wait for the page to be fully loaded.
        
        Args:
            timeout: Maximum time to wait in seconds
            
        Returns:
            bool: True if page loaded successfully, False otherwise
        """
        try:
            # Wait for document.readyState to be "complete"
            WebDriverWait(self.driver, timeout).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            # Random wait to simulate human behavior
            time.sleep(random.uniform(1, 2))
            return True
        except:
            self.logger.warning("Timeout waiting for page to load")
            return False

    def _detect_cover_letter_field(self, container) -> Tuple[Optional[WebElement], bool]:
        """
        Detect cover letter fields in any container using an enhanced strategy.
        
        Args:
            container: Element to search within
            
        Returns:
            Tuple containing (field element or None, whether field was found)
        """
        cover_letter_selectors = [
            # Explicit selectors by attributes
            "textarea[id*='cover-letter'], textarea[name*='cover-letter'], textarea[aria-label*='cover letter']",
            "textarea[id*='coverletter'], textarea[name*='coverletter']",
            "textarea[placeholder*='cover letter'], textarea[placeholder*='Cover Letter']",
            "textarea[id*='text-entity-list-form-component']",
            # Generic selectors for large textareas
            "textarea.ember-text-area",
            "textarea.jobs-easy-apply-form-element__textarea",
            # Any large textarea (likely cover letter)
            "textarea[rows='5'], textarea[rows='6'], textarea[rows='7'], textarea[rows='8']",
            "textarea[cols='40'], textarea[cols='50'], textarea[cols='60']"
        ]
        
        # New categories of selectors
        xpath_selectors = [
            # Search by nearby label suggesting cover letter
            "//label[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'cover letter')]/following::textarea",
            "//label[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'carta de presentación')]/following::textarea",
            "//label[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'cover')]/following::textarea",
            # Search by div with suggestive title
            "//div[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'cover letter')]/following::textarea",
            "//div[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'additional information')]/following::textarea",
            "//h3[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'cover')]/following::textarea"
        ]
        
        # Try CSS selectors first (faster)
        for selector in cover_letter_selectors:
            try:
                elements = container.find_elements(By.CSS_SELECTOR, selector)
                for element in elements:
                    if element.is_displayed():
                        # Verify size or attributes to confirm it's a cover letter field
                        size = element.size
                        if size['height'] >= 60 or size['width'] >= 300:  # Large fields are likely cover letter
                            self.logger.info(f"Cover letter field found with selector: {selector}")
                            self.logger.info(f"Field size: {size}")
                            return element, True
            except Exception as e:
                self.logger.debug(f"Error searching for cover letter with selector {selector}: {e}")
                continue
        
        # If not found with CSS, try XPath
        for xpath in xpath_selectors:
            try:
                elements = container.find_elements(By.XPATH, xpath)
                for element in elements:
                    if element.is_displayed():
                        # Analyze context to confirm it's a cover letter
                        page_source = container.get_attribute("innerHTML").lower()
                        cover_letter_keywords = ["cover letter", "carta de presentación", "cover", "carta", "additional information"]
                        if any(keyword in page_source for keyword in cover_letter_keywords):
                            self.logger.info(f"Cover letter field found with XPath: {xpath}")
                            return element, True
            except Exception as e:
                self.logger.debug(f"Error searching for cover letter with XPath {xpath}: {e}")
                continue
        
        # As last resort, look for any large textarea
        try:
            textareas = container.find_elements(By.TAG_NAME, "textarea")
            for textarea in textareas:
                try:
                    if textarea.is_displayed():
                        # Get placeholder or label
                        placeholder = textarea.get_attribute("placeholder") or ""
                        aria_label = textarea.get_attribute("aria-label") or ""
                        
                        # Check if placeholder or aria-label suggests cover letter
                        if any(keyword in (placeholder + aria_label).lower() for keyword in 
                               ["cover", "carta", "present", "additional", "custom", "more"]):
                            self.logger.info(f"Cover letter field detected by placeholder/aria-label: {placeholder or aria_label}")
                            return textarea, True
                        
                        # Check size (cover letters are usually large fields)
                        size = textarea.size
                        if size['height'] >= 70 or size['width'] >= 350:
                            self.logger.info(f"Large textarea detected, likely cover letter. Size: {size}")
                            return textarea, True
                except Exception as e:
                    continue
        except Exception as e:
            self.logger.debug(f"Error in final textarea search: {e}")
        
        # No cover letter field found
        return None, False

    def _handle_easy_apply_modal(self, resume_path: Optional[str], cover_letter_text: Optional[str] = None) -> bool:
        """ 
        Handle all steps within the Easy Apply modal window.
        
        Args:
            resume_path: Path to resume file
            cover_letter_text: Cover letter text (optional)
            
        Returns:
            bool: True if application was successful, False otherwise
        """
        # Reset cover letter needed flag
        self.cover_letter_needed = False
        
        try:
            modal_selector = "div[aria-labelledby*='easy-apply-modal-title'], div.jobs-easy-apply-modal"
            self.logger.debug("Waiting for Easy Apply modal...")
            modal = WebDriverWait(self.driver, 15).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, modal_selector))
            )
            self.logger.info("Easy Apply modal opened.")
            self._take_debug_screenshot("modal_opened")

            # XPath selectors for common buttons in the modal
            # Prioritize final submit buttons
            final_submit_xpath = "//button[@aria-label='Submit application' or contains(@aria-label,'Enviar solicitud') or contains(.,'Enviar solicitud')]"
            next_or_review_xpath = "//button[@aria-label='Continue to next step' or contains(@aria-label,'Siguiente') or contains(.,'Siguiente') or @aria-label='Review application' or contains(@aria-label,'Revisar')]"
            # Combine to search for any in order
            any_action_button_xpath = f"{final_submit_xpath} | {next_or_review_xpath}"

            step_counter = 0
            max_steps = 20  # Increased step limit for long forms

            while step_counter < max_steps:
                step_counter += 1
                self.logger.info(f"Modal - Step {step_counter}")
                current_url = self.driver.current_url  # For error logs
                self._take_debug_screenshot(f"modal_step_{step_counter}")

                # --- Look for cover letter field with improved method ---
                if cover_letter_text:
                    try:
                        cover_letter_field, is_cover_letter = self._detect_cover_letter_field(modal)
                        
                        if is_cover_letter and cover_letter_field:
                            self.logger.info("Cover letter field found with improved method!")
                            self.cover_letter_needed = True
                            self._take_debug_screenshot("cover_letter_field_found")
                            
                            # Clear field and enter text
                            cover_letter_field.clear()
                            time.sleep(0.5)
                            
                            # Use character-by-character approach to simulate human typing
                            # For large fields, this can be slow, so use alternative:
                            # Combine JS to set value + send some characters to trigger events
                            try:
                                # First set value with JS
                                self.driver.execute_script("arguments[0].value = arguments[1];", cover_letter_field, cover_letter_text)
                                
                                # Then send some characters to trigger change events
                                cover_letter_field.send_keys(" ")  # Space
                                time.sleep(0.2)
                                cover_letter_field.send_keys("\b")  # Backspace to remove space
                            except:
                                # If failed, try traditional method
                                self.logger.info("Using traditional text input method")
                                cover_letter_field.send_keys(cover_letter_text)
                                
                            self.logger.info("Cover letter pasted in field.")
                            time.sleep(1)
                    except Exception as cl_err:
                        self.logger.warning(f"Error finding/filling cover letter field: {cl_err}")

                # --- Handle common form fields ---
                try:
                    # Handle checkboxes (especially for consent questions)
                    checkboxes = modal.find_elements(By.CSS_SELECTOR, "input[type='checkbox']:not(:checked)")
                    if checkboxes:
                        for checkbox in checkboxes:
                            try:
                                if checkbox.is_displayed():
                                    # Check if it's a checkbox for accepting something (terms, etc.)
                                    checkbox_id = checkbox.get_attribute("id") or ""
                                    checkbox_label_xpath = f"//label[@for='{checkbox_id}']"
                                    
                                    try:
                                        label = self.driver.find_element(By.XPATH, checkbox_label_xpath)
                                        label_text = label.text.lower()
                                        
                                        # If it looks like a consent/terms checkbox, check it
                                        if any(keyword in label_text for keyword in ["consent", "agree", "terms", "acepto", "autorizo"]):
                                            self.logger.info(f"Checking consent checkbox: '{label_text}'")
                                            try:
                                                checkbox.click()
                                            except:
                                                self.driver.execute_script("arguments[0].click();", checkbox)
                                    except:
                                        # If we can't determine the purpose, try to check it anyway
                                        self.logger.info("Checking checkbox with unidentifiable label")
                                        try:
                                            checkbox.click()
                                        except:
                                            self.driver.execute_script("arguments[0].click();", checkbox)
                            except Exception as check_err:
                                self.logger.debug(f"Error with checkbox: {check_err}")
                    
                    # Handle select/dropdown
                    selects = modal.find_elements(By.TAG_NAME, "select")
                    if selects:
                        for select_elem in selects:
                            try:
                                if select_elem.is_displayed():
                                    # Import Select for dropdown interaction
                                    from selenium.webdriver.support.ui import Select
                                    select = Select(select_elem)
                                    
                                    # Get all available options
                                    options = select.options
                                    
                                    # If an option is already selected by default, don't change
                                    selected_options = [opt for opt in options if opt.is_selected()]
                                    if selected_options and selected_options[0].text.strip():
                                        self.logger.info(f"Select already has option selected: '{selected_options[0].text}'")
                                        continue
                                        
                                    # If no selection or first empty, select first valid option
                                    if len(options) > 1:
                                        # Try to find a good option to select
                                        # Prefer "Yes" or "Sí" for Yes/No questions
                                        yes_option = None
                                        for opt in options:
                                            if opt.text.strip().lower() in ["yes", "sí", "si"]:
                                                yes_option = opt
                                                break
                                                
                                        if yes_option:
                                            select.select_by_visible_text(yes_option.text.strip())
                                            self.logger.info(f"Selected 'Yes/Sí' for question")
                                        else:
                                            # Select first non-empty option
                                            for index, option in enumerate(options):
                                                if option.text.strip() and index > 0:  # Skip first if empty
                                                    select.select_by_index(index)
                                                    self.logger.info(f"Selected '{option.text}' from select")
                                                    break
                            except Exception as select_err:
                                self.logger.debug(f"Error with select: {select_err}")
                                
                    # Handle required input fields that aren't completed
                    try:
                        # Identify uncompleted required fields
                        required_inputs = modal.find_elements(By.CSS_SELECTOR, "input[required]:not([type='checkbox']):not([type='hidden'])")
                        for input_field in required_inputs:
                            try:
                                if input_field.is_displayed() and not input_field.get_attribute("value"):
                                    input_type = input_field.get_attribute("type") or "text"
                                    
                                    # Handle different input types
                                    if input_type == "text":
                                        # Try to determine what kind of data it expects
                                        placeholder = input_field.get_attribute("placeholder") or ""
                                        aria_label = input_field.get_attribute("aria-label") or ""
                                        field_id = input_field.get_attribute("id") or ""
                                        
                                        input_field_context = (placeholder + " " + aria_label + " " + field_id).lower()
                                        
                                        # Fill based on context
                                        if any(word in input_field_context for word in ["city", "ciudad"]):
                                            input_field.send_keys("Madrid")
                                        elif any(word in input_field_context for word in ["phone", "teléfono", "telefono"]):
                                            input_field.send_keys("+34608493139")
                                        elif any(word in input_field_context for word in ["years", "experience", "años", "experiencia"]):
                                            input_field.send_keys("3")
                                        else:
                                            # Generic value if we can't determine type
                                            input_field.send_keys("Yes")
                                    
                                    elif input_type == "number":
                                        input_field.send_keys("3")  # Default numeric value
                            except Exception as input_err:
                                self.logger.debug(f"Error completing input: {input_err}")
                    except Exception as required_err:
                        self.logger.debug(f"Error finding required fields: {required_err}")
                    
                except Exception as form_err:
                    self.logger.debug(f"General form handling error: {form_err}")

                # --- Resume upload attempt ---
                try:
                    upload_input_selector = "input[type='file'][id*='upload-resume'], input[type='file'][aria-label*='upload resume'], input[type='file'][name*='resume'], input[type='file']"
                    resume_upload_input = WebDriverWait(modal, 2).until(  # Short wait in case it appears
                         EC.presence_of_element_located((By.CSS_SELECTOR, upload_input_selector))
                    )
                    if resume_path:
                        self.logger.info(f"Resume field found. Uploading: {resume_path}")
                        resume_upload_input.send_keys(resume_path)
                        time.sleep(3)  # Allow time for upload
                    else: 
                        self.logger.warning("Resume field found but no path defined.")
                except TimeoutException: 
                    self.logger.debug("No resume upload field found in this step.")
                except Exception as upload_err: 
                    self.logger.error(f"Resume upload error: {upload_err}", exc_info=True)

                # --- Click Next / Submit ---
                action_button = None
                
                # Strategy 1: Search with standard XPath
                try:
                    self.logger.debug("Looking for action button with standard XPath...")
                    action_button = WebDriverWait(modal, 6).until(
                        EC.element_to_be_clickable((By.XPATH, any_action_button_xpath))
                    )
                except (TimeoutException, NoSuchElementException):
                    self.logger.debug("No action button found with standard XPath")
                
                # Strategy 2: Find any button and filter by text if first strategy failed
                if not action_button:
                    try:
                        self.logger.debug("Looking for any button in the modal...")
                        buttons = modal.find_elements(By.TAG_NAME, "button")
                        self.logger.info(f"Found {len(buttons)} buttons in modal")
                        
                        for btn in buttons:
                            try:
                                btn_text = btn.text.strip().lower()
                                self.logger.debug(f"Button found with text: '{btn_text}'")
                                if any(keyword in btn_text for keyword in ['siguiente', 'revisar', 'enviar', 'submit', 'review', 'next', 'continue']):
                                    self.logger.info(f"Potential action button found: '{btn_text}'")
                                    if btn.is_displayed() and btn.is_enabled():
                                        action_button = btn
                                        break
                            except:
                                continue
                    except Exception as e:
                        self.logger.warning(f"Error searching for alternative buttons: {e}")
                
                # If we found a button, try to click it
                if action_button:
                    button_text = "unknown"
                    try:
                        button_text = action_button.text.strip()
                        button_aria_label = action_button.get_attribute("aria-label") or ""
                        button_desc = button_text or button_aria_label or "no text"
                        self.logger.info(f"Clicking button: '{button_desc}'")
                        
                        # Check if it's a final submit button
                        is_final_submit = False
                        if any(keyword in button_text.lower() for keyword in ['enviar', 'submit']):
                            is_final_submit = True
                            self.logger.info("Detected final submit button.")
                        
                        # MULTIPLE CLICK STRATEGY
                        click_success = False
                        
                        # 1. Normal attempt
                        try:
                            self.logger.debug("Trying normal click...")
                            action_button.click()
                            click_success = True
                            self.logger.info("Normal click successful")
                        except Exception as e:
                            self.logger.debug(f"Normal click failed: {e}")
                        
                        # 2. JavaScript click if normal failed
                        if not click_success:
                            try:
                                self.logger.debug("Trying JavaScript click...")
                                self.driver.execute_script("arguments[0].click();", action_button)
                                click_success = True
                                self.logger.info("JavaScript click successful")
                            except Exception as e:
                                self.logger.debug(f"JavaScript click failed: {e}")
                        
                        # 3. ActionChains if previous methods failed
                        if not click_success:
                            try:
                                self.logger.debug("Trying ActionChains click...")
                                actions = ActionChains(self.driver)
                                actions.move_to_element(action_button).pause(0.5).click().perform()
                                click_success = True
                                self.logger.info("ActionChains click successful")
                            except Exception as e:
                                self.logger.debug(f"ActionChains click failed: {e}")
                        
                        # If all clicks failed
                        if not click_success:
                            self.logger.error("All click methods failed")
                            continue  # Try with next step
                        
                        time.sleep(3)  # Longer wait to see results
                        self._take_debug_screenshot(f"after_click_step_{step_counter}")
                        
                        # --- Check result AFTER click ---
                        # 1. Did modal disappear? (Most likely success)
                        try:
                            WebDriverWait(self.driver, 3).until_not(
                                EC.visibility_of_element_located((By.CSS_SELECTOR, modal_selector))
                            )
                            self.logger.info("SUCCESS! Modal closed after click. Application likely submitted.")
                            return True
                        except TimeoutException:
                            # 2. If modal still present, was it final click and success message appears?
                            if is_final_submit:
                                try:
                                    success_msg_xpath = "//*[contains(text(), 'Solicitud enviada') or contains(text(), 'Application sent') or contains(text(), 'applied') or contains(text(), 'aplicado')]"
                                    success_element = WebDriverWait(self.driver, 3).until(
                                        EC.visibility_of_element_located((By.XPATH, success_msg_xpath))
                                    )
                                    self.logger.info(f"SUCCESS! Confirmation message found: '{success_element.text}'.")
                                    return True
                                except TimeoutException:
                                    self.logger.warning(f"Clicked final '{button_text}' button, but modal still visible with no success message.")
                                    # Continue with next step instead of immediately failing
                            
                            # 3. If not final click or no confirmation, continue
                            try:
                                # Refresh modal reference
                                modal = WebDriverWait(self.driver, 5).until(
                                    EC.visibility_of_element_located((By.CSS_SELECTOR, modal_selector))
                                )
                                self.logger.debug("Modal still visible, continuing to next step.")
                            except:
                                self.logger.warning("Could not refresh modal reference")
                                break
                    except Exception as e:
                        self.logger.error(f"Error during button handling in step {step_counter}: {e}")
                        continue
                else:
                    self.logger.warning(f"No action button found in step {step_counter}")
                    # Check for any other interactive elements
                    try:
                        # Look for other interactive elements like checkboxes or dropdowns
                        interactive_elements = modal.find_elements(By.CSS_SELECTOR, "input[type='checkbox'], select")
                        if interactive_elements:
                            self.logger.info(f"Found {len(interactive_elements)} interactive elements")
                            # Try to interact with checkboxes
                            for elem in interactive_elements:
                                try:
                                    if elem.tag_name == "input" and elem.get_attribute("type") == "checkbox":
                                        if not elem.is_selected():
                                            self.logger.info("Checking checkbox")
                                            self.driver.execute_script("arguments[0].click();", elem)
                                    elif elem.tag_name == "select":
                                        self.logger.info("Selecting first option in dropdown")
                                        # Import Select if needed
                                        from selenium.webdriver.support.ui import Select
                                        select = Select(elem)
                                        select.select_by_index(1)  # Select first non-default option
                                except Exception as e:
                                    self.logger.warning(f"Error interacting with element: {e}")
                        else:
                            self.logger.warning("No additional interactive elements found")
                    except Exception as e:
                        self.logger.warning(f"Error looking for interactive elements: {e}")
                    
                    # If no buttons or interactive elements, try a drastic approach
                    try:
                        # Try to submit with Enter key
                        self.logger.info("Drastic attempt: Sending ENTER key")
                        from selenium.webdriver.common.keys import Keys
                        ActionChains(self.driver).send_keys(Keys.ENTER).perform()
                        time.sleep(2)
                    except Exception as e:
                        self.logger.warning(f"Error sending ENTER: {e}")
            
            # If max_steps exceeded
            self.logger.warning(f"Maximum step limit ({max_steps}) reached in modal.")
            return False

        except TimeoutException:
            self.logger.error("Timeout waiting for Easy Apply modal to appear.")
            self._take_debug_screenshot("error_modal_not_appearing")
            return False
        except Exception as modal_err:
             self.logger.error(f"Unexpected error handling modal: {modal_err}", exc_info=True)
             return False

    def _find_apply_button_with_retry(self) -> Tuple[Optional[WebElement], bool]:
        """
        Enhanced method to specifically find the apply/easy apply button
        with multiple strategies and retries.
        
        Returns:
            Tuple with (button element or None, is_easy_apply flag)
        """
        self.logger.info("Looking for apply button with enhanced strategies")
        
        # Capture state for debugging
        self._take_debug_screenshot("apply_button_search_start")
        
        # 1. Direct strategy - search by text or class
        button_xpaths = [
            "//button[contains(text(), 'Solicitud sencilla') or contains(., 'Solicitud sencilla')]",
            "//button[contains(text(), 'Easy Apply') or contains(., 'Easy Apply')]",
            "//button[contains(@class, 'jobs-apply-button')]",
            "//button[contains(@aria-label, 'Solicitud sencilla')]",
            "//button[contains(@aria-label, 'Easy Apply')]",
            "//button[contains(@data-control-name, 'jobs-apply-button')]",
            "//button[contains(@class, 'jobs-apply-button') and contains(@class, 'artdeco-button')]"
        ]
        
        for xpath in button_xpaths:
            try:
                buttons = self.driver.find_elements(By.XPATH, xpath)
                for button in buttons:
                    if button.is_displayed() and button.is_enabled():
                        self.logger.info(f"Button found with XPath: {xpath}")
                        return button, True
            except:
                continue
        
        # 2. JavaScript strategy specific for the easy apply button
        js_find_apply = """
        return (function() {
            // Find any button containing "solicitud sencilla" or "easy apply"
            const buttons = document.querySelectorAll('button');
            for (const btn of buttons) {
                if (!btn.offsetParent) continue; // Skip hidden buttons
                
                const btnText = btn.innerText.toLowerCase();
                const ariaLabel = (btn.getAttribute('aria-label') || '').toLowerCase();
                const btnClass = (btn.getAttribute('class') || '').toLowerCase();
                
                // Check if it's an apply button by text or class
                if (
                    btnText.includes('solicitud sencilla') || 
                    btnText.includes('easy apply') || 
                    ariaLabel.includes('solicitud sencilla') || 
                    ariaLabel.includes('easy apply') ||
                    btnClass.includes('jobs-apply-button')
                ) {
                    return {
                        element: btn,
                        text: btn.innerText
                    };
                }
            }
            
            // Look for more specific element shown in screenshot
            const applyContainer = document.querySelector('.jobs-unified-top-card__apply-container');
            if (applyContainer) {
                const btn = applyContainer.querySelector('button');
                if (btn && btn.offsetParent) {
                    return {
                        element: btn,
                        text: btn.innerText
                    };
                }
            }
            
            return null;
        })();
        """
        
        try:
            result = self.driver.execute_script(js_find_apply)
            if result and result.get('element'):
                button = result.get('element')
                text = result.get('text', '')
                self.logger.info(f"Button found with JavaScript: '{text}'")
                return button, True
        except Exception as e:
            self.logger.warning(f"Error in JS search: {e}")
        
        # 3. Final strategy: search in specific interface sections
        try:
            # Look in top action areas
            action_areas = [
                ".jobs-unified-top-card__actions",
                ".jobs-unified-top-card__apply-container",
                ".jobs-s-apply",
                ".jobs-details-top-card__actions"
            ]
            
            for selector in action_areas:
                try:
                    container = self.driver.find_element(By.CSS_SELECTOR, selector)
                    buttons = container.find_elements(By.TAG_NAME, "button")
                    
                    for button in buttons:
                        if button.is_displayed() and button.is_enabled():
                            btn_text = button.text.lower()
                            if "solicitud" in btn_text or "apply" in btn_text:
                                self.logger.info(f"Button found in action area: '{btn_text}'")
                                return button, True
                except:
                    continue
        except Exception as e:
            self.logger.warning(f"Error in action area search: {e}")
        
        # No button found
        self.logger.warning("No apply button found")
        self._take_debug_screenshot("apply_button_search_failure")
        return None, False

    def _find_apply_button_extreme(self) -> Tuple[Optional[WebElement], bool]:
        """
        Extreme method to find the apply button using all possible strategies,
        including DOM structure analysis and drastic approaches.
        
        Returns:
            Tuple with (button found or None, is_easy_apply flag)
        """
        page_url = self.driver.current_url
        job_id = re.search(r'/view/(\d+)', page_url)
        job_id = job_id.group(1) if job_id else "unknown"
        
        self.logger.info(f"EXTREME STRATEGY for finding apply button on job {job_id}")
        self._take_debug_screenshot(f"extreme_search_start_{job_id}")
        
        # First check if already applied
        try:
            already_applied_indicators = [
                "//li[contains(text(), 'Solicitado')]",
                "//span[contains(text(), 'Solicitud enviada')]",
                "//li[contains(@class, 'job-card-container__footer-item')][contains(text(), 'Solicitado')]",
                "//span[contains(@class, 'full-width')][contains(text(), 'Solicitud enviada')]",
                "//span[contains(text(), 'Applied')]",
                "//div[contains(@class, 'jobs-details-top-card__apply-state')]//span[contains(text(), 'Applied') or contains(text(), 'Solicitado')]"
            ]
            
            for indicator in already_applied_indicators:
                try:
                    applied_element = self.driver.find_element(By.XPATH, indicator)
                    applied_text = applied_element.text.strip()
                    self.logger.info(f"DETECTED! Job already applied: '{applied_text}'")
                    self._take_debug_screenshot(f"job_already_applied_{job_id}")
                    # Return None to indicate no further processing needed
                    return None, False
                except NoSuchElementException:
                    continue
        except Exception as e:
            self.logger.warning(f"Error checking if job is already applied: {e}")
        
        # Try first with the improved method
        apply_button, is_easy_apply = self._find_apply_button_with_retry()
        if apply_button:
            return apply_button, is_easy_apply
            
        # PHASE 1: Scroll and additional wait to ensure complete loading
        self.logger.info("Phase 1: Scroll to top and wait for complete loading")
        self.driver.execute_script("window.scrollTo(0, 0);")  # Scroll to top
        time.sleep(2)  # Allow page to stabilize
        
        # PHASE 1.5: Wait for key page elements to load
        try:
            # Wait for job title to load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 
                    ".jobs-unified-top-card__job-title, .job-details-jobs-unified-top-card__job-title"
                ))
            )
            self.logger.info("Job title loaded correctly")
        except Exception as e:
            self.logger.warning(f"Could not detect job title: {e}")
        
        # PHASE 2: Detection through analysis of known zones
        self.logger.info("Phase 2: Looking for main application panel")
        try:
            # Look for the application panel that typically contains the button
            panel_selectors = [
                ".jobs-unified-top-card__actions",
                ".jobs-s-apply",
                ".jobs-apply-button--top-card", 
                ".jobs-details-top-card__actions",
                ".jobs-unified-top-card__apply-container",
                ".jobs-apply-button",
                ".jobs-save-button ~ div"  # Panel near the save button
            ]
            
            for selector in panel_selectors:
                try:
                    panel = self.driver.find_element(By.CSS_SELECTOR, selector)
                    self.logger.info(f"Panel found: {selector}")
                    
                    # Look for button within panel
                    buttons = panel.find_elements(By.TAG_NAME, "button")
                    for btn in buttons:
                        try:
                            btn_text = btn.text.strip().lower()
                            btn_class = btn.get_attribute("class") or ""
                            btn_aria = btn.get_attribute("aria-label") or ""
                            
                            is_visible = btn.is_displayed() and btn.is_enabled()
                            
                            # Check if it's an apply button
                            easy_apply_keywords = ["easy apply", "solicitud sencilla"]
                            apply_keywords = ["apply", "solicitar", "solicitud"]
                            
                            if is_visible:
                                full_text = f"{btn_text} {btn_aria}".lower()
                                
                                if any(kw in full_text for kw in easy_apply_keywords) or "easy-apply" in btn_class:
                                    self.logger.info(f"'Easy Apply' button found in panel. Text: '{btn_text}'")
                                    return btn, True  # It's Easy Apply
                                elif any(kw in full_text for kw in apply_keywords) and not any(kw in full_text for kw in ["applied", "save", "guardar"]):
                                    self.logger.info(f"Standard 'Apply' button found in panel. Text: '{btn_text}'")
                                    return btn, False  # It's standard Apply
                        except Exception as btn_err:
                            continue
                except NoSuchElementException:
                    continue
                except Exception as panel_err:
                    self.logger.debug(f"Error analyzing panel {selector}: {panel_err}")
        except Exception as e:
            self.logger.warning(f"Error in phase 2: {e}")
        
        # PHASE 3: Search for buttons by ID (highly specific)
        self.logger.info("Phase 3: Search by specific ID")
        try:
            id_selectors = [
                "jobs-apply-button",
                "ember[0-9]+",  # Dynamically generated IDs by Ember.js
                "job-details-jobs-unified-top-card__apply-button"
            ]
            
            for id_pattern in id_selectors:
                try:
                    # Use XPath for ID patterns
                    if '[0-9]+' in id_pattern:
                        buttons = self.driver.find_elements(By.XPATH, f"//button[contains(@id, '{id_pattern.replace('[0-9]+', '')}')]")
                    else:
                        buttons = self.driver.find_elements(By.ID, id_pattern)
                    
                    for button in buttons:
                        if button.is_displayed() and button.is_enabled():
                            button_text = button.text.strip()
                            self.logger.info(f"Button found by ID. Text: '{button_text}'")
                            
                            # Determine if it's Easy Apply based on text or attributes
                            is_easy_apply = False
                            if "solicitud sencilla" in button_text.lower() or "easy apply" in button_text.lower():
                                is_easy_apply = True
                            elif button.get_attribute("aria-label") and ("solicitud sencilla" in button.get_attribute("aria-label").lower() or 
                                                                      "easy apply" in button.get_attribute("aria-label").lower()):
                                is_easy_apply = True
                            elif "easy-apply" in (button.get_attribute("class") or ""):
                                is_easy_apply = True
                                
                            self._take_debug_screenshot(f"button_found_by_id_{job_id}")
                            return button, is_easy_apply
                except Exception as id_err:
                    continue
        except Exception as e:
            self.logger.warning(f"Error in ID search: {e}")
        
        # PHASE 4: Search using advanced JavaScript
        self.logger.info("Phase 4: Advanced JavaScript analysis")
        try:
            js_script = """
            return (function() {
                // Specific texts to look for in buttons (case insensitive)
                const easyApplyTexts = ['easy apply', 'solicitud sencilla', 'aplicación sencilla'];
                const applyTexts = ['apply', 'solicitar', 'aplicar', 'applica'];
                
                // Helper function to check if an element is visible
                function isVisible(el) {
                    if (!el) return false;
                    if (window.getComputedStyle(el).display === 'none') return false;
                    if (window.getComputedStyle(el).visibility === 'hidden') return false;
                    if (el.offsetParent === null && el.tagName !== 'BODY') return false;
                    return true;
                }
                
                // 1. First look for buttons with specific LinkedIn classes
                const classPatterns = ['jobs-apply-button', 'artdeco-button', 'job-details-jobs-unified-top-card__apply-button'];
                for (const pattern of classPatterns) {
                    const buttons = document.querySelectorAll(`button[class*="${pattern}"]`);
                    for (const btn of buttons) {
                        if (!isVisible(btn)) continue;
                        
                        // Check button text and attributes
                        const btnText = (btn.innerText || '').toLowerCase();
                        const ariaLabel = (btn.getAttribute('aria-label') || '').toLowerCase();
                        const btnClass = (btn.getAttribute('class') || '').toLowerCase();
                        
                        // Check if it's Easy Apply
                        if (easyApplyTexts.some(t => btnText.includes(t) || ariaLabel.includes(t)) || 
                            btnClass.includes('easy-apply')) {
                            return {
                                element: btn,
                                isEasyApply: true,
                                text: btn.innerText
                            };
                        }
                        // Check if it's normal Apply (avoid "Applied" or "Save" buttons)
                        else if (applyTexts.some(t => btnText.includes(t) || ariaLabel.includes(t)) && 
                                !btnText.includes('applied') && !btnText.includes('save') && 
                                !btnText.includes('guardar')) {
                            return {
                                element: btn,
                                isEasyApply: false,
                                text: btn.innerText
                            };
                        }
                    }
                }
                
                // 2. Look in specific action containers
                const actionContainers = [
                    '.jobs-unified-top-card__actions',
                    '.jobs-details-top-card__actions',
                    '.jobs-s-apply',
                    '.job-view-layout',
                    '.jobs-details__main-content'
                ];
                
                for (const containerSelector of actionContainers) {
                    const container = document.querySelector(containerSelector);
                    if (!container) continue;
                    
                    const buttons = container.querySelectorAll('button');
                    for (const btn of buttons) {
                        if (!isVisible(btn)) continue;
                        
                        const btnText = (btn.innerText || '').toLowerCase();
                        const ariaLabel = (btn.getAttribute('aria-label') || '').toLowerCase();
                        
                        // Specifically check for text indicating application
                        if (easyApplyTexts.some(t => btnText.includes(t) || ariaLabel.includes(t))) {
                            return {
                                element: btn,
                                isEasyApply: true,
                                text: btn.innerText
                            };
                        } 
                        else if (applyTexts.some(t => btnText.includes(t) || ariaLabel.includes(t)) && 
                                !btnText.includes('applied') && !btnText.includes('save')) {
                            return {
                                element: btn,
                                isEasyApply: false,
                                text: btn.innerText
                            };
                        }
                    }
                }
                
                // 3. More generic search: any visible button with relevant text
                const allButtons = document.querySelectorAll('button');
                for (const btn of allButtons) {
                    if (!isVisible(btn)) continue;
                    
                    const btnText = (btn.innerText || '').toLowerCase();
                    const ariaLabel = (btn.getAttribute('aria-label') || '').toLowerCase();
                    
                    if (easyApplyTexts.some(t => btnText.includes(t) || ariaLabel.includes(t))) {
                        return {
                            element: btn,
                            isEasyApply: true,
                            text: btn.innerText
                        };
                    } 
                    else if (applyTexts.some(t => btnText.includes(t) || ariaLabel.includes(t)) && 
                            !btnText.includes('applied') && !btnText.includes('save') && 
                            !btnText.includes('guardar')) {
                        return {
                            element: btn,
                            isEasyApply: false,
                            text: btn.innerText
                        };
                    }
                }
                
                return null;
            })();
            """
            
            result = self.driver.execute_script(js_script)
            if result:
                button_element = result.get("element")
                is_easy_apply = result.get("isEasyApply", False)
                button_text = result.get("text", "")
                self.logger.info(f"Button found with JavaScript. Text: '{button_text}', EasyApply: {is_easy_apply}")
                return button_element, is_easy_apply
            else:
                self.logger.warning("No button found with advanced JavaScript")
        except Exception as js_err:
            self.logger.warning(f"Error in JavaScript search: {js_err}")
        
        # PHASE 5: Find absolutely ALL buttons on the page and analyze them
        self.logger.info("Phase 5: Exhaustive analysis of all buttons on page")
        try:
            all_buttons = self.driver.find_elements(By.TAG_NAME, "button")
            self.logger.info(f"Found {len(all_buttons)} buttons total")
            
            # Analyze each button looking for clues
            easy_apply_candidates = []
            apply_candidates = []
            
            for btn in all_buttons:
                try:
                    # Gather all possible information about the button
                    btn_text = btn.text.strip().lower()
                    btn_class = btn.get_attribute("class") or ""
                    btn_id = btn.get_attribute("id") or ""
                    btn_aria_label = btn.get_attribute("aria-label") or ""
                    
                    # Check if it's visible
                    is_visible = False
                    try:
                        is_visible = btn.is_displayed() and btn.is_enabled()
                    except:
                        pass
                    
                    # Debug logging
                    if btn_text or "apply" in btn_class or "apply" in btn_id or "apply" in btn_aria_label:
                        self.logger.debug(f"Button: text='{btn_text}', class='{btn_class}', id='{btn_id}', aria='{btn_aria_label}', visible={is_visible}")
                    
                    # Calculate score for each button
                    score = 0
                    
                    # Check if it's a candidate for Easy Apply
                    easy_apply_indicators = ["solicitud sencilla", "easy apply", "jobs-apply-button", "linkedin"]
                    if any(indicator in btn_text or indicator in btn_class or indicator in btn_id or indicator in btn_aria_label 
                           for indicator in easy_apply_indicators) and is_visible:
                        # Calculate score based on how many indicators match
                        for indicator in easy_apply_indicators:
                            if indicator in btn_text:
                                score += 5  # Higher weight for visible text
                            if indicator in btn_aria_label:
                                score += 4  # Good indicator
                            if indicator in btn_class:
                                score += 3  # Moderate indicator
                            if indicator in btn_id:
                                score += 3  # Moderate indicator
                        
                        # Bonus for position (action buttons are usually at the top)
                        try:
                            y_position = btn.location['y']
                            if y_position < 500:  # Typically visible without scrolling
                                score += 2
                        except:
                            pass
                            
                        self.logger.info(f"Easy Apply candidate: '{btn_text or btn_aria_label}' with score {score}")
                        easy_apply_candidates.append((btn, score))
                    elif "apply" in btn_text or "solicitar" in btn_text or "solicitud" in btn_text or "apply" in btn_aria_label:
                        # Similar to above but for normal Apply buttons
                        if "save" not in btn_text and "guardar" not in btn_text and "applied" not in btn_text and is_visible:
                            # Calculate score
                            if "apply" in btn_text or "solicitar" in btn_text:
                                score += 3
                            if "apply" in btn_aria_label:
                                score += 2
                            if "apply" in btn_class:
                                score += 1
                                
                            try:
                                y_position = btn.location['y']
                                if y_position < 500:
                                    score += 1
                            except:
                                pass
                                
                            self.logger.info(f"Normal Apply candidate: '{btn_text or btn_aria_label}' with score {score}")
                            apply_candidates.append((btn, score))
                except Exception as e:
                    continue
            
            # Sort candidates by score (descending)
            easy_apply_candidates.sort(key=lambda x: x[1], reverse=True)
            apply_candidates.sort(key=lambda x: x[1], reverse=True)
            
            # Return the most likely Easy Apply button if available
            if easy_apply_candidates:
                best_button, score = easy_apply_candidates[0]
                self.logger.info(f"Selected best Easy Apply candidate: '{best_button.text.strip() or best_button.get_attribute('aria-label')}' (score: {score})")
                self._take_debug_screenshot(f"best_easy_apply_candidate_{job_id}")
                return best_button, True
                
            # If no Easy Apply buttons, try normal Apply
            if apply_candidates:
                best_button, score = apply_candidates[0]
                self.logger.info(f"Selected best normal Apply candidate: '{best_button.text.strip() or best_button.get_attribute('aria-label')}' (score: {score})")
                self._take_debug_screenshot(f"best_apply_candidate_{job_id}")
                return best_button, False
        except Exception as e:
            self.logger.error(f"Error in exhaustive analysis: {e}")
        
        # If all strategies fail, no button could be found
        self.logger.error("All extreme strategies failed, no apply button found")
        self._take_debug_screenshot(f"all_strategies_failed_{job_id}")
        return None, False

    def get_recruiter_info(self) -> Dict[str, Optional[str]]:
        """
        Extract recruiter/hiring team information from the current job page.
        
        Returns:
            Dictionary with recruiter name and title
        """
        recruiter_info = {
            "name": None,
            "title": None
        }
        
        try:
            # Look for hiring team section
            hiring_team_selectors = [
                "//h2[contains(text(), 'Conoce al equipo de contratación')]",
                "//h2[contains(text(), 'hiring team')]",
                ".job-details-people-who-can-help__section",
                ".job-details-connections-card",
                ".jobs-company__box",
                ".jobs-details-job-summary__text"
            ]
            
            for selector in hiring_team_selectors:
                try:
                    if selector.startswith("//"):
                        team_section = self.driver.find_element(By.XPATH, selector)
                    else:
                        team_section = self.driver.find_element(By.CSS_SELECTOR, selector)
                    
                    self.logger.info(f"Hiring team section found: {selector}")
                    
                    # Find the first recruiter name
                    try:
                        # First try with direct container
                        recruiter_container = None
                        try:
                            recruiter_container = team_section.find_element(By.XPATH, "./following-sibling::div[1]") or team_section
                        except:
                            recruiter_container = team_section
                        
                        # Look for the name
                        name_selectors = [
                            ".//strong", 
                            ".//span[contains(@class, 'bold')]",
                            ".//span[contains(@class, 't-bold')]",
                            ".//a[contains(@class, 'app-aware-link')]//strong",
                            ".//a[contains(@class, 'app-aware-link')]"
                        ]
                        
                        for name_selector in name_selectors:
                            try:
                                name_element = recruiter_container.find_element(By.XPATH, name_selector)
                                recruiter_info["name"] = name_element.text.strip()
                                self.logger.info(f"Recruiter name found: {recruiter_info['name']}")
                                break
                            except:
                                continue
                        
                        # Look for the title
                        title_selectors = [
                            ".//span[contains(@class, 'text--low-emphasis')]",
                            ".//span[contains(@class, 't-14')]",
                            ".//span[contains(@class, 'tvm_text')]",
                            ".//span[contains(@class, 'text-body-small')]"
                        ]
                        
                        for title_selector in title_selectors:
                            try:
                                title_element = recruiter_container.find_element(By.XPATH, title_selector)
                                recruiter_info["title"] = title_element.text.strip()
                                self.logger.info(f"Recruiter title found: {recruiter_info['title']}")
                                break
                            except:
                                continue
                        
                        # If we found at least the name, we're done
                        if recruiter_info["name"]:
                            return recruiter_info
                    except Exception as e:
                        self.logger.warning(f"Error extracting recruiter data: {e}")
                        
                    # If we found the section but not the content, try another section
                    break
                except NoSuchElementException:
                    continue
        except Exception as e:
            self.logger.warning(f"Error looking for recruiter info: {e}")
        
        # As a last resort, look for any featured profile
        try:
            profile_selectors = [
                ".jobs-poster__name",
                ".jobs-poster-package__name",
                ".jobs-unified-top-card__posted-by a"
            ]
            
            for selector in profile_selectors:
                try:
                    profile = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if profile.is_displayed():
                        recruiter_info["name"] = profile.text.strip()
                        self.logger.info(f"Recruiter name found via alternative selector: {recruiter_info['name']}")
                        break
                except:
                    continue
        except Exception as e:
            self.logger.debug(f"Error in alternative recruiter search: {e}")
        
        return recruiter_info

    def check_if_cover_letter_needed(self) -> bool:
        """
        Return whether the application process will need a cover letter
        based on the latest detection in the application process.
        
        Returns:
            bool: True if cover letter is needed
        """
        return self.cover_letter_needed

    def apply(self, job_url: str, cover_letter: Optional[str] = None, resume_path: Optional[str] = None) -> bool:
        """
        Attempt to apply to a LinkedIn job through its URL.
        Detects if already applied, if there's a recruiter, and if cover letter is needed.
        
        Args:
            job_url: URL of the job listing
            cover_letter: Cover letter text (optional)
            resume_path: Path to resume file
            
        Returns:
            bool: True if application was successful, False otherwise
        """
        # Reset cover letter needed flag
        self.cover_letter_needed = False
        
        self.logger.info(f"Attempting to apply for job: {job_url}")
        try:
            # Add variable delay before navigating to simulate human behavior
            delay = random.uniform(2, 4)
            time.sleep(delay)
            
            self.driver.get(job_url)
            # Wait for page to load completely
            self._wait_for_page_load(timeout=10)
            
            # --- Wait for page load with multiple indicators ---
            container_selectors = [
                ".jobs-details__main-content", 
                "#job-details", 
                ".job-view-layout", 
                ".jobs-details-top-card",
                ".jobs-unified-top-card"
            ]
            
            container_found = False
            for i, selector in enumerate(container_selectors):
                try:
                    self.logger.debug(f"Waiting for selector #{i+1}: {selector}")
                    WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    self.logger.info(f"Page loaded, selector found: {selector}")
                    container_found = True
                    break
                except TimeoutException:
                    self.logger.debug(f"Selector #{i+1} not found")
            
            if not container_found:
                # Check for 429 error
                if "429" in self.driver.page_source or "many requests" in self.driver.page_source.lower():
                    self.logger.error("DETECTED 429 ERROR: Too many requests to LinkedIn")
                    self._take_debug_screenshot("429_error_detected")
                    return False
                    
                self.logger.warning("No known container found, attempting to continue anyway")
            
            # Extra time to ensure complete load (even without container)
            self.logger.info("Waiting additional time for complete load...")
            delay = random.uniform(1.5, 3)
            time.sleep(delay)
            
            # Take initial screenshot
            self._take_debug_screenshot(f"page_loaded_{job_url.split('/')[-1]}")
            
            # Ensure focus is on the page (avoid scroll issues)
            self.driver.execute_script("window.focus();")
            
            # Ensure we're viewing the correct part of the page
            self.driver.execute_script("window.scrollTo(0, 0);")  # Scroll to top
            time.sleep(0.5)
            
            # EXTREME STRATEGY to find button
            apply_button, is_easy_apply = self._find_apply_button_extreme()
            
            # If no button or None (already applied), return
            if apply_button is None:
                self.logger.info("Job already applied or no detectable button.")
                return False
            
            if is_easy_apply:
                self.logger.info("SUCCESS! 'Easy Apply' button found with extreme strategy")
                
                # Try to scroll to button to ensure visibility
                try:
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", apply_button)
                    time.sleep(0.5)
                except Exception as e:
                    self.logger.warning(f"Error scrolling to button: {e}")
                
                # Take screenshot before click
                self._take_debug_screenshot("before_easy_apply_click")
                
                # MULTIPLE CLICK STRATEGY
                click_methods = [
                    ("Normal", lambda btn: btn.click()),
                    ("JavaScript", lambda btn: self.driver.execute_script("arguments[0].click();", btn)),
                    ("ActionChains", lambda btn: ActionChains(self.driver).move_to_element(btn).pause(0.5).click().perform()),
                    ("Forced JavaScript", lambda btn: self.driver.execute_script(
                        "arguments[0].dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true, view: window}));", 
                        btn
                    ))
                ]
                
                click_success = False
                for method_name, click_method in click_methods:
                    if click_success:
                        break
                        
                    try:
                        self.logger.info(f"Attempting click with method: {method_name}")
                        click_method(apply_button)
                        self.logger.info(f"Click with method {method_name} apparently successful")
                        click_success = True
                        
                        # Brief wait to confirm
                        time.sleep(1)
                        self._take_debug_screenshot(f"after_click_{method_name}")
                        
                        # Check if modal appeared
                        try:
                            modal_selector = "div[aria-labelledby*='easy-apply-modal-title'], div.jobs-easy-apply-modal"
                            modal = WebDriverWait(self.driver, 3).until(
                                EC.visibility_of_element_located((By.CSS_SELECTOR, modal_selector))
                            )
                            self.logger.info(f"Modal detected after click with {method_name}. CLICK SUCCESSFUL!")
                            break
                        except TimeoutException:
                            self.logger.warning(f"Modal didn't appear after click with {method_name}, may have failed")
                            click_success = False
                    except Exception as e:
                        self.logger.warning(f"Error with click method {method_name}: {e}")
                
                # If no click method succeeded, or modal doesn't appear
                if not click_success:
                    self.logger.error("All click methods failed")
                    return False
                
                # If we're here, click was successful, handle the modal
                return self._handle_easy_apply_modal(resume_path, cover_letter)
            else:
                self.logger.info("'Apply' (standard) button found. Requires manual application.")
                self._take_debug_screenshot("standard_apply_button")
                return False  # Indicates Manual Review
                
        except TimeoutException:
            self.logger.error(f"Timeout loading job page {job_url}", exc_info=True)
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error applying to {job_url}: {e}", exc_info=True)
            self._take_debug_screenshot(f"unexpected_error_{job_url.split('/')[-1]}")
            return False