"""
Main execution module for the LinkedIn job application bot.

This module contains the primary logic for searching and applying to jobs on LinkedIn,
with features for rate limiting, cover letter generation, and detailed logging.
"""

import os
import logging
import time
import random
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from .config import config
from .utils.logger import setup_logger
from .fetcher.linkedin_fetcher import LinkedInFetcher, JobListing, human_delay
from .generator.cover_letter import CoverLetterGenerator
from .automator.browser_automator import BrowserAutomator
from .db.models import init_db, get_db, JobApplication, ApplicationStatus

# --- Configuration & Constants ---
SEARCH_KEYWORDS = '"Machine Learning Engineer" OR "AI Engineer" OR "Artificial Intelligence Engineer" OR "Generative AI Developer" OR "RAG Specialist" OR "NLP Engineer"'
SEARCH_LOCATION = "Remote"
COVER_LETTER_TRIGGERS = ["rag", "retrieval-augmented generation", "generative ai", "llm", "large language model", "fine-tuning"]
SKIP_JOB_TITLE_KEYWORDS = ["junior", "jr.", "entry level", "intern", "internship"]
TIME_FILTER = "week"  # Options: "week" (last week), "day" (last 24h), "month" (last month)

# Rate limiting configuration
MAX_JOBS_TO_PROCESS = 40  # Limit to 40 jobs per execution
MAX_JOBS_PER_SESSION = 15  # Maximum jobs to process before restarting browser
MIN_JOB_PROCESSING_TIME = 30  # Minimum time (seconds) to process each job
MAX_SESSION_DURATION = 40 * 60  # Maximum session duration (40 minutes) before restart

# --- Helper Functions ---
def should_generate_cover_letter(job_description: Optional[str]) -> bool:
    """Determine if cover letter should be generated based on job description keywords."""
    if not job_description: 
        return False
    description_lower = job_description.lower()
    return any(trigger in description_lower for trigger in COVER_LETTER_TRIGGERS)

def should_skip_job(job_title: Optional[str]) -> bool:
    """Check if job should be skipped based on title keywords."""
    if not job_title: 
        return False
    title_lower = job_title.lower()
    return any(skip_keyword in title_lower for skip_keyword in SKIP_JOB_TITLE_KEYWORDS)

def add_random_delay(min_sec: float = 1.0, max_sec: float = 3.0, message: Optional[str] = None, logger = None) -> None:
    """Add a random delay with optional log message."""
    delay = random.uniform(min_sec, max_sec)
    if message and logger:
        logger.info(f"{message} ({delay:.2f}s)")
    time.sleep(delay)

# --- Debug Environment Setup ---
def setup_debug_environment():
    """Set up environment for debugging, creating necessary directories."""
    debug_dirs = ["debug_screenshots", "logs"]
    for dir_name in debug_dirs:
        if not os.path.exists(dir_name):
            os.makedirs(dir_name)
            print(f"Created directory: {dir_name}")

# --- Rate Limiting ---
class RateLimiter:
    """Manages rate limits to avoid LinkedIn restrictions."""
    
    def __init__(self, logger):
        self.logger = logger
        self.last_request_time = time.time()
        self.error_429_count = 0
        self.session_job_count = 0
        self.session_start_time = time.time()
        self.cooldown_active = False
        self.cooldown_until = 0
        self.consecutive_errors = 0
        self.using_fallback_strategy = False
    
    def before_job_processing(self) -> bool:
        """Implement optimized delays and limits before processing a job."""
        now = time.time()
        
        # Check if in cooldown period
        if self.cooldown_active:
            if now < self.cooldown_until:
                remaining = int(self.cooldown_until - now)
                self.logger.info(f"In cooldown period. {remaining}s remaining.")
                return False
            else:
                self.logger.info("Cooldown period ended.")
                self.cooldown_active = False
                self.error_429_count = 0
        
        # Check session limits
        self.session_job_count += 1
        session_duration = now - self.session_start_time
        
        if self.session_job_count >= MAX_JOBS_PER_SESSION:
            self.logger.info(f"Reached session job limit ({MAX_JOBS_PER_SESSION})")
            return False
            
        if session_duration > MAX_SESSION_DURATION:
            self.logger.info(f"Reached maximum session duration ({MAX_SESSION_DURATION/60:.1f}min)")
            return False
            
        # Ensure minimum time between jobs
        time_since_last = now - self.last_request_time
        if time_since_last < MIN_JOB_PROCESSING_TIME:
            delay_needed = MIN_JOB_PROCESSING_TIME - time_since_last
            self.logger.info(f"Adding delay of {delay_needed:.2f}s to meet minimum time between jobs")
            time.sleep(delay_needed)
        
        # Add randomized delay
        human_delay(0.5, 1.5)
        
        # Update last request time
        self.last_request_time = time.time()
        return True
    
    def handle_429_error(self) -> bool:
        """Handle 429 (Too Many Requests) errors with optimized strategy."""
        self.error_429_count += 1
        self.consecutive_errors += 1
        
        # Aggressive strategy for consecutive errors
        if self.consecutive_errors >= 3:
            cooldown_minutes = 10
            self.cooldown_active = True
            self.cooldown_until = time.time() + (cooldown_minutes * 60)
            self.logger.warning(f"Too many consecutive errors. Pausing for {cooldown_minutes} minutes.")
            return False
        
        # Normal strategy for sporadic errors
        if self.error_429_count >= 5:
            cooldown_minutes = 5 + (self.error_429_count * 2)
            self.cooldown_active = True
            self.cooldown_until = time.time() + (cooldown_minutes * 60)
            self.logger.warning(f"Too many 429 errors. Activating cooldown for {cooldown_minutes} minutes.")
            return False
        
        # Incremental wait time
        wait_time = 30 * self.consecutive_errors  # 30s, 60s, 90s...
        self.logger.warning(f"429 error detected. Waiting {wait_time}s before retry.")
        time.sleep(wait_time)
        return True
    
    def reset_session(self):
        """Reset session counters."""
        self.session_job_count = 0
        self.session_start_time = time.time()
        self.consecutive_errors = 0
        self.logger.info("Session counters reset.")
    
    def success(self):
        """Call when an operation succeeds to reset error counters."""
        self.consecutive_errors = 0

# --- Main Execution Logic ---
def main() -> None:
    """Main function to run the LinkedIn job application bot."""
    # Debug environment setup
    setup_debug_environment()
    
    logger = setup_logger(__name__, config.LOG_LEVEL, log_to_file=True, log_file="logs/bot_activity.log")
    logger.info("=====================================================")
    logger.info("Starting bot - Enhanced Logic (With Time Filter)")
    logger.info(f"Date and time: {datetime.now()}")
    logger.info("=====================================================")

    # --- User Profile Data ---
    user_profile: Dict[str, Any] = {
        "full_name": "Juan Navarro", 
        "role": "Machine Learning Engineer | Generative AI & RAG Specialist",
        "summary": "AI & ML Engineer with 2+ years specializing in Generative AI, Retrieval-Augmented Generation (RAG), and LLM Fine-Tuning. Passionate about creating innovative, scalable AI solutions leveraging both cloud APIs and local deployments to optimize resources, enhance data privacy, and maximize performance. Natural leader with exceptional creativity and rapid adaptability.",
        "skills": { 
            "ml_nlp": "RAG (Retrieval-Augmented Generation), GPT/BERT/LLAMA Fine-Tuning, Sentiment Analysis, Embeddings, Conversational AI",
            "frameworks_programming": "Python (Advanced), Rust (Learning), JavaScript, TensorFlow, PyTorch, Keras, Hugging Face Transformers, FastAPI, Flask, React",
            "cloud_devops_mlops": "Google Cloud AI, Azure AI, Firebase, Docker, GitHub Actions, CI/CD pipelines, basic Kubernetes knowledge",
            "databases_vector_stores": "PostgreSQL, MongoDB, FAISS, Pinecone (basic)" 
        },
        "experience_highlights": [
            "Led development of RAG-based chatbots...", 
            "Integrated LLMs (GPT-3.5/4) and FAISS...", 
            "Built AI-powered academic writing platform...", 
            "Engineered ML pipelines...", 
            "Coordinated small teams..."
        ],
        "current_project": "Developing UpgradeBots: an ambitious RAG-based educational platform...",
        "soft_skills": "Natural leader, exceptional creativity, rapid adaptability, proactive approach, strong practical experience.",
        "seeking": "Seeking fully remote opportunities in Generative AI & ML.",
        "contact": { 
            "email": "juan.navarrom97@gmail.com", 
            "phone": "+34 608 493 139", 
            "linkedin": "linkedin.com/in/juan-navarro-muñoz", 
            "github": "JuanNavarr0" 
        }
    }
    logger.info("User profile loaded.")

    # --- Resume Path (Relative) ---
    cv_folder = "cv"
    cv_filename = "Juan_Navarro_Machine_Learning_Engineer.pdf"
    relative_cv_path = os.path.join(cv_folder, cv_filename)
    resume_file_path: Optional[str] = os.path.abspath(relative_cv_path)
    
    if not os.path.exists(resume_file_path):
        logger.warning(f"WARNING: Resume not found at '{relative_cv_path}'.")
        resume_file_path = None
    else:
        logger.info(f"Resume path set (relative base): '{relative_cv_path}'")

    # --- Initialize Components ---
    fetcher = None
    automator = None
    driver = None
    rate_limiter = RateLimiter(logger)
    
    try:
        try:
            from datetime import timezone
            utc_now = lambda: datetime.now(timezone.utc)
        except ImportError:
            import pytz
            utc_now = lambda: datetime.now(pytz.utc)
            
        processed_count = 0
        applied_count = 0
        manual_count = 0
        skipped_count = 0
        error_count = 0
        initial_job_listings: List[JobListing] = []

        init_db(config)
        logger.info("Database initialized.")
        
        def initialize_browser():
            """Initialize or restart browser and related components."""
            nonlocal fetcher, driver, automator
            
            # Close previous session if exists
            if fetcher and fetcher.driver:
                logger.info("Closing previous session...")
                try:
                    fetcher.close()
                except:
                    pass
                    
            # Start new session
            logger.info("Initializing Fetcher (WebDriver and Login)...")
            fetcher = LinkedInFetcher(config)
            try: 
                fetcher._initialize_driver()
                driver = fetcher.driver
                add_random_delay(3, 5, "Waiting before login...", logger)
                fetcher._login()
                logger.info("Login successful.")
                
                if driver: 
                    automator = BrowserAutomator(driver, config)
                    logger.info("Automator initialized.")
                else: 
                    logger.error("Critical failure: WebDriver not available.")
                    raise RuntimeError("WebDriver failed.")
                    
                # Reset session counters
                rate_limiter.reset_session()
                
                return True
            except Exception as e: 
                logger.error(f"Initialization/login failure: {e}", exc_info=True)
                return False
        
        # Perform initial initialization
        if not initialize_browser():
            logger.error("Could not initialize browser. Aborting.")
            return

        # Initialize cover letter generator if API key available
        generator = None
        if config.OPENAI_API_KEY:
            generator = CoverLetterGenerator(config)
            if generator.client:
                logger.info("Cover letter generator initialized (OpenAI).")
            else:
                logger.warning("Generator configured, but OpenAI client failed.")
                generator = None
        else:
            logger.info("OpenAI API Key not found, generator disabled.")

        # Set up search criteria
        search_criteria = {
            "keywords": SEARCH_KEYWORDS, 
            "location": SEARCH_LOCATION,
            "time_filter": TIME_FILTER
        }
        logger.info(f"Using criteria: Keywords='{SEARCH_KEYWORDS}', Location='{SEARCH_LOCATION}', Time='{TIME_FILTER}'")
        logger.info("Searching for jobs (basic scraping)...")
        
        # Add pause before search
        add_random_delay(2, 4, "Waiting before search...", logger)
        
        # Perform initial job search
        initial_job_listings = fetcher.search_jobs(search_criteria)

        if not initial_job_listings: 
            logger.warning("No initial job listings found or scraping failed.")
        else: 
            logger.info(f"Basic scraping OK. {len(initial_job_listings)} jobs to process.")

        if initial_job_listings:
            # Limit quantity for testing if needed
            jobs_to_process = initial_job_listings[:MAX_JOBS_TO_PROCESS]
            if len(initial_job_listings) > MAX_JOBS_TO_PROCESS:
                logger.info(f"Limiting to {MAX_JOBS_TO_PROCESS} jobs to process")
            
            with get_db() as db_session:
                for job_index, job_basic_info in enumerate(jobs_to_process):
                    # Check if we should continue or restart session
                    if not rate_limiter.before_job_processing():
                        logger.info("Rate limiter suggests restarting session.")
                        initialize_browser()
                        # Reset counter but preserve DB session
                        rate_limiter.reset_session()
                        # Ensure sufficient pause after restart
                        add_random_delay(5, 10, "Post-restart pause...", logger)
                
                    # Process each job in its own try/except to continue with the next job
                    # even if there's a failure in one job
                    try:
                        processed_count += 1
                        logger.info(f"--- Processing {processed_count}/{len(jobs_to_process)}: {job_basic_info.title} at {job_basic_info.company} ---")
                        
                        application_record = None
                        cover_letter_text: Optional[str] = None
                        apply_success = False
                        final_status = ApplicationStatus.PENDING
                        application_notes = ""
                        recruiter_info = {"name": None, "title": None}

                        # --- Check if URL is valid ---
                        if not job_basic_info.url: 
                            logger.warning("Invalid URL. Skipping.")
                            skipped_count += 1
                            continue
                        
                        # --- Check if job is already in database ---
                        existing_app = db_session.query(JobApplication).filter(JobApplication.job_url == job_basic_info.url).first()
                        if existing_app: 
                            logger.warning(f"Already in DB (Status: {existing_app.status.value}). Skipping.")
                            skipped_count += 1
                            continue
                        
                        # --- Check if job has already been applied to (according to LinkedIn) ---
                        if job_basic_info.already_applied:
                            logger.warning(f"Job already applied according to LinkedIn. Skipping.")
                            final_status = ApplicationStatus.APPLIED
                            application_notes = "Detected as already applied (according to LinkedIn)"
                            skipped_count += 1
                            
                            # Save in DB as already applied
                            application_record = JobApplication(
                                linkedin_job_id=job_basic_info.linkedin_job_id,
                                job_title=job_basic_info.title, 
                                company_name=job_basic_info.company,
                                job_url=job_basic_info.url, 
                                location=job_basic_info.location,
                                status=final_status, 
                                notes=application_notes,
                                cover_letter_generated=False,
                                application_date=utc_now()
                            )
                            db_session.add(application_record)
                            db_session.commit()
                            continue
                        
                        # --- Check if title indicates we should skip (junior, etc.) ---
                        if should_skip_job(job_basic_info.title):
                            logger.info(f"Skipping based on title ('{job_basic_info.title}').")
                            final_status = ApplicationStatus.SKIPPED
                            application_notes = "Skipped based on title (Junior)"
                            skipped_count += 1
                        else:
                            # --- Get detailed job description ---
                            logger.info("Getting detailed description...")
                            job_description = None
                            
                            # Add humanized delay before requesting details
                            add_random_delay(2, 4, "Waiting before requesting details...", logger)
                            
                            try:
                                job_description = fetcher.get_job_details(job_basic_info.url)
                                
                                # Check for empty response
                                if job_description == "":
                                    raise ValueError("Empty response from get_job_details")
                                    
                            except Exception as desc_e:
                                # Specifically check for 429 error
                                if "429" in str(desc_e) or hasattr(fetcher.driver, 'page_source') and "429" in fetcher.driver.page_source:
                                    logger.error("429 error detected when getting description")
                                    # Let rate_limiter handle the error
                                    if not rate_limiter.handle_429_error():
                                        # If it indicates we should restart session
                                        initialize_browser()
                                        # Retry this same job after restart
                                        job_index -= 1
                                        continue
                                else:
                                    logger.error(f"Error getting description: {desc_e}")
                                
                                job_description = None
                            
                            if not job_description: 
                                logger.error("Could not get description.")
                                final_status = ApplicationStatus.ERROR
                                application_notes = "Failed to get description"
                                error_count += 1
                            else:
                                # --- Description obtained, process the job ---
                                logger.info("Description obtained.")
                                job_basic_info.description = job_description
                                
                                # --- Look for recruiter information ---
                                try:
                                    recruiter_info = fetcher.get_recruiter_info(job_basic_info.url)
                                    if recruiter_info["name"]:
                                        logger.info(f"Recruiter detected: {recruiter_info['name']} ({recruiter_info['title'] or 'No title'})")
                                    else:
                                        logger.info("No recruiter information detected")
                                except Exception as rec_err:
                                    logger.warning(f"Error looking for recruiter information: {rec_err}")
                                
                                # --- Try to apply to the job first to see if cover letter is needed ---
                                if automator:
                                    logger.info("Attempting to apply (Automator)...")
                                    
                                    # Add humanized delay before applying
                                    add_random_delay(2, 3, "Waiting before attempting to apply...", logger)
                                    
                                    try:
                                        # First try without cover letter to see if needed
                                        apply_success = False
                                        
                                        try:
                                            apply_success = automator.apply(job_url=job_basic_info.url, resume_path=resume_file_path)
                                        except Exception as apply_e:
                                            logger.error(f"Error in first application attempt: {apply_e}", exc_info=True)
                                            # Check specifically for 429 error
                                            if "429" in str(apply_e) or hasattr(automator.driver, 'page_source') and "429" in automator.driver.page_source:
                                                logger.error("429 error detected during application")
                                                # Let rate_limiter handle the error
                                                if not rate_limiter.handle_429_error():
                                                    # If it indicates we should restart session
                                                    initialize_browser()
                                                    # Retry this same job after restart
                                                    job_index -= 1
                                                    continue
                                        
                                        # Check if cover letter was needed but not provided
                                        cover_letter_needed = automator.check_if_cover_letter_needed()
                                        
                                        if not apply_success and cover_letter_needed and generator:
                                            # If failed and needs cover letter, generate and try again
                                            logger.info("Cover letter required. Generating...")
                                            try:
                                                # Update user profile with recruiter info if available
                                                user_profile_with_recruiter = user_profile.copy()
                                                if recruiter_info["name"]:
                                                    user_profile_with_recruiter["recruiter_name"] = recruiter_info["name"]
                                                    user_profile_with_recruiter["recruiter_title"] = recruiter_info["title"]
                                                
                                                # Generate cover letter
                                                cover_letter_text = generator.generate(
                                                    job_details=job_basic_info,
                                                    user_profile=user_profile_with_recruiter
                                                )
                                                
                                                if cover_letter_text:
                                                    logger.info("Cover letter generated. Waiting before retrying...")
                                                    
                                                    # Human-like pause between attempts
                                                    add_random_delay(3, 5, "Pause between application attempts", logger)
                                                    
                                                    # New attempt with cover letter
                                                    try:
                                                        apply_success = automator.apply(
                                                            job_url=job_basic_info.url,
                                                            cover_letter=cover_letter_text,
                                                            resume_path=resume_file_path
                                                        )
                                                    except Exception as apply2_e:
                                                        logger.error(f"Error in second application with cover letter: {apply2_e}", exc_info=True)
                                                        
                                                        # Check specifically for 429 error
                                                        if "429" in str(apply2_e) or hasattr(automator.driver, 'page_source') and "429" in automator.driver.page_source:
                                                            logger.error("429 error detected during second application")
                                                            # Let rate_limiter handle the error
                                                            if not rate_limiter.handle_429_error():
                                                                # If it indicates we should restart session
                                                                initialize_browser()
                                                                # Retry this same job after restart
                                                                job_index -= 1
                                                                continue
                                                                
                                                        apply_success = False
                                                    
                                                    if apply_success:
                                                        logger.info("APPLICATION SUCCESSFUL with cover letter!")
                                                        final_status = ApplicationStatus.APPLIED
                                                        applied_count += 1
                                                    else:
                                                        logger.info("Failed in second attempt despite cover letter")
                                                        final_status = ApplicationStatus.MANUAL_REVIEW
                                                        application_notes += "|Failed with cover letter"
                                                        manual_count += 1
                                                else:
                                                    logger.error("Cover letter generation failed.")
                                                    application_notes += "|Cover Letter Gen Failed"
                                                    final_status = ApplicationStatus.MANUAL_REVIEW
                                                    manual_count += 1
                                            except Exception as gen_e:
                                                logger.error(f"Cover letter generation error: {gen_e}", exc_info=True)
                                                application_notes += f"|Cover Letter Gen Error: {gen_e}"
                                                final_status = ApplicationStatus.MANUAL_REVIEW
                                                manual_count += 1
                                        elif apply_success:
                                            # If succeeded in first attempt (without needing cover letter)
                                            logger.info("Automator SUCCESS.")
                                            final_status = ApplicationStatus.APPLIED
                                            applied_count += 1
                                        else:
                                            # If failed but not due to missing cover letter
                                            logger.info("Automator FAILED.")
                                            final_status = ApplicationStatus.MANUAL_REVIEW
                                            application_notes += "|Manual Review"
                                            manual_count += 1
                                    except Exception as app_e:
                                        logger.error(f"Critical application error: {app_e}", exc_info=True)
                                        final_status = ApplicationStatus.ERROR
                                        application_notes += f"|Application Error: {app_e}"
                                        error_count += 1
                                else:
                                    logger.error("Automator not available.")
                                    final_status = ApplicationStatus.ERROR
                                    application_notes += "|Automator OFF"
                                    error_count += 1

                        # --- Save information to database ---
                        try:
                            logger.debug(f"Saving to DB. Status: {final_status.name}, Notes: {application_notes}")
                            application_record = JobApplication(
                                linkedin_job_id=job_basic_info.linkedin_job_id, 
                                job_title=job_basic_info.title, 
                                company_name=job_basic_info.company,
                                job_url=job_basic_info.url, 
                                location=job_basic_info.location, 
                                status=final_status, 
                                notes=application_notes.strip("| "),
                                cover_letter_generated=bool(cover_letter_text), 
                                cover_letter_text=cover_letter_text,
                                application_date=utc_now() if final_status == ApplicationStatus.APPLIED else None
                            )
                            db_session.add(application_record)
                            db_session.commit()  # Commit after each processed job
                        except Exception as db_e:
                            logger.error(f"Error saving to DB: {db_e}")
                            # Try to commit despite error
                            try:
                                db_session.commit()
                            except:
                                pass
                        
                        logger.info(f"Job completed. Saved status: {final_status.name}")
                        
                        # --- CRITICAL SECTION: Handle state after application ---
                        # Add extra pause after successful application
                        if final_status == ApplicationStatus.APPLIED:
                            logger.info("Successful application, pausing before continuing...")
                            add_random_delay(8, 12, "Extra post-application pause", logger)
                            
                            # Force reload of LinkedIn main page to "reset" state
                            try:
                                logger.info("Reloading LinkedIn main page to reset state...")
                                fetcher.driver.get("https://www.linkedin.com/feed/")
                                time.sleep(3)  # Allow time for main page to load
                            except Exception as reload_e:
                                logger.warning(f"Error reloading main page: {reload_e}")
                        else:
                            # Normal pause between jobs
                            add_random_delay(4, 6, "Pause between jobs", logger)
                        
                        # Periodically check browser state
                        if job_index > 0 and job_index % 3 == 0:  # Increased from 5 to 3 for more frequent checks
                            try:
                                # Simple check that browser is still responding
                                current_url = fetcher.driver.current_url
                                logger.info(f"Browser state OK. Current URL: {current_url}")
                            except Exception as browser_e:
                                logger.error(f"Error checking browser state: {browser_e}")
                                # If error, try to restart browser
                                raise RuntimeError("Error checking browser state, restarting...")
                        
                    except Exception as job_e:
                        # Error processing this specific job
                        logger.error(f"Error processing job #{processed_count}: {job_e}", exc_info=True)
                        error_count += 1
                        
                        # Try to continue with next job
                        try:
                            # Capture screenshot for debugging
                            if fetcher and fetcher.driver:
                                try:
                                    fetcher.driver.save_screenshot(f"error_job_{processed_count}.png")
                                except:
                                    pass
                                
                            # If error seems browser-related, restart
                            browser_error_keywords = ["webdriver", "driver", "stale", "session", "element"]
                            if any(kw in str(job_e).lower() for kw in browser_error_keywords):
                                logger.warning("Likely browser error detected, restarting...")
                                initialize_browser()
                                continue
                                
                            # Return to main page to reset state
                            fetcher.driver.get("https://www.linkedin.com/feed/")
                            time.sleep(5)  # Extra wait for stabilization
                        except Exception as recovery_e:
                            logger.error(f"Error in recovery after job failure: {recovery_e}")
                            # If we can't recover, better restart browser
                            initialize_browser()
                        
                        # Continue with next job
                        continue
                        
        else:
            logger.info("No jobs in initial list to process.")

    except Exception as e:
        logger.exception(f"Critical error in main execution: {e}")
    finally:
        if fetcher and fetcher.driver:
            logger.info("Closing WebDriver...")
            fetcher.close()
        elif driver:
            logger.info("Closing WebDriver (outside fetcher)...")
            driver.quit()
        logger.info("=======================================================")
        logger.info("Bot completed.")
        logger.info(f"SUMMARY: Processed={processed_count}, Applied(Auto)={applied_count}, Manual Review={manual_count}, Skipped(Filter)={skipped_count}, Errors={error_count}")
        logger.info("=======================================================")

# --- Entry Point ---
if __name__ == "__main__":
    if not config.LINKEDIN_EMAIL or not config.LINKEDIN_PASSWORD:
        print("CRITICAL ERROR: Missing LINKEDIN_EMAIL or LINKEDIN_PASSWORD in .env")
    else:
        # Verify MANUAL_REVIEW status
        try:
            _ = ApplicationStatus.MANUAL_REVIEW
        except AttributeError:
            print("CRITICAL ERROR: Missing 'MANUAL_REVIEW' status in ApplicationStatus (src/db/models.py).")
            exit(1)
        main()