import os
import random
from datetime import datetime, timedelta
from django.conf import settings
from ..api.media_management import upload_photo as api_upload_photo
from ..api.post_management import create_post as api_create_post
from ..api.qa_management import answer_question, post_question
from ..api.review_management import respond_to_review
from ..models import Business, Review, QandA
from ..utils.logging_utils import log_api_request

def upload_photo(business):
    """
    Upload a photo to Google Business Profile
    """
    try:
        # Get access token from business user
        access_token = business.user.google_access_token
        
        # Example photo data - this should be customized per business
        photo_data = {
            "mediaFormat": "PHOTO",
            "locationAssociation": {
                "category": "PROFILE"
            },
            "media": "BASE64_ENCODED_PHOTO_DATA"  # Replace with actual photo data
        }
        
        result = api_upload_photo(
            access_token=access_token,
            account_id=business.business_id,
            location_id=business.business_id,
            photo_data=photo_data
        )
        
        log_api_request(
            user_id=business.user.id,
            business_id=business.id,
            action_type='photo_upload',
            details='Weekly photo upload completed'
        )
        
        return result
    except Exception as e:
        log_api_request(
            user_id=business.user.id,
            business_id=business.id,
            action_type='photo_upload',
            status='error',
            error=e
        )
        raise

def generate_post(business):
    """
    Generate and create a post on Google Business Profile
    """
    try:
        access_token = business.user.google_access_token
        
        # Example post data - should be customized per business
        post_data = {
            "languageCode": "en",
            "summary": f"Check out our latest updates! {datetime.now().strftime('%B %Y')}",
            "topicType": "STANDARD",
            "media": [{
                "mediaFormat": "PHOTO",
                "sourceUrl": "PHOTO_URL"  # Replace with actual photo URL
            }]
        }
        
        result = api_create_post(
            access_token=access_token,
            account_id=business.business_id,
            location_id=business.business_id,
            post_data=post_data
        )
        
        log_api_request(
            user_id=business.user.id,
            business_id=business.id,
            action_type='post_creation',
            details='Weekly post created'
        )
        
        return result
    except Exception as e:
        log_api_request(
            user_id=business.user.id,
            business_id=business.id,
            action_type='post_creation',
            status='error',
            error=e
        )
        raise

def update_qa(business):
    """
    Update Q&A section on Google Business Profile
    """
    try:
        access_token = business.user.google_access_token
        
        # Get existing Q&A
        existing_qa = QandA.objects.filter(business=business, answered=False)
        
        for qa in existing_qa:
            # Example answer data
            answer_data = {
                "answer": {
                    "text": generate_answer(qa.question, business.id)
                }
            }
            
            result = answer_question(
                access_token=access_token,
                account_id=business.business_id,
                location_id=business.business_id,
                question_id=qa.id,
                answer_data=answer_data
            )
            
            qa.answered = True
            qa.save()
            
            log_api_request(
                user_id=business.user.id,
                business_id=business.id,
                action_type='qa_update',
                details=f'Answered question: {qa.question}'
            )
        
        return "Q&A updates completed"
    except Exception as e:
        log_api_request(
            user_id=business.user.id,
            business_id=business.id,
            action_type='qa_update',
            status='error',
            error=e
        )
        raise

def respond_to_reviews(business):
    """
    Respond to new reviews on Google Business Profile
    """
    try:
        access_token = business.user.google_access_token
        
        # Get unresponded reviews
        unresponded_reviews = Review.objects.filter(
            business=business,
            responded=False
        )
        
        for review in unresponded_reviews:
            # Generate appropriate response based on rating
            response_text = generate_review_response(
                review.rating, 
                review.content,
                business.id
            )
            
            response_data = {
                "comment": response_text
            }
            
            result = respond_to_review(
                access_token=access_token,
                account_id=business.business_id,
                location_id=business.business_id,
                review_id=review.review_id,
                response_data=response_data
            )
            
            review.responded = True
            review.response = response_text
            review.save()
            
            log_api_request(
                user_id=business.user.id,
                business_id=business.id,
                action_type='review_response',
                details=f'Responded to review ID: {review.review_id}'
            )
        
        return "Review responses completed"
    except Exception as e:
        log_api_request(
            user_id=business.user.id,
            business_id=business.id,
            action_type='review_response',
            status='error',
            error=e
        )
        raise

from .rag_utils import answer_question

def generate_answer(question, business_id):
    """Generate context-aware answers using RAG"""
    return answer_question(
        query=question,
        business_id=business_id,
        chat_history=[],
    )

def generate_review_response(rating, content, business_id):
    """Generate context-aware review responses using RAG"""
    context = f"Review rating: {rating}/5\nReview content: {content}"
    return answer_question(
        query="Generate an appropriate professional response to this review: " + content,
        business_id=business_id,
        chat_history=[{
            'role': 'system',
            'content': f"Business context: {context}\nResponse requirements: Maintain professional tone, address specific feedback, offer solution if needed"
        }]
    )
