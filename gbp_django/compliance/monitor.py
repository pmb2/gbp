#!/usr/bin/env python3
"""
Compliance Monitoring Backend for Google Business Profile Automation

This script monitors key compliance criteria for each business account:
  - Reviews must be responded to within 24 hours.
  - Questions must be answered within 12 hours.
  - At least one post should be scheduled/published every 7 days.

If any of these criteria are not met, the script triggers the appropriate
automation tasks (using either our official API integration or fallback methods).

Replace the dummy “get_latest_*” functions with your real API calls or database queries to retrieve the last review, question, or post dates for each business. (For example, your Google Business Profile API integration should return the timestamp of the last review response, etc.)
"""

import asyncio
import logging
from datetime import datetime, timedelta

# Set up logging.
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

# Compliance thresholds (customize as needed)
REVIEW_RESPONSE_THRESHOLD = timedelta(hours=24)
QUESTION_RESPONSE_THRESHOLD = timedelta(hours=12)
POST_FREQUENCY_THRESHOLD = timedelta(days=7)

# Dummy functions to simulate retrieving the latest timestamps.
# Replace these with your real functions that query your API or database.
async def get_latest_review_date(business_id: str) -> datetime:
    # Example: return the timestamp of the last unanswered review.
    # For demonstration, we simulate an overdue review.
    return datetime.now() - timedelta(hours=25)

async def get_latest_question_date(business_id: str) -> datetime:
    # Example: return the timestamp of the last unanswered question.
    # For demonstration, we simulate one that’s within threshold.
    return datetime.now() - timedelta(hours=10)

async def get_last_post_date(business_id: str) -> datetime:
    # Example: return the timestamp of the last published/scheduled post.
    # For demonstration, we simulate an overdue post.
    return datetime.now() - timedelta(days=8)

# Dummy automation trigger functions.
# Replace these with calls to your automation routines.
async def trigger_review_response_automation(business_id: str):
    logging.info(f"[{business_id}] Triggering review response automation task.")
    # Call your API or fallback method here.
    
async def trigger_question_response_automation(business_id: str):
    logging.info(f"[{business_id}] Triggering question response automation task.")
    
async def trigger_post_automation(business_id: str):
    logging.info(f"[{business_id}] Triggering new post automation task.")

# Compliance check functions.
async def check_review_compliance(business_id: str):
    latest_review = await get_latest_review_date(business_id)
    if datetime.now() - latest_review > REVIEW_RESPONSE_THRESHOLD:
        logging.warning(f"[{business_id}] Review response is overdue (last review at {latest_review}).")
        await trigger_review_response_automation(business_id)
    else:
        logging.info(f"[{business_id}] Review responses are compliant.")

async def check_question_compliance(business_id: str):
    latest_question = await get_latest_question_date(business_id)
    if datetime.now() - latest_question > QUESTION_RESPONSE_THRESHOLD:
        logging.warning(f"[{business_id}] Question response is overdue (last question at {latest_question}).")
        await trigger_question_response_automation(business_id)
    else:
        logging.info(f"[{business_id}] Question responses are compliant.")

async def check_post_compliance(business_id: str):
    last_post = await get_last_post_date(business_id)
    if datetime.now() - last_post > POST_FREQUENCY_THRESHOLD:
        logging.warning(f"[{business_id}] No post in the last 7 days (last post at {last_post}).")
        await trigger_post_automation(business_id)
    else:
        logging.info(f"[{business_id}] Posting frequency is compliant.")

# Monitor compliance for a single business.
async def monitor_compliance(business_id: str):
    logging.info(f"[{business_id}] Running compliance checks...")
    # Determine if criteria are met
    review_date = await get_latest_review_date(business_id)
    question_date = await get_latest_question_date(business_id)
    post_date = await get_last_post_date(business_id)
    now = datetime.now()
    review_overdue = now - review_date > REVIEW_RESPONSE_THRESHOLD
    question_overdue = now - question_date > QUESTION_RESPONSE_THRESHOLD
    post_overdue = now - post_date > POST_FREQUENCY_THRESHOLD

    # Run automation triggers as needed based on overdue status
    if review_overdue:
        await trigger_review_response_automation(business_id)
    if question_overdue:
        await trigger_question_response_automation(business_id)
    if post_overdue:
        await trigger_post_automation(business_id)

    logging.info(f"[{business_id}] Compliance checks completed.")

    # Compute compliance score: each metric gives 100 if compliant, else 0; average for overall score.
    review_score = 0 if review_overdue else 100
    question_score = 0 if question_overdue else 100
    post_score = 0 if post_overdue else 100
    overall_score = (review_score + question_score + post_score) // 3

    # Update the Business record with the calculated compliance score
    try:
        from gbp_django.models import Business
        business = Business.objects.get(business_id=business_id)
        business.compliance_score = overall_score
        business.save(update_fields=['compliance_score'])
        logging.info(f"[{business_id}] Updated compliance score to {overall_score}%")
    except Exception as e:
        logging.error(f"[{business_id}] Failed to update compliance score: {e}")

# Scheduler function to run the compliance check periodically.
async def compliance_scheduler(business_id: str, interval_minutes: int = 30):
    while True:
        try:
            await monitor_compliance(business_id)
        except Exception as e:
            logging.error(f"[{business_id}] Error during compliance monitoring: {e}")
        await asyncio.sleep(interval_minutes * 60)

# Run compliance monitoring for multiple businesses concurrently.
async def run_compliance_monitors(business_ids: list):
    tasks = [compliance_scheduler(biz_id) for biz_id in business_ids]
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    from gbp_django.models import Business
    # Get all active businesses (exclude ones with default 'unverified' business_id)
    business_ids = list(Business.objects.exclude(business_id='unverified').values_list('business_id', flat=True))
    logging.info(f"Monitoring compliance for {len(business_ids)} businesses: {business_ids}")
    try:
        asyncio.run(run_compliance_monitors(business_ids))
    except KeyboardInterrupt:
        logging.info("Compliance monitoring stopped by user.")
