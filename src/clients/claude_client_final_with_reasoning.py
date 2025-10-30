import os
import json
import asyncio
import logging
from typing import Any, Sequence
from anthropic import AsyncAnthropic
from pydantic import BaseModel
from pathlib import Path

_LOGGER = logging.getLogger(__name__)


class DocQAResponse(BaseModel):
    answer: str
    sources: list[str]
    reasoning: str = ""


class ClaudeAsyncClient:
    def __init__(self, api_key: str, model_name: str = "claude-sonnet-4-5-20250929"):
        self.api_key = api_key
        self.model_name = model_name
        self.client = AsyncAnthropic(api_key=api_key)
        _LOGGER.info(f"Using Claude with model {self.model_name}")

    async def generate_response(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> dict:
        """Generate a response from Claude."""
        try:
            response = await self.client.messages.create(
                model=self.model_name,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": user_message,
                    }
                ],
            )

            # Extract text from response
            response_text = response.content[0].text

            # Parse JSON response
            try:
                result = json.loads(response_text)
            except json.JSONDecodeError:
                # Try to extract JSON from markdown code blocks
                if "```json" in response_text:
                    json_str = response_text.split("```json")[1].split("```")[0].strip()
                    result = json.loads(json_str)
                elif "```" in response_text:
                    json_str = response_text.split("```")[1].split("```")[0].strip()
                    result = json.loads(json_str)
                else:
                    # If no JSON found, return error
                    result = {"answer": response_text, "sources": [], "reasoning": ""}

            return result

        except Exception as e:
            _LOGGER.exception(f"Error generating response: {e}")
            return {"answer": "ERROR", "sources": [], "reasoning": "", "error": str(e)}


async def main_batched(
    batched_input: list[dict],
    api_key: str,
    model_name: str = "claude-sonnet-4-5-20250929",
    concurrency: int = 10,
):
    """Process batched requests with Claude using FINAL prompt and capture reasoning."""
    client = ClaudeAsyncClient(api_key, model_name)
    sem = asyncio.Semaphore(concurrency)

    # Load FINAL prompt
    prompt_path = Path(__file__).parent.parent / "prompts" / "claude_docvqa_final.md"
    with open(prompt_path, 'r') as f:
        system_prompt = f.read()

    async def _generate_one(item: dict) -> dict:
        """Generate response for a single item."""
        context = item.get("context", "")
        question = item.get("question", "")

        # Create user message with executive summary request
        user_message = f"""Document (doc_as_markdown):

```markdown
{context}
```

Question: {question}

Apply the 4-phase approach (Question Comprehension → Markdown Analysis → Visual Structure → Spatial Verification) to answer this question.

Output your response as JSON with a proper executive summary:
{{
  "reasoning": "Executive Summary: Provide a clear, professional summary that explains: (1) What the question is asking for and any key modifiers (first/last/top/bottom/etc), (2) Where and how you located the answer in the document (specific location, chunk type, visual position), (3) How you verified correctness using spatial/structural information, and (4) Any important context or considerations. Be thorough but concise.",
  "answer": "final answer",
  "sources": ["id1", "id2"]
}}

The reasoning should be a proper executive summary - clear, informative, and professional."""

        async with sem:
            try:
                result = await client.generate_response(
                    system_prompt=system_prompt,
                    user_message=user_message,
                    max_tokens=4096,
                    temperature=0.0,
                )

                # Extract fields
                answer = result.get("answer", "ERROR")
                sources = result.get("sources", [])
                reasoning = result.get("reasoning", "")

                return {
                    "image_id": item.get("image_id"),
                    "question_id": item.get("question_id"),
                    "question": question,
                    "answer": item.get("answer"),
                    "gemini_pred": item.get("gemini_pred", "N/A"),
                    "pred": answer,
                    "sources": sources,
                    "reasoning": reasoning,
                }

            except Exception as e:
                _LOGGER.exception(f"Error processing item: {e}")
                return {
                    "image_id": item.get("image_id"),
                    "question_id": item.get("question_id"),
                    "question": question,
                    "answer": item.get("answer"),
                    "pred_error": str(e),
                }

    # Process all items
    tasks = [_generate_one(item) for item in batched_input]
    results = await asyncio.gather(*tasks)

    return results
