import requests
from gbp_django.models import QandA
from gbp_django import db

def store_questions_and_answers(qa_data, account_id):
    for question in qa_data.get('questions', []):
        existing_qa = QandA.query.filter_by(question=question['name']).first()
        if not existing_qa:
            new_qa = QandA(
                business_id=account_id,
                question=question.get('text', ''),
                answer=question.get('answers', [{}])[0].get('text', '') if question.get('answers') else '',
                answered=bool(question.get('answers'))
            )
            db.session.add(new_qa)
        else:
            existing_qa.answer = question.get('answers', [{}])[0].get('text', '') if question.get('answers') else ''
            existing_qa.answered = bool(question.get('answers'))
    db.session.commit()

def post_question(access_token, account_id, location_id, question_data):
    url = f"https://mybusiness.googleapis.com/v4/accounts/{account_id}/locations/{location_id}/questions"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.post(url, headers=headers, json=question_data)
    response.raise_for_status()
    return response.json()

def answer_question(access_token, account_id, location_id, question_id, answer_data):
    url = f"https://mybusiness.googleapis.com/v4/accounts/{account_id}/locations/{location_id}/questions/{question_id}/answers"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.post(url, headers=headers, json=answer_data)
    response.raise_for_status()
    return response.json()

def delete_question_or_answer(access_token, account_id, location_id, question_id):
    url = f"https://mybusiness.googleapis.com/v4/accounts/{account_id}/locations/{location_id}/questions/{question_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.delete(url, headers=headers)
    response.raise_for_status()
    return response.status_code == 204

def get_questions_and_answers(access_token, account_id, location_id):
    url = f"https://mybusiness.googleapis.com/v4/accounts/{account_id}/locations/{location_id}/questions"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()
