#!/usr/bin/env python3
"""
Simple evaluation script for ADE DocVQA Benchmark.
Evaluates Claude on DocVQA validation split using the hybrid prompt.
"""

import os
import sys
import json
import asyncio
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from clients.claude_client_final_with_reasoning import ClaudeAsyncClient


def load_prompt():
    """Load the hybrid prompt."""
    prompt_file = Path(__file__).parent / "prompt.md"
    with open(prompt_file) as f:
        return f.read()


def load_parsed_document(image_name: str):
    """Load parsed document JSON for an image."""
    parsed_file = Path(__file__).parent / "parsed" / f"{image_name}.json"

    if not parsed_file.exists():
        return None

    with open(parsed_file) as f:
        return json.load(f)


def create_markdown_context(parsed_data):
    """Create markdown context from parsed ADE data."""
    if not parsed_data:
        return ""

    markdown_parts = []
    for chunk in parsed_data.get("chunks", []):
        markdown_parts.append(chunk.get("markdown", ""))

    return "\n\n".join(markdown_parts)


async def evaluate_question(client, prompt, question_data, sem):
    """Evaluate a single question."""
    async with sem:
        # Load parsed document
        image_name = Path(question_data["image"]).stem
        parsed_data = load_parsed_document(image_name)

        if not parsed_data:
            print(f"  ⚠ No parsed data for {image_name}")
            return {
                "question_id": question_data["question_id"],
                "question": question_data["question"],
                "answer": question_data["answers"],
                "pred": "ERROR: No parsed data",
                "correct": False
            }

        # Create context
        context = create_markdown_context(parsed_data)

        # Create user message
        user_message = f"""Document (with spatial grounding):

```markdown
{context}
```

Question: {question_data['question']}

Choose the appropriate strategy and answer the question.
Output your response as JSON:
{{
  "answer": "final answer",
  "sources": ["id1", "id2"]
}}"""

        try:
            # Generate response
            result = await client.generate_response(
                system_prompt=prompt,
                user_message=user_message,
                max_tokens=4096,
                temperature=0.0,
            )

            pred = result.get("answer", "ERROR")

            # Check correctness (exact match, case-insensitive)
            pred_norm = pred.strip().lower()
            is_correct = any(
                pred_norm == ans.strip().lower()
                for ans in question_data["answers"]
            )

            return {
                "question_id": question_data["question_id"],
                "question": question_data["question"],
                "answer": question_data["answers"],
                "pred": pred,
                "sources": result.get("sources", []),
                "correct": is_correct
            }

        except Exception as e:
            print(f"  ✗ Error on Q{question_data['question_id']}: {e}")
            return {
                "question_id": question_data["question_id"],
                "question": question_data["question"],
                "answer": question_data["answers"],
                "pred": f"ERROR: {str(e)}",
                "correct": False
            }


async def main():
    """Main evaluation function."""
    # Check API key
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set")
        print("Please set it with: export ANTHROPIC_API_KEY='your-key-here'")
        return

    # Load annotations
    val_file = Path(__file__).parent / "data" / "val" / "val_v1.0.json"
    print(f"Loading annotations from {val_file}...")

    with open(val_file) as f:
        val_data = json.load(f)

    questions = val_data["data"]
    print(f"Found {len(questions)} questions")

    # Load prompt
    print("Loading hybrid prompt...")
    prompt = load_prompt()

    # Initialize client
    model = "claude-sonnet-4-20250514"  # Use Sonnet 4.5 (best results)
    client = ClaudeAsyncClient(api_key, model)
    sem = asyncio.Semaphore(10)  # Control concurrency

    print(f"\nEvaluating with {model}...")
    print("This will take ~1-2 hours for full validation set.\n")

    # Evaluate all questions
    tasks = [evaluate_question(client, prompt, q, sem) for q in questions]
    results = await asyncio.gather(*tasks)

    # Calculate accuracy
    correct = sum(1 for r in results if r["correct"])
    accuracy = (correct / len(results)) * 100

    # Save results
    output_file = Path(__file__).parent / "results" / "predictions.jsonl"
    output_file.parent.mkdir(exist_ok=True)

    with open(output_file, "w") as f:
        for result in results:
            f.write(json.dumps(result) + "\n")

    # Print summary
    print("\n" + "="*70)
    print(f"Evaluation Complete!")
    print(f"Total questions: {len(results)}")
    print(f"Correct: {correct} ({accuracy:.2f}%)")
    print(f"Results saved to: {output_file}")
    print("="*70)


if __name__ == "__main__":
    asyncio.run(main())
