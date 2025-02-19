import os
import json
import asyncio
import logging

from django.http import JsonResponse, HttpResponseNotFound, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt

from gbp_django.models import Business
from gbp_django.utils.llm_reasoning import generate_compliance_reasoning
from gbp_django.utils.automations import FallbackGBPAgent

@csrf_exempt
def automation_fallback(request, business_id):
    """
    API endpoint to trigger automation fallback for a business.
    It uses the compliance reasoning model to generate instructions and then executes them using the fallback agent.
    """
    if request.method != "POST":
        return HttpResponseBadRequest("Only POST method is allowed.")

    try:
        business = Business.objects.get(business_id=business_id)
    except Business.DoesNotExist:
        return HttpResponseNotFound("Business not found.")

    # Setup cookies folder and cookie file for the fallback agent.
    base_dir = os.path.dirname(os.path.abspath(__file__))
    cookies_folder = os.path.join(base_dir, "browser_cookies")
    os.makedirs(cookies_folder, exist_ok=True)
    cookie_file = os.path.join(cookies_folder, f"cookies_{business_id}.json")
    chrome_path = "/usr/bin/chromium-browser"

    # Initialize the fallback agent.
    agent = FallbackGBPAgent(business_id, cookie_file, chrome_path, headless=True)

    # Generate reasoning output using the compliance reasoning model.
    reasoning_output = generate_compliance_reasoning({
         "business_id": business.business_id,
         "business_name": business.business_name,
         "website": business.website_url,
         "compliance_score": business.compliance_score
    })

    actions = reasoning_output.get("actions", [])
    results = []

    async def process_actions():
        nonlocal results
        for action in actions:
            action_type = action.get("type")
            target = action.get("target")
            details = action.get("details")
            logging.info(f"[{business.business_id} Automation] Processing action: {action}")
            if target == "website" and action_type in ("update", "fallback_update"):
                result = await agent.update_business_info(
                    business_url=business.website_url,
                    new_hours=getattr(business, "hours", "Mon-Fri 09:00-17:00"),
                    new_website=details
                )
                results.append({"action": action, "result": result})
            else:
                logging.info(f"[{business.business_id} Automation] No handler for action: {action}")
                results.append({"action": action, "result": "No handler implemented."})

    try:
        asyncio.run(process_actions())
    except Exception as proc_e:
        logging.error(f"Error while processing automation actions: {proc_e}")
        return JsonResponse({"error": str(proc_e)}, status=500)

    response_data = {
         "message": "Automation fallback executed.",
         "reasoning": reasoning_output,
         "results": results
    }
    return JsonResponse(response_data)
