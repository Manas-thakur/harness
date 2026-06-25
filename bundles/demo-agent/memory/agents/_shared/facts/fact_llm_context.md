---
id: fact_llm_context
type: fact
category: context
version: 1
created: '2026-06-25'
updated: '2026-06-25'
tags:
- llm
- context
- limits
---

# Fact: LLM Context Window Management

## Core Information
- **Context Window**: Maximum tokens that can be processed in a single request
- **Token Estimation**: ~4 characters per token (English text)
- **Safe Limit**: Keep context under 80% of model's maximum to allow for response generation

## Best Practices
1. Prioritize recent conversation history
2. Summarize older conversations when approaching limits
3. Remove redundant or low-value context
4. Keep system prompts concise but complete

## Related Skills
- [[skill_summarization]] - For condensing old conversations
- [[skill_context_management]] - For prioritizing relevant information

## Notes
- Different models have different context limits
- Always account for output token allocation
- Consider streaming responses for long outputs
