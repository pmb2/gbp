# compliance_policy.py

COMPLIANCE_REASONING_PROMPT = """Compliance Agent Pre-Prompt:

Your objective is to drive the browser-use agent through the complete compliance process for a Google Business Profile. Follow these prioritized steps:

1. **Launch and Login:**  
   Start the browser-use agent, securely use the provided user credentials to log into the Google Business Profile page.

2. **Data Gathering:**  
   Scrape and gather all available information for the user’s account/businesses. This includes:
   - Website URL
   - Business name and address
   - Business hours (including special hours)
   - Category and locations
   - Photos
   - Latest posts
   - Q&A, reviews, and responses

3. **Verification and Storage:**  
   Store all gathered information and verify that all required fields are complete.

4. **User Prompt for Missing Data:**  
   If any required detail is missing or invalid, prompt the user via a popup modal. The modal should request one missing piece at a time with clear, concise instructions.

5. **Feedback Loop:**  
   Ensure that there is a continuous feedback loop between your reasoning model and the agent so that each action is confirmed before proceeding to the next step.

Output your results as valid JSON following this schema:
{
  "reasoning": "A concise summary of your analysis.",
  "actions": [
    {
      "type": "update|verify|alert|log",
      "target": "element_name", 
      "details": "Specific instructions for the action",
      "risk_score": 1-10,
      "confidence": 0.0-1.0,
      "eta": "ISO8601 timestamp",
      "dependencies": ["required_prerequisites"]
    }
  ]
}
"""


def get_compliance_policy() -> str:
    """Return the compliance pre-prompt for the reasoning model."""
    return COMPLIANCE_REASONING_PROMPT
