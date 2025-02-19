#!/usr/bin/env python3
"""
Integrated Google Business Profile Automation with Onboarding, Structured Compliance Flow, and Compliance Check

This module:
  1. Attempts to perform tasks (e.g. update info, respond to reviews, schedule posts, upload photos)
     via the official Google Business Profile API.
  2. Falls back to browser automation (using browser‑use/Playwright) when API access isn’t available.
  3. Provides an interactive onboarding function so users can add new business accounts
     by collecting cookies/session data (or credentials) required for automation.
  4. Implements a reasoning model to drive a structured compliance flow. This flow ensures that:
       - Mandatory details (e.g. business website) are verified and updated first.
       - Then content compliance (reviews, Q&A, posts, photos) is checked.
     The reasoning model outputs structured JSON that calls on the FallbackAgent’s browser‑use actions.
  5. Uses an auto‑login workaround: when logging in, the agent injects GOOGLE_USER and GOOGLE_PW (from env)
     into the login fields. If 2FA is encountered, the user is prompted for the code.
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
        """Initialize the API handler with OAuth2 credentials."""
        self.credentials_file = credentials_file
        self.service = None
        self.account_info = None
        self._build_service()

    def _build_service(self):
        try:
            creds = Credentials.from_authorized_user_file(self.credentials_file)
            self.service = build('mybusiness', 'v4', credentials=creds)
            logging.info("Google Business Profile API service built successfully.")
        except Exception as e:
            logging.error(f"Error building API service: {e}")
            self.service = None

    def check_organization_status(self) -> dict:
        """Check whether the API account is an Organization account."""
        if not self.service:
            return {"valid": False, "error": "API service not built"}
        try:
            result = self.service.accounts().list().execute()
            accounts = result.get("accounts", [])
            if not accounts:
                return {"valid": False, "error": "No accounts found."}
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
        """Update business info via the API."""
        if not self.service:
            return {"success": False, "error": "No API service"}
        try:
            location = self.service.accounts().locations().get(name=location_name).execute()
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
        """Respond to a review via the API."""
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
        """Create a new post via the API."""
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
        """Upload a photo via the API."""
        if not self.service:
            return {"success": False, "error": "No API service"}
        try:
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
        """Initialize the fallback agent using browser-use (which uses Playwright)."""
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
        Launch a visible login flow using Selenium to collect cookies.
        Auto‑fill login credentials from environment variables.
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
        driver.implicitly_wait(5)
        try:
            username_field = driver.find_element_by_name("identifier")
            password_field = driver.find_element_by_name("password")
            username = os.getenv("GOOGLE_USER")
            password = os.getenv("GOOGLE_PW")
            if username and password:
                username_field.clear()
                username_field.send_keys(username)
                driver.find_element_by_id("identifierNext").click()
                driver.implicitly_wait(5)
                password_field = driver.find_element_by_name("password")
                password_field.clear()
                password_field.send_keys(password)
                driver.find_element_by_id("passwordNext").click()
                logging.info(f"[{self.business_id}] Auto‑login attempted with environment credentials.")
            else:
                logging.warning("GOOGLE_USER or GOOGLE_PW not set; falling back to manual login.")
                input(f"[{self.business_id}] Complete the login manually, then press Enter...")
        except Exception as e:
            logging.warning(f"[{self.business_id}] Auto‑login error: {e}. Falling back to manual login.")
            input(f"[{self.business_id}] Complete the login manually, then press Enter...")

        logging.info(f"[{self.business_id}] Checking for 2FA requirements.")
        try:
            otp_field = driver.find_element_by_name("otp")
            otp_code = input(f"[{self.business_id}] 2FA detected. Enter OTP code: ")
            otp_field.clear()
            otp_field.send_keys(otp_code)
            driver.find_element_by_id("verifyOtp").click()
            logging.info(f"[{self.business_id}] 2FA code submitted.")
        except Exception:
            pass

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
        logging.info(f"[{self.business_id} Fallback] Update action succeeded on {edit_url}")
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

    async def compliance_check(self, business_url: str) -> dict:
        """
        Perform a compliance check by scraping key sections (posts, reviews, Q&A) and updating the database.
        """
        from playwright.async_api import Page
        import os, json, uuid
        from datetime import datetime
        from gbp_django.models import Business, Post, Review, QandA, AutomationLog

        page: Page = await self.context.new_page()
        compliance_data = {}
        sections = {
            "posts": f"{business_url}/posts",
            "reviews": f"{business_url}/reviews",
            "qna": f"{business_url}/qna"
        }
        for section, url in sections.items():
            logging.info(f"[{self.business_id} Compliance] Checking {section} at {url}")
            await page.goto(url)
            await page.wait_for_timeout(2000)
            items = await page.query_selector_all(".item")
            section_data = [(await item.inner_text()).strip() for item in items]
            compliance_data[section] = section_data

        await page.close()

        compliance_file = os.path.join(os.path.dirname(self.cookies_file), f"compliance_{self.business_id}.json")
        new_changes = {}
        if os.path.exists(compliance_file):
            with open(compliance_file, "r") as f:
                old_data = json.load(f)
            for section in compliance_data:
                old_section_data = old_data.get(section, [])
                new_entries = [entry for entry in compliance_data[section] if entry not in old_section_data]
                if new_entries:
                    new_changes[section] = new_entries
        else:
            new_changes = compliance_data

        with open(compliance_file, "w") as f:
            json.dump(compliance_data, f, indent=2)
        logging.info(f"[{self.business_id} Compliance] New changes: {new_changes}")

        try:
            business_obj = Business.objects.get(business_id=self.business_id)
        except Business.DoesNotExist:
            logging.error(f"[{self.business_id} Compliance] Business not found in DB.")
            return {"status": "failed", "error": "Business not found"}

        if "posts" in new_changes:
            for post_content in new_changes["posts"]:
                if not Post.objects.filter(business=business_obj, content=post_content).exists():
                    Post.objects.create(
                        business=business_obj,
                        post_id=str(uuid.uuid4()),
                        post_type="compliance",
                        content=post_content,
                        status="completed"
                    )
        if "reviews" in new_changes:
            for review_content in new_changes["reviews"]:
                if not Review.objects.filter(business=business_obj, content=review_content).exists():
                    Review.objects.create(
                        business=business_obj,
                        review_id=str(uuid.uuid4()),
                        content=review_content,
                        rating=5,
                        responded=False
                    )
        if "qna" in new_changes:
            for question_content in new_changes["qna"]:
                if not QandA.objects.filter(business=business_obj, question=question_content).exists():
                    QandA.objects.create(
                        business=business_obj,
                        question=question_content,
                        answered=False
                    )

        score = sum(len(new_changes.get(section, [])) for section in new_changes)
        business_obj.compliance_score = score
        business_obj.save(update_fields=["compliance_score"])

        AutomationLog.objects.create(
            business_id=self.business_id,
            action_type="SYSTEM_ALERT",
            details={"compliance_check": new_changes},
            status="COMPLETED",
            user_id="system",
            executed_at=datetime.now()
        )

        return {"status": "success", "new_changes": new_changes, "compliance_data": compliance_data}


###############################################################################
# BusinessProfileManager: Managing Multiple Business Accounts
###############################################################################
class BusinessProfileManager:
    def __init__(self, businesses: dict, cookies_folder: str, chrome_path: str,
                 credentials_file: str, headless: bool = True):
        """
        Initialize agents for multiple businesses.
        """
        self.businesses = businesses
        self.cookies_folder = cookies_folder
        self.chrome_path = chrome_path
        self.credentials_file = credentials_file
        self.headless = headless
        self.api_handler = GoogleBusinessAPIHandler(credentials_file)
        self.fallback_agents = {}
        for business_id in businesses:
            cookie_file = os.path.join(cookies_folder, f"cookies_{business_id}.json")
            self.fallback_agents[business_id] = FallbackGBPAgent(business_id, cookie_file, chrome_path,
                                                                 headless=headless)
            logging.info(f"[{business_id}] Fallback agent connected.");

    async def process_business(self, business_id: str, task_data: dict) -> None:
        """
        Process automation tasks for a business.
        """
        business_url = self.businesses[business_id]
        from gbp_django.models import Business
        business_obj = Business.objects.get(business_id=business_id)
        location_name = business_obj.google_location_id or task_data.get("location_name")
        if not location_name:
            logging.error(f"[{business_id}] Missing Google location ID.")
            raise Exception("Missing Google location ID for business update")
        logging.info(f"[{business_id}] Processing tasks for {business_url} with location: {location_name}")

        org_status = self.api_handler.check_organization_status()
        if not org_status.get("valid", False):
            logging.warning(f"[{business_id}] API account invalid: {org_status.get('error')}")
            logging.info(f"[{business_id}] Using fallback automation.")
            await self._run_fallback_flow(business_id, business_url, task_data)

        if not org_status.get("valid", False):
            api_success = False
            results = "Fallback automation executed"
        else:
            api_success = True
            results = {}
            try:
                results["update"] = self.api_handler.update_business_info(location_name, task_data["new_hours"],
                                                                          task_data["new_website"])
                logging.info(f"[COMPLIANCE] API update task completed for business {business_id}")
                if not results["update"].get("success"):
                    api_success = False
                    raise Exception("update_business_info failed.")
                results["respond"] = self.api_handler.respond_to_review(location_name, task_data["review_id"],
                                                                        task_data["review_response"])
                if not results["respond"].get("success"):
                    api_success = False
                    raise Exception("respond_to_review failed.")
                results["post"] = self.api_handler.schedule_post(location_name, task_data["post_content"],
                                                                 hours_from_now=1)
                if not results["post"].get("success"):
                    api_success = False
                    raise Exception("schedule_post failed.")
                results["upload"] = self.api_handler.upload_photo(location_name, task_data["photo_path"])
                if not results["upload"].get("success"):
                    api_success = False
                    raise Exception("upload_photo failed.")
                logging.info(f"[{business_id}] API tasks completed: {results}")
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
        report_data = {"results": results, "method": method_used}
        try:
            executed_at = datetime.now().isoformat()
            EmailService.send_automation_report(business_id, "Automation", report_data, executed_at)
        except Exception as e:
            logging.error(f"[{business_id}] Email report error: {e}")
            api_success = False

        if not api_success:
            logging.info(f"[{business_id}] Falling back to browser automation.")
            await self._run_fallback_flow(business_id, business_url, task_data)

    async def _run_fallback_flow(self, business_id: str, business_url: str, task_data: dict) -> None:
        agent = self.fallback_agents[business_id]
        try:
            logging.info(f"[{business_id}][AGENT] Initiating update_business_info via fallback agent");
            update_res = await agent.update_business_info(business_url, task_data["new_hours"],
                                                          task_data["new_website"])
            logging.info(f"[{business_id}][AGENT] Update result: {update_res}");
            logging.info(f"[{business_id}][AGENT] Initiating respond_review via fallback agent");
            respond_res = await agent.respond_review(business_url, task_data["review_text"],
                                                     task_data["review_response"])
            logging.info(f"[{business_id}][AGENT] Respond result: {respond_res}");
            logging.info(f"[{business_id}][AGENT] Initiating schedule_post via fallback agent");
            post_res = await agent.schedule_post(business_url, task_data["post_content"], hours_from_now=1)
            logging.info(f"[{business_id}][AGENT] Post result: {post_res}");
            logging.info(f"[{business_id}][AGENT] Initiating upload_photo via fallback agent");
            upload_res = await agent.upload_photo(business_url, task_data["photo_path"])
            logging.info(f"[{business_id}][AGENT] Upload result: {upload_res}");
            logging.info(f"[{business_id} Fallback] All fallback tasks completed.");
        except Exception as e:
            logging.error(f"[{business_id} Fallback] Error in fallback flow: {e}");

    async def run_all_businesses(self, tasks_data: dict) -> None:
        tasks = [self.process_business(biz_id, tasks_data[biz_id]) for biz_id in tasks_data]
        await asyncio.gather(*tasks)

    async def run_structured_compliance_flow(self) -> None:
        """
        Execute the compliance flow step-by-step using the reasoning model.
        """
        logging.info("[COMPLIANCE] Running structured compliance flow for all businesses.");
        from model_interface import get_llm_model
        from compliance_policy import get_compliance_policy

        llm = get_llm_model()
        pre_prompt = get_compliance_policy()

        from gbp_django.models import Business
        for business in Business.objects.all():
            business_url = self.businesses.get(business.business_id)
            if not business_url:
                continue

            logging.info(f"[COMPLIANCE] Initiating reasoning model for business {business.business_id}");
            logging.info(f"[COMPLIANCE] Starting structured compliance flow for business {business.business_id}");
            prompt = (
                f"Business ID: {business.business_id}\n"
                f"Business Name: {business.business_name}\n"
                f"Website: {business.website_url}\n"
                f"Compliance Score: {business.compliance_score}\n"
                "Generate a structured plan with actions to ensure compliance. "
                "Prioritize updating missing or invalid mandatory details first, then content compliance."
            )
            logging.info(f"[REASONER] Executing structured reasoning with prompt: {prompt}")
            logging.info("[REASONER] Prompting reasoning model now...")
            from gbp_django.utils.llm_reasoning import generate_compliance_reasoning
            reasoning_result = generate_compliance_reasoning({
                "business_id": business.business_id,
                "business_name": business.business_name,
                "website": business.website_url,
                "compliance_score": business.compliance_score
            })
            logging.info(f"[{business.business_id} Structured Compliance] Reasoning output: {reasoning_result}")
            logging.info(
                f"[COMPLIANCE] Structured compliance actions generated for business {business.business_id}: {len(reasoning_result.get('actions', []))} actions")

            # Pass the first instruction to the fallback agent and log the result.
            agent = self.fallback_agents.get(business.business_id)
            if agent:
                firstInst = None
                for item in reasoning_result.get("actions", []):
                    if item.get("type") == "instruction":
                        firstInst = item
                        break
                if firstInst:
                    logging.info(
                        f"[{business.business_id} Instruction] Passing first instruction to agent: " + firstInst.get(
                            "details"))
                    try:
                        instruction_result = await agent.execute_instruction(firstInst.get("details"))
                        logging.info(
                            f"[{business.business_id} Instruction] Execution result: " + str(instruction_result))
                        reasoning_result.get("actions", []).remove(firstInst)
                    except Exception as ex:
                        logging.error(f"[{business.business_id} Instruction] Error executing instruction: " + str(ex))
                else:
                    logging.info(f"[{business.business_id} Instruction] No instruction action found.")
            else:
                logging.error(f"No fallback agent found for business {business.business_id}")

            actions = reasoning_result.get("actions", [])
            while actions:
                for action in actions:
                    logging.debug(f"Structured compliance action: {action}")
                    action_type = action.get("type")
                    target = action.get("target")
                    details = action.get("details")
                    logging.info(f"[{business.business_id} Compliance Action] {action_type} on {target}: {details}")
                    agent = self.fallback_agents.get(business.business_id)
                    if not agent:
                        logging.error(f"No fallback agent found for business {business.business_id}")
                        continue
                    try:
                        if target == "website" and action_type in ("update", "fallback_update"):
                            new_website = details  # Parse details as needed
                            logging.info(
                                f"[{business.business_id}][AGENT] Initiating fallback update for website: {new_website}")
                            result = await agent.update_business_info(business_url,
                                                                      getattr(business, "hours", "Mon-Fri 09:00-17:00"),
                                                                      new_website)
                            logging.info(f"[{business.business_id}][AGENT] Fallback update result: {result}")
                        elif target in ["reviews", "qna", "posts", "photos"] and action_type in (
                        "verify", "fallback_verify"):
                            logging.info(
                                f"[{business.business_id}][AGENT] Initiating fallback compliance check for target: {target}")
                            result = await agent.compliance_check(business_url)
                            logging.info(f"[{business.business_id}][AGENT] Fallback compliance check result: {result}")
                        elif action_type == "alert":
                            input(
                                f"[{business.business_id}] Intervention required for {target}: {details}. Press Enter after action.")
                        elif action_type == "log":
                            logging.info(f"[{business.business_id} LOG] {details}")
                        elif action_type == "instruction":
                            logging.info(f"[{business.business_id}][AGENT] Executing instruction: {details}")
                            if hasattr(agent, "execute_instruction"):
                                result = await agent.execute_instruction(details)
                                logging.info(f"[{business.business_id}][AGENT] Instruction result: {result}")
                            else:
                                logging.info(
                                    f"[{business.business_id}][AGENT] No execute_instruction method available; skipping instruction.")
                    except Exception as e:
                        logging.error(
                            f"[{business.business_id}] Error executing fallback action {action_type} on {target}: {e}")
                    logging.info(f"[{business.business_id} Compliance] Completed action: {action_type} on {target}")
                # Feed back the executed actions to the reasoning model to get next instructions.
                feedback_data = {
                    "business_id": business.business_id,
                    "executed_actions": actions
                }
                logging.info(
                    f"[{business.business_id} Feedback] Sending executed actions to reasoning model: {feedback_data}")
                new_reasoning = generate_compliance_reasoning(feedback_data)
                actions = new_reasoning.get("actions", [])
                if not actions:
                    logging.info(
                        f"[{business.business_id} Feedback] No further actions received from reasoning model. Exiting feedback loop.")
                    break
            logging.info("[COMPLIANCE] Structured compliance flow completed.")

    async def run_compliance_checks(self) -> None:
        tasks = [self.fallback_agents[biz_id].compliance_check(self.businesses[biz_id]) for biz_id in self.businesses]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for biz_id, result in zip(self.businesses.keys(), results):
            logging.info(f"[{biz_id}] Compliance check result: {result}")


###############################################################################
# Onboarding Function: Add a New Business Account
###############################################################################
def onboard_new_business(cookies_folder: str, chrome_path: str) -> tuple:
    """Interactively onboard a new business and collect cookies."""
    business_id = input("Enter the new business ID (unique identifier): ").strip()
    business_url = input("Enter the business URL (e.g., https://business.google.com/your_business_id): ").strip()
    cookie_file = os.path.join(cookies_folder, f"cookies_{business_id}.json")
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

    chrome_path = r"/usr/bin/chromium-browser"
    credentials_file = os.path.join(base_dir, "credentials.json")

    businesses = {}
    add_new = input("Would you like to add a new business? (y/n): ").strip().lower()
    if add_new == "y":
        new_id, new_url = onboard_new_business(cookies_folder, chrome_path)
        businesses[new_id] = new_url
    else:
        businesses = {
            "business1": "https://business.google.com/your_business_id1",
            "business2": "https://business.google.com/your_business_id2"
        }

    tasks_data = {
        biz_id: {
            "location_name": "accounts/EXAMPLE/locations/EXAMPLE",
            "new_hours": "Mon-Fri 09:00-17:00",
            "new_website": f"https://new-website-for-{biz_id}.example.com",
            "review_id": "reviewEXAMPLE",
            "review_text": "The service was excellent!",
            "review_response": "Thank you for your kind feedback! We are thrilled to serve you.",
            "post_content": "We're excited to announce a new promotion this week!",
            "photo_path": r"/path/to/photo.jpg"
        }
        for biz_id in businesses
    }

    manager = BusinessProfileManager(businesses, cookies_folder, chrome_path, credentials_file, headless=True)

    try:
        asyncio.run(manager.run_all_businesses(tasks_data))
    except Exception as e:
        logging.error(f"Error running tasks for all businesses: {e}")

    run_compliance = input("Would you like to run a compliance check? (y/n): ").strip().lower()
    if run_compliance == "y":
        try:
            asyncio.run(manager.run_compliance_checks())
        except Exception as e:
            logging.error(f"Error running compliance checks: {e}")

    run_structured = input("Run structured compliance flow (prioritized, step-by-step)? (y/n): ").strip().lower()
    if run_structured == "y":
        try:
            asyncio.run(manager.run_structured_compliance_flow())
        except Exception as e:
            logging.error(f"Error running structured compliance flow: {e}")
