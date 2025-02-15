#!/usr/bin/env python3
"""
Integrated Google Business Profile Automation with Onboarding

This module:
  1. Attempts to perform tasks (e.g. update info, respond to reviews, schedule posts, upload photos)
     via the official Google Business Profile API.
  2. Falls back to browser automation (using browser‑use/Playwright) when API access isn’t available.
  3. Provides an interactive onboarding function so users can add new business accounts
     by collecting cookies/session data (or credentials) required for automation.
"""

import os
import json
import logging
import asyncio
from datetime import datetime, timedelta

# Google API libraries for the primary layer
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from googleapiclient.errors import HttpError

# Environment and credential management
from dotenv import load_dotenv
from pydantic import SecretStr

load_dotenv()
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")


###############################################################################
# Primary Layer: Google Business Profile API Handler
###############################################################################
class GoogleBusinessAPIHandler:
    def __init__(self, credentials_file: str):
        """
        Initialize the API handler with OAuth2 credentials.
        """
        self.credentials_file = credentials_file
        self.service = None
        self.account_info = None
        self._build_service()

    def _build_service(self):
        try:
            creds = Credentials.from_authorized_user_file(self.credentials_file)
            # Build the API service (adjust API name and version per current docs)
            self.service = build('mybusiness', 'v4', credentials=creds)
            logging.info("Google Business Profile API service built successfully.")
        except Exception as e:
            logging.error(f"Error building API service: {e}")
            self.service = None

    def check_organization_status(self) -> dict:
        """
        Check whether the API account is an Organization account.
        Returns a dict with a 'valid' flag and details.
        """
        if not self.service:
            return {"valid": False, "error": "API service not built"}
        try:
            result = self.service.accounts().list().execute()
            accounts = result.get("accounts", [])
            if not accounts:
                return {"valid": False, "error": "No accounts found."}
            # For demonstration, use the first account
            self.account_info = accounts[0]
            account_name = self.account_info.get("name", "").lower()
            if "organization" in account_name or "agency" in account_name:
                logging.info("Account appears to be an Organization account.")
                return {"valid": True, "account": self.account_info}
            else:
                logging.warning("Account is not an Organization account.")
                return {"valid": False, "error": "Not an organization account."}
        except HttpError as err:
            logging.error(f"HTTP error during organization check: {err}")
            return {"valid": False, "error": str(err)}
        except Exception as e:
            logging.error(f"Error during organization check: {e}")
            return {"valid": False, "error": str(e)}

    def update_business_info(self, location_name: str, new_hours: str, new_website: str) -> dict:
        """
        Update business info via the API.
        location_name: resource name (e.g. "accounts/123/locations/456").
        """
        if not self.service:
            return {"success": False, "error": "No API service"}
        try:
            location = self.service.accounts().locations().get(name=location_name).execute()
            # Update fields (this is a simplified example)
            if "regularHours" in location:
                try:
                    open_time, close_time = [t.strip() for t in new_hours.split("-")]
                    location["regularHours"]["periods"][0]["openTime"] = open_time
                    location["regularHours"]["periods"][0]["closeTime"] = close_time
                except Exception as parse_err:
                    logging.warning("Failed to parse hours, skipping regularHours update.")
            location["websiteUrl"] = new_website

            updated_location = self.service.accounts().locations().patch(
                name=location_name,
                body=location,
                updateMask="regularHours,websiteUrl"
            ).execute()
            logging.info("Business info updated via API.")
            return {"success": True, "updated_location": updated_location}
        except HttpError as err:
            logging.error(f"API error updating business info: {err}")
            return {"success": False, "error": str(err)}
        except Exception as e:
            logging.error(f"Error updating business info: {e}")
            return {"success": False, "error": str(e)}

    def respond_to_review(self, location_name: str, review_id: str, response_text: str) -> dict:
        """
        Respond to a review via the API.
        """
        if not self.service:
            return {"success": False, "error": "No API service"}
        try:
            response = self.service.accounts().locations().reviews().updateReply(
                parent=f"{location_name}/reviews/{review_id}",
                body={"comment": response_text}
            ).execute()
            logging.info("Review responded to via API.")
            return {"success": True, "response": response}
        except HttpError as err:
            logging.error(f"API error responding to review: {err}")
            return {"success": False, "error": str(err)}
        except Exception as e:
            logging.error(f"Error responding to review: {e}")
            return {"success": False, "error": str(e)}

    def schedule_post(self, location_name: str, post_content: str, hours_from_now: int = 1) -> dict:
        """
        Create a new post via the API.
        """
        if not self.service:
            return {"success": False, "error": "No API service"}
        try:
            scheduled_time = (datetime.now() + timedelta(hours=hours_from_now)).isoformat()
            post_body = {
                "summary": post_content,
                "media": [],
                "languageCode": "en",
                "scheduleTime": scheduled_time
            }
            response = self.service.accounts().locations().localPosts().create(
                parent=location_name,
                body=post_body
            ).execute()
            logging.info("Post scheduled via API.")
            return {"success": True, "post": response}
        except HttpError as err:
            logging.error(f"API error scheduling post: {err}")
            return {"success": False, "error": str(err)}
        except Exception as e:
            logging.error(f"Error scheduling post: {e}")
            return {"success": False, "error": str(e)}

    def upload_photo(self, location_name: str, photo_file_path: str) -> dict:
        """
        Upload a photo via the API.
        Note: Actual photo upload might require multipart upload via MediaFileUpload.
        """
        if not self.service:
            return {"success": False, "error": "No API service"}
        try:
            # Placeholder: In production, use googleapiclient.http.MediaFileUpload, etc.
            response = self.service.accounts().locations().media().upload(
                parent=location_name,
                media_body=photo_file_path
            ).execute()
            logging.info("Photo uploaded via API.")
            return {"success": True, "media": response}
        except HttpError as err:
            logging.error(f"API error uploading photo: {err}")
            return {"success": False, "error": str(err)}
        except Exception as e:
            logging.error(f"Error uploading photo: {e}")
            return {"success": False, "error": str(e)}


###############################################################################
# Secondary Layer: Fallback Browser Automation Agent using browser-use
###############################################################################
class FallbackGBPAgent:
    def __init__(self, business_id: str, cookies_file: str, chrome_path: str, headless: bool = True):
        """
        Initialize the fallback agent using browser-use (which uses Playwright).
        """
        self.business_id = business_id
        self.cookies_file = cookies_file
        self.headless = headless
        logging.info(f"[{self.business_id}] Initializing fallback agent (headless={self.headless})")
        chrome_args = []
        if self.headless:
            chrome_args.append("--headless=new")
        chrome_args.extend([
            "--disable-gpu",
            "--no-sandbox",
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage"
        ])
        from browser_use.browser.browser import Browser, BrowserConfig
        from browser_use.browser.context import BrowserContext, BrowserContextConfig

        config = BrowserConfig(chrome_instance_path=chrome_path)
        config.chrome_args = chrome_args
        self.browser = Browser(config=config)
        self.context = BrowserContext(browser=self.browser, config=BrowserContextConfig(cookies_file=cookies_file))
        logging.info(f"[{self.business_id}] Fallback agent initialized.")

    def collect_cookies_interactively(self, login_url: str):
        """
        Launch a visible login flow using Selenium (if available) to collect cookies.
        This should be run when onboarding a new business.
        """
        try:
            if hasattr(self.context, "driver"):
                driver = self.context.driver
            elif hasattr(self.context, "launch_driver"):
                driver = self.context.launch_driver()
            else:
                raise AttributeError("No Selenium driver available in the context.")
        except AttributeError as e:
            logging.error(f"[{self.business_id}] Unable to obtain Selenium driver: {e}")
            return

        driver.get(login_url)
        logging.info(f"[{self.business_id}] Navigated to login URL: {login_url}")
        input(f"[{self.business_id}] Complete the login in the opened browser window, then press Enter...")
        cookies = driver.get_cookies()
        with open(self.cookies_file, "w") as f:
            json.dump(cookies, f)
        logging.info(f"[{self.business_id}] Cookies saved to {self.cookies_file}")
        driver.quit()

    async def update_business_info(self, business_url: str, new_hours: str, new_website: str) -> dict:
        from playwright.async_api import Page
        page: Page = await self.context.new_page()
        edit_url = f"{business_url}/edit"
        logging.info(f"[{self.business_id} Fallback] Navigating to {edit_url} for update.")
        await page.goto(edit_url)
        await page.fill("input[name='website']", new_website)
        await page.fill("input[name='hours']", new_hours)
        await page.click("button:has-text('Save')")
        await page.wait_for_selector("text=Profile updated successfully", timeout=10000)
        result = {"business_id": self.business_id, "status": "success", "method": "fallback_update"}
        await page.close()
        return result

    async def respond_review(self, business_url: str, review_text: str, response_text: str) -> dict:
        from playwright.async_api import Page
        page: Page = await self.context.new_page()
        reviews_url = f"{business_url}/reviews"
        logging.info(f"[{self.business_id} Fallback] Navigating to {reviews_url} for review response.")
        await page.goto(reviews_url)
        review_selector = f"text={review_text}"
        await page.wait_for_selector(review_selector, timeout=10000)
        await page.click(f"{review_selector} >> .. >> button:has-text('Reply')")
        await page.fill("textarea.reply-input", response_text)
        await page.click("button:has-text('Submit')")
        await page.wait_for_selector("text=Your reply has been posted", timeout=10000)
        result = {"business_id": self.business_id, "status": "success", "method": "fallback_respond"}
        await page.close()
        return result

    async def schedule_post(self, business_url: str, post_content: str, hours_from_now: int = 1) -> dict:
        from playwright.async_api import Page
        page: Page = await self.context.new_page()
        post_url = f"{business_url}/posts/new"
        logging.info(f"[{self.business_id} Fallback] Navigating to {post_url} to schedule post.")
        await page.goto(post_url)
        await page.fill("textarea.post-content", post_content)
        scheduled_time = (datetime.now() + timedelta(hours=hours_from_now)).strftime("%Y-%m-%d %H:%M")
        await page.fill("input[name='scheduled_time']", scheduled_time)
        await page.click("button:has-text('Schedule')")
        await page.wait_for_selector("text=Post scheduled successfully", timeout=10000)
        result = {"business_id": self.business_id, "status": "success", "method": "fallback_post",
                  "scheduled_time": scheduled_time}
        await page.close()
        return result

    async def upload_photo(self, business_url: str, photo_path: str) -> dict:
        from playwright.async_api import Page
        page: Page = await self.context.new_page()
        photos_url = f"{business_url}/photos"
        logging.info(f"[{self.business_id} Fallback] Navigating to {photos_url} to upload photo.")
        await page.goto(photos_url)
        async with page.expect_file_chooser() as fc_info:
            await page.click("button:has-text('Upload Photo')")
        file_chooser = await fc_info.value
        await file_chooser.set_files(photo_path)
        await page.wait_for_selector("text=Photo uploaded successfully", timeout=10000)
        result = {"business_id": self.business_id, "status": "success", "method": "fallback_upload"}
        await page.close()
        return result


###############################################################################
# BusinessProfileManager: Managing Multiple Business Accounts
###############################################################################
class BusinessProfileManager:
    def __init__(self, businesses: dict, cookies_folder: str, chrome_path: str,
                 credentials_file: str, headless: bool = True):
        """
        Initialize agents for multiple businesses.

        Args:
            businesses (dict): Mapping of business_id to business_url.
            cookies_folder (str): Folder for storing cookie files.
            chrome_path (str): Path to Chrome/Chromium.
            credentials_file (str): Path to Google API OAuth credentials.
            headless (bool): Run in headless mode by default.
        """
        self.businesses = businesses
        self.cookies_folder = cookies_folder
        self.chrome_path = chrome_path
        self.credentials_file = credentials_file
        self.headless = headless
        self.api_handler = GoogleBusinessAPIHandler(credentials_file)
        # Initialize fallback agents for each business.
        self.fallback_agents = {}
        for business_id in businesses:
            cookie_file = os.path.join(cookies_folder, f"cookies_{business_id}.json")
            self.fallback_agents[business_id] = FallbackGBPAgent(business_id, cookie_file, chrome_path,
                                                                 headless=headless)

    async def process_business(self, business_id: str, task_data: dict) -> None:
        """
        For a given business, attempt API-based automation first;
        if API calls fail or the account is not properly set up, fall back to browser automation.

        task_data must include:
            - location_name (e.g. "accounts/123/locations/456")
            - new_hours, new_website
            - review_id, review_text, review_response
            - post_content, photo_path
        """
        business_url = self.businesses[business_id]
        from gbp_django.models import Business
        business_obj = Business.objects.get(business_id=business_id)
        location_name = business_obj.google_location_id if business_obj.google_location_id else task_data.get("location_name")
        logging.info(f"[{business_id}] Processing tasks for {business_url} with location: {location_name}")

        org_status = self.api_handler.check_organization_status()
        if not org_status.get("valid", False):
            logging.warning(f"[{business_id}] API account not valid (or not organization): {org_status.get('error')}")
            logging.info(f"[{business_id}] Using fallback automation.")
            await self._run_fallback_flow(business_id, business_url, task_data)
        
        if not org_status.get("valid", False):
            api_success = False
            results = "Fallback automation executed"
        else:
            api_success = True
            results = {}
            try:
                results["update"] = self.api_handler.update_business_info(location_name, task_data["new_hours"], task_data["new_website"])
                if not results["update"].get("success"):
                    api_success = False
                    raise Exception("update_business_info failed.")
                results["respond"] = self.api_handler.respond_to_review(location_name, task_data["review_id"], task_data["review_response"])
                if not results["respond"].get("success"):
                    api_success = False
                    raise Exception("respond_to_review failed.")
                results["post"] = self.api_handler.schedule_post(location_name, task_data["post_content"], hours_from_now=1)
                if not results["post"].get("success"):
                    api_success = False
                    raise Exception("schedule_post failed.")
                results["upload"] = self.api_handler.upload_photo(location_name, task_data["photo_path"])
                if not results["upload"].get("success"):
                    api_success = False
                    raise Exception("upload_photo failed.")
                logging.info(f"[{business_id}] API tasks completed successfully: {results}")
            except Exception as e:
                logging.error(f"[{business_id}] API error: {e}")
                api_success = False
                logging.info(f"[{business_id}] Falling back to browser automation.")
                await self._run_fallback_flow(business_id, business_url, task_data)
                results = "Fallback automation executed"
        logging.info(f"[{business_id}] Sending automation report email.")
        from gbp_django.utils.email_service import EmailService
        from datetime import datetime
        method_used = "API" if api_success else "Fallback"
        report_data = {
            "results": results,
            "method": method_used
        }
        try:
            executed_at = datetime.now().isoformat()
            EmailService.send_automation_report(business_id, "Automation", report_data, executed_at)
        except Exception as e:
            logging.error(f"[{business_id}] API error: {e}")
            api_success = False

        if not api_success:
            logging.info(f"[{business_id}] Falling back to browser automation.")
            await self._run_fallback_flow(business_id, business_url, task_data)

    async def _run_fallback_flow(self, business_id: str, business_url: str, task_data: dict) -> None:
        agent = self.fallback_agents[business_id]
        try:
            update_res = await agent.update_business_info(business_url,
                                                          task_data["new_hours"],
                                                          task_data["new_website"])
            logging.info(f"[{business_id} Fallback] Update: {update_res}")

            respond_res = await agent.respond_review(business_url,
                                                     task_data["review_text"],
                                                     task_data["review_response"])
            logging.info(f"[{business_id} Fallback] Respond: {respond_res}")

            post_res = await agent.schedule_post(business_url,
                                                 task_data["post_content"],
                                                 hours_from_now=1)
            logging.info(f"[{business_id} Fallback] Post: {post_res}")

            upload_res = await agent.upload_photo(business_url,
                                                  task_data["photo_path"])
            logging.info(f"[{business_id} Fallback] Upload: {upload_res}")

            logging.info(f"[{business_id} Fallback] All fallback tasks completed.")
        except Exception as e:
            logging.error(f"[{business_id} Fallback] Error in fallback flow: {e}")

    async def run_all_businesses(self, tasks_data: dict) -> None:
        tasks = []
        for business_id in tasks_data:
            tasks.append(self.process_business(business_id, tasks_data[business_id]))
        await asyncio.gather(*tasks)


###############################################################################
# Onboarding Function: Add a New Business Account
###############################################################################
def onboard_new_business(cookies_folder: str, chrome_path: str) -> tuple:
    """
    Interactively onboard a new business by gathering its unique ID, URL, and
    performing an interactive login to collect cookies/session data.

    Returns:
        (business_id, business_url)
    """
    business_id = input("Enter the new business ID (unique identifier): ").strip()
    business_url = input("Enter the business URL (e.g., https://business.google.com/your_business_id): ").strip()
    cookie_file = os.path.join(cookies_folder, f"cookies_{business_id}.json")
    # Instantiate a fallback agent in visible (non-headless) mode to perform login.
    agent = FallbackGBPAgent(business_id, cookie_file, chrome_path, headless=False)
    login_url = "https://accounts.google.com/ServiceLogin?service=businessprofile"
    logging.info(f"[{business_id}] Onboarding new business. Initiating interactive login.")
    agent.collect_cookies_interactively(login_url)
    logging.info(f"[{business_id}] Onboarding complete. Cookies stored in {cookie_file}.")
    return business_id, business_url


###############################################################################
# MAIN ENTRY POINT
###############################################################################
if __name__ == "__main__":
    base_dir = os.path.dirname(__file__)
    cookies_folder = os.path.join(base_dir, "browser_cookies")
    os.makedirs(cookies_folder, exist_ok=True)

    # Path to Chrome/Chromium executable (adjust for your OS/environment)
    chrome_path = r"/usr/bin/chromium-browser"
    # Path to the Google API credentials JSON file (for OAuth2)
    credentials_file = os.path.join(base_dir, "credentials.json")

    # Load existing businesses (in a production system, this would come from persistent storage)
    # For demonstration, we start with an empty dictionary.
    businesses = {}

    # Ask the user if they want to onboard a new business.
    add_new = input("Would you like to add a new business? (y/n): ").strip().lower()
    if add_new == "y":
        new_id, new_url = onboard_new_business(cookies_folder, chrome_path)
        businesses[new_id] = new_url
    else:
        # Otherwise, define pre-existing businesses here.
        businesses = {
            "business1": "https://business.google.com/your_business_id1",
            "business2": "https://business.google.com/your_business_id2"
        }

    # Define task-specific data for each business.
    # For API calls, 'location_name' should be the resource name (e.g. "accounts/123/locations/456")
    tasks_data = {
        biz_id: {
            "location_name": "accounts/EXAMPLE/locations/EXAMPLE",  # Replace with actual resource names.
            "new_hours": "Mon-Fri 09:00-17:00",
            "new_website": f"https://new-website-for-{biz_id}.example.com",
            "review_id": "reviewEXAMPLE",  # Replace with actual review ID.
            "review_text": "The service was excellent!",
            "review_response": "Thank you for your kind feedback! We are thrilled to serve you.",
            "post_content": "We're excited to announce a new promotion this week!",
            "photo_path": r"/path/to/photo.jpg"  # Adjust the file path accordingly.
        }
        for biz_id in businesses
    }

    # Create a BusinessProfileManager instance.
    manager = BusinessProfileManager(businesses, cookies_folder, chrome_path, credentials_file, headless=True)

    # Run all tasks concurrently.
    try:
        asyncio.run(manager.run_all_businesses(tasks_data))
    except Exception as e:
        logging.error(f"Error running tasks for all businesses: {e}")
