import json
from typing import Dict
from gbp_django.utils.model_interface import get_llm_model

# Compliance Checklist Policy for Reasoning Model:
# - Verify the completeness of the business profile: Info, Hours & Attributes.
# - Confirm regularity of content posts, review responses, Q&A replies, and photo updates.
# - For any item below the expected threshold:
#    • Specify whether human intervention is required or a specific update is needed.
# - For compliant items, report the last update time.
# - Structure output as valid JSON with:
#    • "reasoning": A short bulleted summary.
#    • "actions": A list of action objects containing "type", "target", "details", "risk_score", and "confidence".
# - Also include a sub-list of task statuses summarizing current progress and next steps.
COMPLIANCE_CHECKLIST_POLICY = (
    "Compliance Checklist Policy:\n"
    "- Validate business profile completeness (Info, Hours, & Attributes).\n"
    "- Check regular content posts, review responses, Q&A, and fresh photos.\n"
    "- If an item is non-compliant:\n"
    "   • Recommend either a manual update ('Human intervention required') or an automated fix.\n"
    "- If compliant, report last update as 'Updated recently' with the corresponding timestamp.\n"
    "- Output must be valid JSON with keys \"reasoning\" and \"actions\".\n"
    "- Include a summary sub-list of current task status and next steps for each item."
)

def generate_reasoning_response(pre_prompt: str, prompt: str) -> Dict:
    """
    Generate a reasoning response using the configured LLM.
    
    Args:
        pre_prompt (str): Pre‑prompt with instructions and context.
        prompt (str): The data to analyze.
        
    Returns:
        Dict: A dictionary containing a "reasoning" summary and a list of "actions".
    """
    llm = get_llm_model()
    full_prompt = f"{pre_prompt}\n---\n{prompt}"
    
    try:
        if hasattr(llm, "structured_reasoning"):
            response = llm.structured_reasoning(pre_prompt, full_prompt)
        else:
            response_text = llm.generate_response(full_prompt, "")
            response = json.loads(response_text)
    except Exception as e:
        response = {
            "reasoning": f"Error generating reasoning response: {str(e)}",
            "actions": []
        }
    return response

def generate_compliance_reasoning(data: Dict) -> Dict:
    """
    Generate reasoning output specifically for compliance checks.
    
    Args:
        data (Dict): Compliance data to be analyzed.
        
    Returns:
        Dict: Structured reasoning analysis with recommended actions.
    """
    prompt = json.dumps(data, indent=2)
    return generate_reasoning_response(COMPLIANCE_CHECKLIST_POLICY, prompt)
