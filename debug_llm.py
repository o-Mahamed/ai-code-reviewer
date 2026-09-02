from llm_reviewer import SYSTEM_PROMPT, ReviewResult, LLMReviewer

reviewer = LLMReviewer()
source = open("../tests/fixtures/logic_bug.py").read()
user_content = f"Review this Python file:\n\n```python\n{source}\n```"

completion = reviewer.client.chat.completions.parse(
    model="gpt-5.6-terra",
    messages=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ],
    response_format=ReviewResult,
)
msg = completion.choices[0].message
print("finish_reason:", completion.choices[0].finish_reason)
print("refusal:", msg.refusal)
print("parsed:", msg.parsed)
print("raw content:", msg.content)
