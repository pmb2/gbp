COMPLIANCE_REASONING_PROMPT = """**Compliance Checklist Reasoning Protocol**

1. **Data Verification**
   - [ ] Confirm business info matches official records
   - [ ] Validate hours against recent activity
   - [ ] Cross-check services with licensing

2. **Content Standards**
   - [ ] Verify brand guideline compliance
   - [ ] Check media rights/licenses
   - [ ] Review user-generated content

3. **Update Priorities**
   ! Urgent (24h): Legal/safety issues
   ! High (72h): Contact info/hours
   ! Medium (1wk): Style/metadata

4. **Action Types**
   → update: Direct data changes
   → alert: Human review needed
   → verify: Additional verification

5. **Output Formatting**
   - Concise reasoning
   - Prioritized actions
   - Specific targets
   - Verification steps"""

def get_compliance_policy() -> str:
    return COMPLIANCE_REASONING_PROMPT
