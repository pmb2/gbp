import json
import logging
from typing import Dict
from gbp_django.utils.model_interface import get_llm_model

# Updated Compliance Reasoning Policy for the Reasoning Model:
# This policy instructs the reasoning model to generate a step-by-step instruction list
# for the agent to follow during the compliance process. The agent is required to:
# 1. Start the browser-use agent and securely log into the Google Business Profile using
#    environment-provided credentials.
# 2. Scrape and gather all available business data including website URL, business name,
#    address, hours (and special hours), category, locations, photos, latest posts, Q&A,
#    reviews, and responses.
# 3. Verify that the required fields are complete.
# 4. If any required data is missing or invalid, instruct the agent to prompt the user via
#    a popup modal (one piece at a time) with clear instructions.
# 5. Maintain a feedback loop: if any uncertainties arise, include follow-up questions in the response.
#
# The reasoning model must output a valid JSON object with the following schema:
#
# {
#   "reasoning": "A concise summary of the compliance analysis.",
#   "steps": [
#       {
#           "instruction": "Step-by-step instruction for the agent.",
#           "expected_outcome": "What should be achieved in this step."
#       },
#       ...
#   ],
#   "questions": [ "Any clarifying questions the agent has, if applicable." ]
# }

COMPLIANCE_REASONING_PROMPT = """**Compliance Orchestration Protocol v3.0**

Your objective is to guide the browser-use agent through the complete compliance process for a Google Business Profile. Follow these priorities:

1. **Data Collection:**  
   Command the agent to scrape and gather all available business data including website URL, business name, address, business hours (with special hours), category, locations, photos, latest posts, Q&A, reviews, and responses.

2. **Data Verification & Storage:**  
   Ensure that the agent stores all gathered data and verifies that all required fields are complete and valid.

3. **User Prompt for Missing Data:**  
   If any required data is missing or invalid, instruct the agent to prompt the user via a popup modal for that missing piece—one item at a time—with clear instructions.

4. **Feedback Loop:**  
   If the agent has any questions or uncertainties during any step, ask for clarification. Include these as follow-up questions in your output.

Output a valid JSON object with the following keys:
{
  "reasoning": "A concise summary of your analysis.",
  "steps": [
    {
      "instruction": "Step-by-step instruction for the agent to perform.",
      "expected_outcome": "Expected outcome for this step."
    }
  ],
  "questions": ["Any clarifying questions, if applicable."]
}
"""


def get_compliance_policy() -> str:
    """Return the compliance pre-prompt for the reasoning model."""
    return COMPLIANCE_REASONING_PROMPT


def generate_reasoning_response(pre_prompt: str, prompt: str) -> Dict:
    """
    Generate a reasoning response using the configured LLM.

    Args:
        pre_prompt (str): Pre-prompt with instructions and context.
        prompt (str): The data to analyze.

    Returns:
        Dict: A dictionary containing a "reasoning" summary, a list of "steps", and "questions".
    """
    llm = get_llm_model()
    full_prompt = f"{pre_prompt}\n---\n{prompt}"
    logging.debug("Full prompt for reasoning: " + full_prompt)

    try:
        if hasattr(llm, "structured_reasoning"):
            response = llm.structured_reasoning(pre_prompt, full_prompt)
        else:
            from groq import Groq
            client = Groq()
            completion = client.chat.completions.create(
                model="deepseek-r1-distill-llama-70b",
                messages=[{
                    "role": "user",
                    "content": full_prompt
                }],
                temperature=0.6,
                max_completion_tokens=1024,
                top_p=0.95,
                stream=True,
                reasoning_format="raw"
            )
            response_text = ""
            for chunk in completion:
                response_text += (chunk.choices[0].delta.content or "")
            if not response_text.strip():
                raise ValueError("Empty response from LLM")
            json_start = response_text.find('{')
            if json_start != -1:
                response_text = response_text[json_start:]
            try:
                decoder = json.JSONDecoder()
                response_obj, idx = decoder.raw_decode(response_text)
                response = response_obj
            except json.JSONDecodeError as json_err:
                logging.error("Failed to parse LLM response as JSON. Raw response:" + response_text)
                raise ValueError("Invalid JSON from LLM: " + str(json_err))
    except Exception as e:
        response = {
            "reasoning": f"Error generating reasoning response: {str(e)}",
            "steps": [],
            "questions": []
        }
    logging.debug("Reasoning model raw output: " + str(response))
    return response


def generate_compliance_reasoning(data: Dict) -> Dict:
    """
    Generate reasoning output specifically for compliance checks.

    Args:
        data (Dict): Compliance data to be analyzed.

    Returns:
        Dict: Structured reasoning analysis with step-by-step instructions and any clarifying questions.
    """
    prompt = json.dumps(data, indent=2)
    return generate_reasoning_response(get_compliance_policy(), prompt)
