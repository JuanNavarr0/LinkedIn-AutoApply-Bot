# LinkedIn Job Application Bot

An automated Python bot designed to streamline the process of searching and applying for jobs on LinkedIn.

## Disclaimer

Automating interactions with websites like LinkedIn may be against their Terms of Service. Use this bot responsibly and at your own risk. LinkedIn's website structure changes frequently, which may break the bot's functionality, requiring updates to selectors and automation logic.

## Features

- Searches for jobs on LinkedIn based on keywords and location
- Logs into LinkedIn using provided credentials
- Applies to jobs using LinkedIn's "Easy Apply" feature
- Optional personalized cover letter generation using OpenAI
- Stores application history and status in a database
- Configurable logging levels
- Docker support for containerized execution

## Requirements

- Python 3.6+
- Selenium WebDriver
- Chrome browser
- LinkedIn account
- OpenAI API key (optional, for cover letter generation)

## Installation

1. Clone this repository
2. Install dependencies:
   pip install -r requirements.txt
3. Create a `.env` file with your credentials (see `.env.example`)
4. Place your resume PDF in the `/cv` directory

## Usage

Run the bot with:
python -m src.main

Or using Docker:
docker-compose up --build

## Configuration

Edit the search parameters and filters in `src/main.py`:

- `SEARCH_KEYWORDS`: Job titles to search for
- `SEARCH_LOCATION`: Location preference
- `TIME_FILTER`: Filter for job posting date
- Other parameters like job title filters, processing limits, etc.

## License

[MIT](LICENSE)
