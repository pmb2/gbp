# File: utils/gbp_agent.py

import asyncio
import os
import random
import time
import logging
from datetime import datetime, timedelta

from dotenv import load_dotenv
from pydantic import SecretStr
from langchain_google_genai import ChatGoogleGenerativeAI

from browser_use import Agent
from browser_use.browser.browser import Browser, BrowserConfig
from browser_use.browser.context import BrowserContext, BrowserContextConfig

# ======================
# CONFIGURATION & ENVIRONMENT
# ======================
load_dotenv()
api_key = os.getenv('GEMINI_API_KEY')
if not api_key:
    raise ValueError('GEMINI_API_KEY is not set')

# Initialize the LLM (Gemini or similar)
llm = ChatGoogleGenerativeAI(model='gemini-2.0-flash-exp', api_key=SecretStr(api_key))

# Global logging configuration
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")


# ======================
# GBPAgent Class Definition
# ======================
class GBPAgent:
    def __init__(self, cookies_file: str, chrome_path: str, headless: bool = False):
        """
        Initialize the agent with its own browser context and cookie file.

        Args:
            cookies_file (str): Path to the file that stores your session cookies.
            chrome_path (str): Full path to the Chrome/Chromium executable.
            headless (bool): Whether to run in headless mode. Set to False for a visible window.
        """
        self.headless = headless
        logging.info(f"Initializing GBPAgent (headless={self.headless})")

        # Build chrome arguments
        chrome_args = []
        if self.headless:
            chrome_args.append("--headless=new")
        else:
            logging.info("Running in visible (non-headless) mode.")
        chrome_args.extend([
            "--disable-gpu",
            "--no-sandbox",
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage"
        ])

        # Create Browser instance with the given Chrome path
        self.browser = Browser(
            config=BrowserConfig(
                chrome_instance_path=chrome_path,
                arguments=chrome_args
            )
        )
        logging.info("Browser instance created.")

        # Create a BrowserContext using the provided cookies file.
        self.context = BrowserContext(
            browser=self.browser,
            config=BrowserContextConfig(cookies_file=cookies_file)
        )
        self.llm = llm
        logging.info("GBPAgent initialized successfully.")

    async def run_task(self, task_description: str, max_steps: int = 25):
        """
        Run an agent task with a given detailed prompt.

        Args:
            task_description (str): A detailed prompt describing the task.
            max_steps (int): Maximum number of actions/steps for the agent.
        """
        logging.info("=== Starting Agent Task ===")
        logging.info(f"Task Description:\n{task_description}")
        agent = Agent(
            browser_context=self.context,
            task=task_description,
            llm=self.llm,
            max_actions_per_step=4
        )
        await agent.run(max_steps=max_steps)
        logging.info("=== Agent Task Completed ===")

    # --- Modular Task Prompt Generators ---
    def generate_update_business_info_task(self, business_id: str, base_url: str, new_hours: str,
                                           new_website: str) -> str:
        """
        Generate a prompt to update business profile information.

        Args:
            business_id (str): Unique identifier for the business.
            base_url (str): Base URL for the Google Business Profile (e.g., "https://business.google.com").
            new_hours (str): The new business hours.
            new_website (str): The new website URL.
        Returns:
            str: A detailed prompt for the update task.
        """
        business_edit_url = f"{base_url}/{business_id}/edit"
        return f"""
Task: Update Business Profile Information.
1. Navigate to the business profile edit page: {business_edit_url}.
2. Locate the field for the website and update it to: '{new_website}'.
3. Locate the field for business hours and update it to: '{new_hours}'.
4. Click the 'Save' button and confirm that a success message appears.
5. Return a JSON summary of the updated information, including confirmation of changes.
"""

    def generate_respond_review_task(self, business_id: str, base_url: str, review_text: str,
                                     response_text: str = None) -> str:
        """
        Generate a prompt to respond to a review.

        Args:
            business_id (str): Unique business identifier.
            base_url (str): Base URL for the business profile.
            review_text (str): The review text to locate.
            response_text (str, optional): If provided, the exact response text to use;
                                           otherwise, use a default tone.
        Returns:
            str: A detailed prompt for the review response task.
        """
        business_reviews_url = f"{base_url}/{business_id}/reviews"
        if not response_text:
            response_text = "Thank you for your feedback! We’re glad you enjoyed our service."
        return f"""
Task: Respond to a Review.
1. Navigate to the reviews section of the business profile: {business_reviews_url}.
2. Identify the review containing the text: '{review_text}'.
3. Click the 'Reply' button next to that review.
4. Enter the following reply: '{response_text}'.
5. Submit the reply and verify that it appears.
6. Return a JSON summary indicating the success or failure of the reply.
"""

    def generate_schedule_post_task(self, business_id: str, base_url: str, post_content: str,
                                    hours_from_now: int = 1) -> str:
        """
        Generate a prompt to create and schedule a new post.

        Args:
            business_id (str): Unique business identifier.
            base_url (str): Base URL for the business profile.
            post_content (str): The content of the post.
            hours_from_now (int): How many hours in the future to schedule the post.
        Returns:
            str: A detailed prompt for the scheduling task.
        """
        scheduled_time = (datetime.now() + timedelta(hours=hours_from_now)).strftime("%Y-%m-%d %H:%M")
        post_page_url = f"{base_url}/{business_id}/posts/new"
        return f"""
Task: Create and Schedule a New Post.
1. Navigate to the new post creation page: {post_page_url}.
2. Enter the post content: '{post_content}'.
3. Set the scheduled publication time to: {scheduled_time}.
4. Submit the post or schedule it.
5. Confirm that a success message is displayed indicating the post is scheduled.
6. Return a JSON summary including the post content, scheduled time, and status.
"""

    def generate_upload_photo_task(self, business_id: str, base_url: str, photo_path: str) -> str:
        """
        Generate a prompt to upload a photo.

        Args:
            business_id (str): Unique business identifier.
            base_url (str): Base URL for the business profile.
            photo_path (str): Local path to the photo file.
        Returns:
            str: A detailed prompt for the photo upload task.
        """
        photos_url = f"{base_url}/{business_id}/photos"
        return f"""
Task: Upload a New Photo.
1. Navigate to the photos section: {photos_url}.
2. Click the 'Add Photo' or 'Upload Photo' button.
3. Upload the photo from: '{photo_path}'.
4. Confirm that the photo is successfully uploaded and visible in the gallery.
5. Return a JSON summary indicating the status of the photo upload.
"""

    # --- Orchestrator Flow (Modular) ---
    async def run_full_flow(self, business_id: str, base_url: str,
                            new_hours: str, new_website: str,
                            review_text: str, review_response: str,
                            post_content: str, photo_path: str):
        """
        Execute a full automation flow using modular tasks.

        Args:
            business_id (str): Unique business identifier.
            base_url (str): Base URL for the business profile (e.g., "https://business.google.com").
            new_hours (str): New business hours.
            new_website (str): New website URL.
            review_text (str): Text from the review to reply to.
            review_response (str): The response text for the review.
            post_content (str): Content for a new post.
            photo_path (str): Local file path for the photo to upload.
        """
        # 1. Update business info
        update_info_prompt = self.generate_update_business_info_task(business_id, base_url, new_hours, new_website)
        await self.run_task(update_info_prompt, max_steps=25)

        # 2. Respond to a review
        respond_review_prompt = self.generate_respond_review_task(business_id, base_url, review_text, review_response)
        await self.run_task(respond_review_prompt, max_steps=25)

        # 3. Schedule a new post
        schedule_post_prompt = self.generate_schedule_post_task(business_id, base_url, post_content, hours_from_now=1)
        await self.run_task(schedule_post_prompt, max_steps=25)

        # 4. Upload a photo
        upload_photo_prompt = self.generate_upload_photo_task(business_id, base_url, photo_path)
        await self.run_task(upload_photo_prompt, max_steps=25)

        logging.info("Full automation flow completed successfully.")


# ======================
# MAIN ENTRY POINT
# ======================
if __name__ == "__main__":
    # Set up your cookies file (each agent instance should have its own cookies file to avoid clashes)
    cookies_file = os.path.join(os.path.dirname(__file__), "browser_cookies", "gbp_cookies.txt")

    # Set the path to Chrome/Chromium. (Adjust this path as needed for your Windows EC2 instance)
    chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"  # For Windows
    # For Linux, it might be '/usr/bin/chromium-browser'

    # Instantiate the agent in visible mode (headless=False)
    agent = GBPAgent(cookies_file=cookies_file, chrome_path=chrome_path, headless=False)

    # Example parameters for a business profile (adjust these values per agent instance)
    business_id = "your_business_id"  # e.g., "accounts/123456789"
    base_url = "https://business.google.com"
    new_hours = "Mon-Fri 9am-5pm"
    new_website = "https://new-website.example.com"
    review_text = "The service was excellent!"
    review_response = "Thank you for your kind feedback! We are thrilled to serve you."
    post_content = "We're excited to announce a new promotion this week!"
    photo_path = r"C:\path\to\your\photo.jpg"  # Adjust as needed for Windows

    # Run the full flow asynchronously
    try:
        asyncio.run(agent.run_full_flow(business_id, base_url,
                                        new_hours, new_website,
                                        review_text, review_response,
                                        post_content, photo_path))
    except Exception as e:
        logging.error(f"Full automation flow encountered an error: {e}")
