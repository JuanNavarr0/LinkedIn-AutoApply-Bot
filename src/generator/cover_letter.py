"""
Cover letter generation module using AI models.

Provides functionality to generate personalized cover letters using OpenAI's API
based on job details and user profile information.
"""

import logging
from typing import Dict, Any, Optional

import openai

from ..config import Config


class CoverLetterGenerator:
    """
    Generates personalized cover letters using OpenAI's API.
    """

    def __init__(self, config: Config):
        """
        Initialize the CoverLetterGenerator.

        Args:
            config: The application configuration object containing the OpenAI API key.
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        if not self.config.OPENAI_API_KEY:
            self.logger.warning("OPENAI_API_KEY not found in config. Cover letter generation will be disabled.")
            self.client = None
        else:
            try:
                self.client = openai.OpenAI(api_key=self.config.OPENAI_API_KEY)
                self.logger.info("OpenAI client initialized.")
            except Exception as e:
                 self.logger.error(f"Failed to initialize OpenAI client: {e}", exc_info=True)
                 self.client = None

    def generate(self, job_details: Any, user_profile: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """
        Generate a personalized cover letter for a job application.

        Args:
            job_details: Object containing job information (title, company, description).
            user_profile: Dictionary containing user information (skills, experience, contact).

        Returns:
            The generated cover letter as a string, or None if generation fails.
        """
        if not self.client:
            self.logger.error("Cannot generate cover letter: AI client not initialized or API key missing.")
            return None
        if not user_profile:
            self.logger.error("Cannot generate cover letter: User profile data is missing.")
            return None
            
        # Extract contact info safely
        contact_info = user_profile.get("contact", {})
        user_name = user_profile.get("full_name", "Juan Navarro")
        user_email = contact_info.get("email", "")
        user_phone = contact_info.get("phone", "")
        user_linkedin = contact_info.get("linkedin", "")
        user_github = contact_info.get("github", None)  # Optional GitHub

        job_title = getattr(job_details, 'title', 'the position')
        company_name = getattr(job_details, 'company', 'your company')
        job_description = getattr(job_details, 'description', '')

        self.logger.info(f"Generating cover letter for job: {job_title} at {company_name}")

        try:
            # Create the contact block string
            contact_block = f"{user_name}\n{user_email} | {user_phone} | LinkedIn: {user_linkedin}"
            if user_github:
                contact_block += f" | GitHub: {user_github}"

            prompt = f"""
            You are assisting Juan Navarro, a Machine Learning Engineer specializing in Generative AI & RAG, in writing a personalized cover letter.
            Your task is to generate a compelling cover letter for the position of '{job_title}' at '{company_name}'.

            Use the following information about Juan Navarro:
            - Role: {user_profile.get('role', 'AI & Machine Learning Engineer')}
            - Summary: {user_profile.get('summary', '')}
            - Key Skills:
                - ML/NLP: {user_profile.get('skills', {}).get('ml_nlp', 'Not specified')}
                - Frameworks/Programming: {user_profile.get('skills', {}).get('frameworks_programming', 'Not specified')}
                - Cloud/DevOps/MLOps: {user_profile.get('skills', {}).get('cloud_devops_mlops', 'Not specified')}
                - Databases/Vector Stores: {user_profile.get('skills', {}).get('databases_vector_stores', 'Not specified')}
            - Experience Highlights: {'; '.join(user_profile.get('experience_highlights', []))}
            - Current Project Focus: {user_profile.get('current_project', '')}
            - Soft Skills: {user_profile.get('soft_skills', '')}

            Here is the job description (use this to tailor the letter):
            --- START JOB DESCRIPTION ---
            {job_description[:1000]}...
            --- END JOB DESCRIPTION ---

            Follow this structure and tone, inspired by Juan's example cover letter:
            1.  Opening: Address the Hiring Manager (e.g., "Dear Hiring Manager,"). State Juan's role and specialization.
            2.  Core Pitch: Briefly mention his passion/approach. Connect to the role/company.
            3.  Evidence: 2-3 *most relevant* skills/experiences matching the job description.
            4.  Current Project/Ambition (Optional): Mention relevant ongoing work.
            5.  Personal Attributes: Mention key soft skills.
            6.  Closing: Express strong interest and enthusiasm for discussing alignment. Include a call to action.
            7.  Sign-off: Use "Best regards,".

            **IMPORTANT INSTRUCTIONS**
            - Personalize heavily based on the job description.
            - Be concise and professional.
            - Write the entire letter AS Juan Navarro. After the "Best regards," sign-off, you MUST include the following contact information block EXACTLY as provided below, with line breaks:
            {contact_block}
            - DO NOT include any other placeholders like "[Company Name]" etc. The letter must be complete and ready to send.
            """

            self.logger.debug(f"Generated prompt for OpenAI:\n{prompt[:300]}...")

            # Call the AI model
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant writing professional, personalized cover letters, including specific contact details at the end."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=750,
                temperature=0.6,
                n=1,
                stop=None,
            )

            # Extract the generated text
            if response.choices and response.choices[0].message:
                 generated_text = response.choices[0].message.content.strip()
                 self.logger.info("Successfully generated cover letter (incl. contact details).")
                 # Verify if the contact block was included
                 if user_email not in generated_text[-150:]:
                     self.logger.warning("Contact details might be missing from generated letter.")
                 return generated_text
            else:
                 self.logger.error("Failed to generate cover letter: No response content.")
                 return None

        except openai.APIError as e:
             self.logger.error(f"OpenAI API error: {e}", exc_info=True)
             return None
        except Exception as e:
             self.logger.error(f"Unexpected error during cover letter generation: {e}", exc_info=True)
             return None