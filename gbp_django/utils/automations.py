import asyncio
import os
import json
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

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ======================
# CONFIGURATION & ENVIRONMENT
# ======================
load_dotenv()
api_key = os.getenv('GEMINI_API_KEY')
if not api_key:
    raise ValueError('GEMINI_API_KEY is not set')

# Initialize LLM (Gemini or similar)
llm = ChatGoogleGenerativeAI(model='gemini-2.0-flash-exp', api_key=SecretStr(api_key))

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")


# ======================
# Helper: Retrieve underlying Selenium driver
# ======================
def get_selenium_driver(agent):
    """
    Attempt to retrieve the underlying Selenium driver from the agent's BrowserContext.
    Adjust the attribute/method names as needed based on your browser-use version.
    """
    # First, try if the BrowserContext already exposes a driver attribute.
    if hasattr(agent.context, "driver"):
        logging.info("Found driver via agent.context.driver")
        return agent.context.driver
    # Alternatively, try a method called launch_driver() if available.
    elif hasattr(agent.context, "launch_driver"):
        logging.info("Launching driver via agent.context.launch_driver()")
        return agent.context.launch_driver()
    else:
        raise AttributeError("No underlying Selenium driver found in agent context.")


# ======================
# GBPAgent Class Definition
# ======================
class GBPAgent:
    def __init__(self, cookies_file: str, chrome_path: str, headless: bool = False):
        """
        Initialize the agent with its own browser context.

        Args:
            cookies_file (str): Path to the file that stores your session cookies.
            chrome_path (str): Full path to the Chrome/Chromium executable.
            headless (bool): Whether to run Chrome in headless mode.
        """
        self.headless = headless
        logging.info(f"Initializing GBPAgent (headless={self.headless})")

        # Prepare additional Chrome arguments.
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

        # Create a BrowserConfig object.
        config = BrowserConfig(chrome_instance_path=chrome_path)
        # (Assuming the current version of browser-use expects a separate attribute for extra arguments.)
        config.chrome_args = chrome_args
        logging.info(f"Chrome arguments set: {chrome_args}")

        # Create the Browser instance using the config.
        self.browser = Browser(config=config)
        logging.info("Browser instance created.")

        # Create a BrowserContext that loads your cookies for an authenticated session.
        self.context = BrowserContext(
            browser=self.browser,
            config=BrowserContextConfig(cookies_file=cookies_file)
        )
        self.llm = llm
        logging.info("GBPAgent initialized successfully.")

    async def run_task(self, task_description: str, max_steps: int = 25):
        """
        Create and run an Agent for the given task.

        Args:
            task_description (str): A detailed prompt describing the task.
            max_steps (int): Maximum steps for the agent to run.
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

    # --- Task Prompt Generators ---
    def generate_update_business_info_task(self, business_url: str, new_hours: str, new_website: str) -> str:
        business_edit_url = f"{business_url}/edit"
        return f"""
Task: Update Business Profile Information.
1. Navigate to the business profile edit page: {business_edit_url}.
2. Locate the field for the website and update it to: '{new_website}'.
3. Locate the field for business hours and update it to: '{new_hours}'.
4. Click the 'Save' button and verify that a success message appears.
5. Return a JSON summary of the updated information.
"""

    def generate_respond_review_task(self, business_url: str, review_text: str, response_text: str) -> str:
        business_reviews_url = f"{business_url}/reviews"
        return f"""
Task: Respond to a Review.
1. Navigate to the reviews section: {business_reviews_url}.
2. Identify the review containing the text: '{review_text}'.
3. Click the 'Reply' button next to that review.
4. Enter the response: '{response_text}'.
5. Submit the reply and confirm that it appears.
6. Return a JSON summary indicating success.
"""

    def generate_schedule_post_task(self, business_url: str, post_content: str, hours_from_now: int = 1) -> str:
        scheduled_time = (datetime.now() + timedelta(hours=hours_from_now)).strftime("%Y-%m-%d %H:%M")
        post_page_url = f"{business_url}/posts/new"
        return f"""
Task: Create and Schedule a New Post.
1. Navigate to the new post creation page: {post_page_url}.
2. Enter the post content: '{post_content}'.
3. Set the scheduled publication time to: {scheduled_time}.
4. Submit or schedule the post.
5. Return a JSON summary including the post content, scheduled time, and status.
"""

    def generate_upload_photo_task(self, business_url: str, photo_path: str) -> str:
        photos_url = f"{business_url}/photos"
        return f"""
Task: Upload a New Photo.
1. Navigate to the photos section: {photos_url}.
2. Click the 'Add Photo' or 'Upload Photo' button.
3. Upload the photo located at: '{photo_path}'.
4. Confirm that the photo is successfully uploaded and appears in the gallery.
5. Return a JSON summary indicating the upload status.
"""

    # --- Orchestrator Flow ---
    async def run_full_flow(self, business_url: str, new_hours: str, new_website: str,
                            review_text: str, review_response: str,
                            post_content: str, photo_path: str):
        """
        Execute a full automation flow using modular tasks.

        Args:
            business_url (str): Base URL for the business profile.
            new_hours (str): New business hours.
            new_website (str): New website URL.
            review_text (str): Review text to reply to.
            review_response (str): The response for the review.
            post_content (str): Content for a new post.
            photo_path (str): Local path for the photo to upload.
        """
        # 1. Update business info.
        update_info_prompt = self.generate_update_business_info_task(business_url, new_hours, new_website)
        await self.run_task(update_info_prompt, max_steps=25)

        # 2. Respond to a review.
        respond_review_prompt = self.generate_respond_review_task(business_url, review_text, review_response)
        await self.run_task(respond_review_prompt, max_steps=25)

        # 3. Schedule a new post.
        schedule_post_prompt = self.generate_schedule_post_task(business_url, post_content, hours_from_now=1)
        await self.run_task(schedule_post_prompt, max_steps=25)

        # 4. Upload a photo.
        upload_photo_prompt = self.generate_upload_photo_task(business_url, photo_path)
        await self.run_task(upload_photo_prompt, max_steps=25)

        logging.info("Full automation flow completed successfully.")


# ======================
# Utility Function: Collect Cookies if Missing
# ======================
def collect_cookies_if_missing(agent: GBPAgent, login_url: str, cookies_file: str, timeout: int = 300):
    """
    If the cookies file does not exist, launch a visible browser session,
    wait for the user to complete the login, and then save cookies to the file.

    Args:
        agent (GBPAgent): The agent instance to use for browser access.
        login_url (str): URL for the login page.
        cookies_file (str): Path where cookies will be saved.
        timeout (int): Maximum time (in seconds) to wait for the user to log in.
    """
    if os.path.exists(cookies_file):
        logging.info(f"Cookie file {cookies_file} already exists. Skipping login.")
        return

    logging.info("Cookie file not found. Starting login flow to collect cookies.")

    try:
        # Try to get the underlying Selenium driver from the BrowserContext.
        driver = get_selenium_driver(agent)
    except AttributeError as e:
        logging.error(f"Unable to retrieve Selenium driver: {e}")
        return

    driver.get(login_url)
    logging.info(f"Navigated to login URL: {login_url}")

    # Wait for the user to complete login (you could later add more advanced waiting logic)
    input("Complete the login in the opened browser window, then press Enter here to continue...")

    # Retrieve cookies from the driver and save them.
    cookies = driver.get_cookies()
    with open(cookies_file, "w") as f:
        json.dump(cookies, f)
    logging.info(f"Cookies saved to {cookies_file}.")

    driver.quit()


# ======================
# MAIN ENTRY POINT (for testing or direct invocation)
# ======================
if __name__ == "__main__":
    # Set up your cookies file (each instance should have its own cookies file)
    cookies_file = os.path.join(os.path.dirname(__file__), "browser_cookies", "gbp_cookies_business1.txt")

    # Set the path to your Chrome/Chromium executable.
    # For Windows, adjust this path accordingly (e.g., r"C:\Program Files\Google\Chrome\Application\chrome.exe")
    # For Linux, you might use '/usr/bin/chromium-browser'
    chrome_path = r"/usr/bin/chromium-browser"

    # Instantiate the agent (visible mode)
    agent = GBPAgent(cookies_file=cookies_file, chrome_path=chrome_path, headless=False)

    # If cookies are missing, run the login flow to collect them.
    login_url = "https://accounts.google.com/ServiceLogin?service=businessprofile"
    collect_cookies_if_missing(agent, login_url, cookies_file)

    # Business-specific parameters:
    business_url = "https://business.google.com/your_business_id"  # Replace with actual business URL
    new_hours = "Mon-Fri 9am-5pm"
    new_website = "https://new-website.example.com"
    review_text = "The service was excellent!"
    review_response = "Thank you for your kind feedback! We are thrilled to serve you."
    post_content = "We're excited to announce a new promotion this week!"
    photo_path = r"C:\path\to\your\photo.jpg"  # Adjust as needed

    # Run the full flow asynchronously (for testing)
    try:
        asyncio.run(agent.run_full_flow(business_url, new_hours, new_website,
                                        review_text, review_response,
                                        post_content, photo_path))
    except Exception as e:
        logging.error(f"Full automation flow encountered an error: {e}")
