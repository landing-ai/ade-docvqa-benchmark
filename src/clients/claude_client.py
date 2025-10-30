import os
import json
import asyncio
import logging
from typing import Any, Sequence
from anthropic import AsyncAnthropic
from pydantic import BaseModel

_LOGGER = logging.getLogger(__name__)


class DocQAResponse(BaseModel):
    answer: str
    sources: list[str]


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
                    result = {"answer": response_text, "sources": []}

            return result

        except Exception as e:
            _LOGGER.exception(f"Error generating response: {e}")
            return {"answer": "ERROR", "sources": [], "error": str(e)}


async def main_batched(
    batched_input: list[dict],
    api_key: str,
    model_name: str = "claude-sonnet-4-5-20250929",
    concurrency: int = 10,
):
    """Process batched requests with Claude."""
    client = ClaudeAsyncClient(api_key, model_name)
    sem = asyncio.Semaphore(concurrency)

    async def _generate_one(item: dict) -> dict:
        """Generate response for a single item."""
        context = item.get("context", "")
        question = item.get("question", "")

        # Load structured analysis prompt
        prompt_path = os.path.join(os.path.dirname(__file__), '..', 'prompts', 'claude_docvqa_structured_analysis.md')
        with open(prompt_path, 'r') as f:
            prompt_template = f.read()

        # Create system prompt
        system_prompt = f"""{prompt_template}

### Understanding the Document Structure

The document is provided with **explicit spatial metadata** for each chunk. Each chunk has a header that contains:

**Chunk Format**:
```
[chunk_type | Page N | Position: VERTICAL-HORIZONTAL | BBox: (left, top, right, bottom)]
Markdown content here...
```

**Example**:
```
[text | Page 0 | Position: TOP-LEFT | BBox: (0.094, 0.084, 0.320, 0.120)]
<a id='uuid'></a>

SCHEDULES TO THE ACCOUNTS

[table | Page 0 | Position: MIDDLE-CENTER | BBox: (0.150, 0.250, 0.850, 0.550)]
<a id='uuid2'></a>

<table id="table-1">
<tr><td id="1-1">Cell A1</td><td id="1-2">Cell B1</td></tr>
<tr><td id="2-1">Cell A2</td><td id="2-2">Cell B2</td></tr>
</table>
```

**What This Tells You**:

1. **Chunk Type**: `text`, `table`, `figure`, `marginalia`, `attestation`
2. **Page Number**: Which page (0-indexed) the content appears on
3. **Position Descriptor**: Coarse position on page
   - Vertical: TOP (< 0.33), MIDDLE (0.33-0.67), BOTTOM (> 0.67)
   - Horizontal: LEFT (< 0.33), CENTER (0.33-0.67), RIGHT (> 0.67)
4. **Bounding Box**: Exact normalized coordinates (0.0 to 1.0)
   - Format: (left, top, right, bottom)
   - Smaller top values = higher on page
   - Smaller left values = more to the left

**Reading Order**: Chunks are ordered by their visual position (top-to-bottom, left-to-right), so:
- Content appearing **first** in the document is visually **at the top**
- Content appearing **last** in the document is visually **at the bottom**
- For same vertical position, left chunks come before right chunks

### Your Task

Answer questions using ONLY the information from "doc_as_markdown" below:

```markdown
{context}
```

### Answer Guidelines

**Output Format** (strict JSON):
```json
{{
  "answer": "exact, concise answer",
  "sources": ["chunk-id-1", "chunk-id-2"]
}}
```

**Rules for Answers**:

1. **Spatial Questions** - Use the explicit spatial metadata:
   - "first", "top", "above" → Look for chunks with small `top` values in BBox or TOP in Position
   - "last", "bottom", "below" → Look for chunks with large `top` values in BBox or BOTTOM in Position
   - "left" vs "right" → Compare `left` values in BBox or check LEFT vs RIGHT in Position
   - "in a box/rectangle" → Look for chunks with type `figure` or those enclosed by other content
   - "extreme" positions → Find min/max of bounding box coordinates
   - Reading order: Earlier chunks = higher/more-left on page

2. **Table Questions** - Use fine-grained IDs:
   - Reference specific cells: `<td id="1-2">` means row 1, column 2
   - Table headers are usually row 0 or first rows
   - Use cell IDs in your sources for precision
   - For "which column", use the column number from cell IDs

3. **Extraction Questions** - Copy exactly:
   - Numbers: Extract as-written, don't interpret or convert
   - Dates: Copy the exact format shown
   - Names: Use exact capitalization and spelling
   - Text: No paraphrasing, use document's exact wording

4. **Conciseness** - Minimal words:
   - Answer the question directly, no explanations
   - Don't repeat the question in your answer
   - Don't add "The document states..." or similar phrases

5. **Formatting**:
   - No newline characters (`\\n`) in answers
   - No triple backticks around the JSON output
   - No markdown formatting in the answer text

### Examples

**Good Answers** (showing proper structure usage):

```
Q: "What is in the first table?"
A: {{"answer": "Budget breakdown", "sources": ["table-1"]}}
→ First table = earliest table ID in markdown

Q: "What number is in row 2, column 3?"
A: {{"answer": "42", "sources": ["2-3"]}}
→ Use cell ID directly

Q: "What appears at the top of the page?"
A: {{"answer": "Company Logo", "sources": ["chunk-1"]}}
→ Top = earliest chunk in markdown

Q: "What is the value for April?"
A: {{"answer": "$1,234.56", "sources": ["3-4"]}}
→ Extract exactly as shown

Q: "What is between the header and footer?"
A: {{"answer": "Main content section", "sources": ["chunk-5"]}}
→ Content between two known positions
```

**Bad Answers** (don't do this):

```
Q: "What is the total?"
A: {{"answer": "The document shows that the total amount is $500", "sources": ["chunk-1"]}}
❌ Too verbose, includes unnecessary words

Q: "What's in the first cell?"
A: {{"answer": "five hundred dollars ($500)", "sources": ["1-1"]}}
❌ Don't interpret or convert, use exact text

Q: "Who signed the document?"
A: {{"answer": "I cannot determine who signed the document from the provided information.", "sources": []}}
❌ Don't give up easily, check attestation chunks
```

### When Answer Is Not Found

Only respond with this if genuinely not in the document:
```json
{{ "answer": "N/A.", "sources": [] }}
```

Before saying N/A, verify you've:
- Checked table cells (use `<td id="...">`)
- Understood spatial terms (first/last/top/bottom)
- Looked in all chunk types (especially `marginalia`, `attestation`)
- Considered the reading order = visual order

---

## Key Principles

1. **Markdown order = Visual order**: Use position in markdown to understand spatial layout
2. **Fine-grained IDs**: Reference table cells, not just table chunks
3. **Exact extraction**: Copy values precisely as they appear
4. **Concise answers**: Minimal words, no explanations
5. **Trust the structure**: The JSON has spatial information baked in through ordering"""

        try:
            async with sem:
                result = await client.generate_response(
                    system_prompt=system_prompt,
                    user_message=question,
                    temperature=0.0,
                )

            item["pred"] = result.get("answer", "")
            item["sources"] = result.get("sources", [])
            if "error" in result:
                item["pred_error"] = result["error"]

        except Exception as e:
            _LOGGER.exception(f"Failed to generate/assign pred: {e}")
            item["pred"] = ""
            item["sources"] = []
            item["pred_error"] = str(e)

        return item

    # Process all items with bounded concurrency
    tasks = [asyncio.create_task(_generate_one(item)) for item in batched_input]
    await asyncio.gather(*tasks)

    return batched_input


async def main_single(
    context: str,
    question: str,
    api_key: str,
    model_name: str = "claude-sonnet-4-5-20250929",
) -> dict:
    """Process a single request with Claude."""
    client = ClaudeAsyncClient(api_key, model_name)

    system_prompt = f"""You are a helpful assistant that answers questions based on a provided document context. To prepare for your task, first examine the following Markdown representation of a document, referred to as "doc_as_markdown".

Begin by reviewing the document presented in the Markdown format below. Pay attention to the structure, as each significant piece of content (like headings, paragraphs, tables and figures etc.) always starts with an anchor HTML tag with an ID, like this <a id="chunk-1"></a>.
Also, when the documents have tables, the tables will be represented in HTML format. And inside the table, each cell will have a unique ID as well, like this <td id="1-1">.
These IDs are crucial for referencing specific parts of the document in your answers. *You should always use the most fine grained IDs possible*.

"doc_as_markdown" looks like this:

```markdown
{context}
```

Answer the question directly using only the information from "doc_as_markdown", with the relevant chunk IDs that are used to get the answer.
It's important to reference the specific sections or chunks of the document that contain the relevant information. Do this by including the unique IDs (found in the HTML elements) in your response.

The answer format should be a JSON object with the following structure:
```json
{{
  "answer": "the answer",
  "sources": ["id_1", "id_2"]  // Put the relevant ids here
}}
```

If the answer is not definitively contained in the document, respond with the following JSON:
```json
{{ "answer": "I cannot find the answer in the provided document.", "sources": [] }}
```

Do not answer with any additional text besides the required output format. Do not add newline characters like '\\n' in the answer. Do not wrap your JSON in a code fence (triple backticks like '```')."""

    result = await client.generate_response(
        system_prompt=system_prompt,
        user_message=question,
        temperature=0.0,
    )

    return result


if __name__ == "__main__":
    import asyncio

    logging.basicConfig(level=logging.INFO)

    # Test with a simple example
    api_key = os.getenv("ANTHROPIC_API_KEY")
    context = "<a id='chunk-1'></a>\n\nThe capital of France is Paris."
    question = "What is the capital of France?"

    result = asyncio.run(main_single(context, question, api_key))
    print(f"Result: {result}")
