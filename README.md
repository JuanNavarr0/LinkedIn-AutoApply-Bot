# LinkedIn Job Application Bot

An advanced automation tool for streamlining the LinkedIn job application process with personalized cover letter generation, rate limiting, and detailed application tracking.

![LinkedIn Bot](https://img.shields.io/badge/LinkedIn-Bot-0077B5?style=for-the-badge&logo=linkedin&logoColor=white) ![Python](https://img.shields.io/badge/Python-3.6+-3776AB?style=for-the-badge&logo=python&logoColor=white) ![Selenium](https://img.shields.io/badge/Selenium-Automation-43B02A?style=for-the-badge&logo=selenium&logoColor=white) ![OpenAI](https://img.shields.io/badge/OpenAI-Integration-412991?style=for-the-badge&logo=openai&logoColor=white)

## ⚠️ Disclaimer

**Important:** Automated interactions with websites like LinkedIn may violate their Terms of Service. This tool is provided for educational purposes only. Use at your own risk. LinkedIn's website structure changes frequently, which may break functionality and require updates.

## 🌟 Features

- **Smart Job Search**: Searches for jobs based on customizable keywords, location, and time filters
- **Automated Applications**: Handles LinkedIn's "Easy Apply" workflow automatically
- **AI-Powered Cover Letters**: Generates personalized cover letters using OpenAI's GPT models
- **Application Tracking**: Stores detailed application history in a database
- **Anti-Detection Measures**: Implements human-like behavior to reduce blocking risk
- **Rate Limiting**: Advanced rate limiting to avoid LinkedIn restrictions
- **Recruiter Detection**: Identifies and extracts recruiter information when available

## 🛠️ Prerequisites

- Python 3.6+
- Chrome browser
- LinkedIn account
- OpenAI API key (optional, for cover letter generation)

## 📋 Installation & Setup

1. **Clone this repository**:
   ```bash
   git clone https://github.com/yourusername/LinkedIn-Job-Bot.git
   cd LinkedIn-Job-Bot

Install dependencies:
bashpip install -r requirements.txt

Configure environment variables:
Create a .env file in the project root with the following:
LINKEDIN_EMAIL=your_linkedin_email@example.com
LINKEDIN_PASSWORD=your_linkedin_password
OPENAI_API_KEY=your_openai_api_key  # Optional, for cover letter generation
DATABASE_URL=sqlite:///jobs.db  # Default SQLite DB, can be changed
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR

Resume setup:

Place your resume PDF in the /cv directory
Update the filename in main.py:
pythoncv_filename = "Your_Resume.pdf"  # Change this to your resume filename




🔧 Personalization
User Profile Customization (Required)
The bot is currently configured for a specific profile. Update the user_profile dictionary in main.py with your own information:
pythonuser_profile: Dict[str, Any] = {
    "full_name": "Your Name",
    "role": "Your Role | Your Specialization",
    "summary": "Your professional summary here...",
    "skills": {
        "skill_category1": "List of skills...",
        "skill_category2": "List of skills...",
        # Add more skill categories as needed
    },
    "experience_highlights": [
        "Experience 1...",
        "Experience 2...",
        # Add more experiences
    ],
    "current_project": "Your current project description...",
    "soft_skills": "Your soft skills...",
    "seeking": "Type of opportunities you're seeking...",
    "contact": {
        "email": "your.email@example.com",
        "phone": "your phone number",
        "linkedin": "your LinkedIn profile URL",
        "github": "your GitHub username"
    }
}
Search Parameters
Customize job search criteria in main.py:
pythonSEARCH_KEYWORDS = "Your Job Title OR Alternative Title OR Another Option"
SEARCH_LOCATION = "Your Preferred Location or Remote"
TIME_FILTER = "week"  # Options: "week", "day", "month"
SKIP_JOB_TITLE_KEYWORDS = ["keywords", "to", "skip"]
Cover Letter Generator
The cover letter generator is currently tailored to the sample profile. Modify the prompt in src/generator/cover_letter.py to match your background and style.
🚀 Usage
Run the bot with:
bashpython -m src.main
📊 Application Tracking
The bot tracks all job applications in a database (default: SQLite). Each application includes:

Job details (title, company, URL, etc.)
Application status (Applied, Skipped, Manual Review, Error)
Cover letter (if generated)
Application date
Notes

⚙️ Configuration Options
Advanced settings can be adjusted in main.py:
python# Rate limiting configuration
MAX_JOBS_TO_PROCESS = 40  # Maximum jobs per execution
MAX_JOBS_PER_SESSION = 15  # Jobs before browser restart
MIN_JOB_PROCESSING_TIME = 30  # Minimum seconds per job
MAX_SESSION_DURATION = 40 * 60  # Maximum session duration (seconds)
📂 Project Structure

src/main.py: Main execution logic
src/config.py: Configuration management
src/fetcher/linkedin_fetcher.py: Job search and data extraction
src/generator/cover_letter.py: Cover letter generation
src/automator/browser_automator.py: Browser automation for applications
src/db/models.py: Database models and session management
src/utils/logger.py: Logging configuration

🔒 Security Notes

Your LinkedIn credentials and OpenAI API key are stored in the .env file, which is excluded from version control.
Never commit your .env file or credentials to a public repository.

⚠️ Limitations

LinkedIn frequently updates its website, which may break some functionality.
Excessive automation may lead to temporary restrictions on your LinkedIn account.
Cover letter generation quality depends on the OpenAI model and prompt engineering.
Some job applications require custom fields that the bot might not handle.

📜 License
This project is licensed under the MIT License - see the LICENSE file for details.
🤝 Contributing
Contributions, issues, and feature requests are welcome! Feel free to check the issues page.

Note: This bot is a tool to assist with job applications, not a replacement for personalized effort in your job search. Always review applications that the bot submits on your behalf.

Let me know if you want any changes to the repository setup or README content, and I'll be happy to help with the next steps of the GitHub setup process!
