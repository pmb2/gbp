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
    from gbp_django.models import Business, Review
    try:
        business = Business.objects.get(business_id=business_id)
        review = Review.objects.filter(business=business).order_by('-created_at').first()
        if review:
            return review.created_at
    except Exception as e:
        logging.error(f"[COMPLIANCE] Error fetching latest review date for {business_id}: {e}")
    return datetime.now() - timedelta(hours=25)

async def get_latest_question_date(business_id: str) -> datetime:
    from gbp_django.models import Business, QandA
    try:
        business = Business.objects.get(business_id=business_id)
        qanda = QandA.objects.filter(business=business).order_by('-created_at').first()
        if qanda:
            return qanda.created_at
    except Exception as e:
        logging.error(f"[COMPLIANCE] Error fetching latest question date for {business_id}: {e}")
    return datetime.now() - timedelta(hours=10)

async def get_last_post_date(business_id: str) -> datetime:
    from gbp_django.models import Business, Post
    try:
        business = Business.objects.get(business_id=business_id)
        post = Post.objects.filter(business=business).order_by('-created_at').first()
        if post:
            return post.created_at
    except Exception as e:
        logging.error(f"[COMPLIANCE] Error fetching latest post date for {business_id}: {e}")
    return datetime.now() - timedelta(days=8)

# Dummy automation trigger functions.
# Replace these with calls to your automation routines.
async def trigger_review_response_automation(business_id: str):
    logging.info(f"[COMPLIANCE] Triggering review response automation for {business_id}")
    await asyncio.sleep(1)  # Simulate processing delay
    
async def trigger_question_response_automation(business_id: str):
    logging.info(f"[COMPLIANCE] Triggering question response automation for {business_id}")
    await asyncio.sleep(1)  # Simulate processing delay
    
async def trigger_post_automation(business_id: str):
    logging.info(f"[COMPLIANCE] Triggering post automation for {business_id}")
    await asyncio.sleep(1)  # Simulate processing delay

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
    logging.info(f"[COMPLIANCE] Starting compliance checks for Business ID: {business_id}")
    
    # Retrieve latest timestamps
    review_date = await get_latest_review_date(business_id)
    logging.info(f"[COMPLIANCE] Latest review date for {business_id}: {review_date}")
    question_date = await get_latest_question_date(business_id)
    logging.info(f"[COMPLIANCE] Latest question date for {business_id}: {question_date}")
    post_date = await get_last_post_date(business_id)
    logging.info(f"[COMPLIANCE] Latest post date for {business_id}: {post_date}")

    let_now = datetime.now()
    review_overdue = let_now - review_date > REVIEW_RESPONSE_THRESHOLD
    logging.info(f"[COMPLIANCE] Review overdue for {business_id}: {review_overdue}")
    question_overdue = let_now - question_date > QUESTION_RESPONSE_THRESHOLD
    logging.info(f"[COMPLIANCE] Question overdue for {business_id}: {question_overdue}")
    post_overdue = let_now - post_date > POST_FREQUENCY_THRESHOLD
    logging.info(f"[COMPLIANCE] Post overdue for {business_id}: {post_overdue}")

    # Run automation triggers as needed based on overdue status
    if review_overdue:
        logging.info(f"[COMPLIANCE] Triggering review response automation for {business_id}")
        await trigger_review_response_automation(business_id)
    if question_overdue:
        logging.info(f"[COMPLIANCE] Triggering question response automation for {business_id}")
        await trigger_question_response_automation(business_id)
    if post_overdue:
        logging.info(f"[COMPLIANCE] Triggering post automation for {business_id}")
        await trigger_post_automation(business_id)

    logging.info(f"[COMPLIANCE] Completed compliance triggers for {business_id}")

    # Compute compliance score: each metric gives 100 if compliant, else 0; calculate average
    review_score = 0 if review_overdue else 100
    question_score = 0 if question_overdue else 100
    post_score = 0 if post_overdue else 100
    overall_score = (review_score + question_score + post_score) // 3
    logging.info(f"[COMPLIANCE] Calculated scores for {business_id} - Review: {review_score}, Question: {question_score}, Post: {post_score}. Overall: {overall_score}%")

    # Update the Business record with the calculated compliance score
    try:
        from gbp_django.models import Business
        business = Business.objects.get(business_id=business_id)
        business.compliance_score = overall_score
        business.save(update_fields=['compliance_score'])
        logging.info(f"[COMPLIANCE] Updated compliance score for {business_id} to {overall_score}%")
    except Exception as e:
        logging.error(f"[COMPLIANCE] Error updating compliance score for {business_id}: {e}")

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
    # Get only verified businesses using the verification_status column
    business_ids = list(Business.objects.filter(verification_status='VERIFIED').values_list('business_id', flat=True))
    logging.info(f"[COMPLIANCE] Monitoring compliance for {len(business_ids)} verified businesses: {business_ids}")
    try:
        asyncio.run(run_compliance_monitors(business_ids))
    except KeyboardInterrupt:
        logging.info("[COMPLIANCE] Compliance monitoring stopped by user.")
