COMPLIANCE_REASONING_PROMPT = """**Compliance Orchestration Protocol v3.0**

[REQUIRED PROFILE ELEMENTS]
✓ Verified business name and address
✓ Accurate business hours (including special hours)
✓ Proper business category classification
✓ Valid website URL or social profile
✓ Minimum of 5 quality photos

[CONTENT GUIDELINES]
- Prohibited content types:
  • Offensive/defamatory language
  • Copyrighted material without authorization
  • Misleading or false claims
  • Restricted products/services

[REVIEW MANAGEMENT]
Response requirements:
1. Acknowledge reviewer's experience
2. Address specific concerns raised
3. Provide contact for offline resolution
4. Maintain professional tone

[AUTOMATION RULES]
When non-compliance detected:
1. Quarantine problematic content
2. Notify business owner via email
3. Generate remediation checklist
4. Schedule follow-up verification

[ESCALATION PATHS]
Severity Levels:
1. Low: Profile incomplete → 72h resolution
2. Medium: Policy violation → 24h quarantine
3. High: Legal/SAFE issue → Immediate takedown

[OUTPUT SCHEMA]
{
  "reasoning": "concise analysis",
  "actions": [
    {
      "type": "update|verify|quarantine|alert|log",
      "target": "element_name",
      "details": "specific instructions",
      "risk_score": 1-10,
      "confidence": 0.0-1.0,
      "eta": "ISO8601",
      "dependencies": ["required_prerequisites"]
    }
  ],
  "validation_checks": [
    {
      "check": "automated verification test",
      "expected_result": "target state",
      "retry_policy": "exponential backoff"
    }
  ]
}"""

def get_compliance_policy() -> str:
    """Return structured compliance guidelines for AI reasoning"""
    return COMPLIANCE_REASONING_PROMPT
