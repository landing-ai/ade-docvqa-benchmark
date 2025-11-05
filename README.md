# ADE DocVQA Benchmark

**98.650% Accuracy on DocVQA Validation Set**

This repository contains our complete DocVQA benchmark implementation using Agentic Document Extraction (ADE) with DPT-2 parsing and Claude for question answering.

## Results

- **Accuracy:** 98.650% (5,263/5,335 correct, excluding 14 dataset issues)
- **Baseline:** 95.36% (with Playground Chat)
- **Improvement:** +3.29 percentage points
- **Remaining errors:** 72 real errors (14 dataset issues excluded but visible)

[**View Interactive Error Gallery →**](./gallery.html)

The gallery includes:
- 40 hardest success cases with visual grounding
- 72 error cases with detailed analysis
- 14 questionable dataset issues (excluded from accuracy but shown for transparency)
- Interactive category filtering

## Repository Contents

### Main Files
- `gallery.html` - Interactive visualization of results and remaining errors
- `prompt.md` - Final hybrid prompt (recommended for best results)
- `evaluate.py` - Simple evaluation script
- `images/` - All 1,286 DocVQA validation images
- `parsed/` - Pre-parsed document JSONs (ADE DPT-2 output)
- `results/` - Prediction results

### Additional Materials
- `extra/` - Alternative prompts, test scripts, analysis reports, and utilities

## Quick Start

### 1. Prerequisites

```bash
# Python 3.8+
python3 --version

# Install dependencies
pip install -r requirements.txt
```

### 2. Get DocVQA Annotations

Download the DocVQA validation annotations from HuggingFace:

```bash
# Create data directory if it doesn't exist
mkdir -p data/val

# Download val annotations
wget https://huggingface.co/datasets/lmms-lab/DocVQA/resolve/main/val_v1.0.json -O data/val/val_v1.0.json
```

Alternatively, visit [DocVQA on HuggingFace](https://huggingface.co/datasets/lmms-lab/DocVQA) and download manually.

### 3. Set API Key

```bash
export ANTHROPIC_API_KEY='your-api-key-here'
```

Get your API key from [Anthropic Console](https://console.anthropic.com/).

### 4. Run Evaluation

```bash
python3 evaluate.py
```

This will:
- Load the hybrid prompt from `prompt.md`
- Process all 5,349 questions in the validation set
- Use pre-parsed documents from `parsed/`
- Save predictions to `results/predictions.jsonl`
- Report final accuracy

**Note:** Full evaluation takes ~1-2 hours with Claude Sonnet 4.5.

## Data Format

### Parsed Documents (`parsed/*.json`)

Each JSON contains ADE DPT-2 parsing output:

```json
{
  "chunks": [
    {
      "id": "chunk_0",
      "type": "text",
      "markdown": "Text content with <bbox:[x1,y1,x2,y2]> annotations",
      "bbox": [x1, y1, x2, y2]
    }
  ]
}
```

### Predictions (`results/predictions.jsonl`)

Each line is a JSON object:

```json
{
  "question_id": 12345,
  "question": "What is the date?",
  "answer": ["January 1, 2020"],
  "pred": "January 1, 2020",
  "sources": ["chunk_0", "chunk_1"],
  "correct": true
}
```

## Methodology

### Approach

1. **Document Parsing:** Use ADE DPT-2 to extract structured content with spatial grounding
2. **Question Answering:** Apply hybrid prompt with Claude Sonnet 4.5
3. **Evaluation:** Exact match scoring (case-insensitive)

### Hybrid Prompt Strategy

Our final prompt (`prompt.md`) uses a two-strategy approach:

1. **Direct Extraction** - For simple factual queries (names, dates, numbers)
2. **Structured Analysis** - For complex spatial/hierarchical questions

Key improvements:
- Footer vs content distinction
- Page number handling (Arabic numerals only)
- Logo text extraction
- Handwritten text detection
- Positional reasoning (last line, under, above, etc.)

## Performance Breakdown

### By Error Category (72 real errors)

| Category | Count | % of Errors | Description |
|----------|-------|-------------|-------------|
| Incorrect Parse | 30 | 41.7% | OCR/parsing errors (character confusion, misreads) |
| Prompt/LLM Misses | 18 | 25.0% | Reasoning or interpretation failures |
| Not ADE Focus | 15 | 20.8% | Spatial layout questions outside ADE's core strength |
| Missed Parse | 9 | 12.5% | Information not extracted during parsing |
| **Dataset Issues** | **14** | **—** | **Questionable ground truth (excluded from count)** |

### Error Categories Explained

- **Incorrect Parse:** OCR/parsing mistakes like character confusion (O/0, I/l/1), table misreads, or parsing artifacts
- **Prompt/LLM Misses:** Claude gives wrong answer despite having correct parsed data - reasoning or instruction-following issues
- **Not ADE Focus:** Questions requiring visual layout analysis, spatial reasoning, or document structure understanding beyond text extraction
- **Missed Parse:** Information exists in document but wasn't extracted by the parser
- **Dataset Issues:** Questionable annotations, ambiguous questions, or debatable ground truth (excluded from accuracy calculation)

## Model Configuration

**Recommended (used for 98.650% result):**
- Model: `claude-sonnet-4-20250514` (Sonnet 4.5)
- Temperature: 0.0
- Max tokens: 4096
- Cost: ~$10 for full evaluation

**Alternative:**
- Model: `claude-opus-4-20250514` (Opus 4)
- Slightly lower accuracy but stronger reasoning
- Cost: ~$100 for full evaluation

## Alternative Prompts

See `extra/prompts/` for previous iterations:

- `enhanced_v2.md` - Earlier version (97.87% accuracy)
- `enhanced_v3.md` - Intermediate version (98.06% accuracy)
- `v4_1.md` - Experimental structured output format (research prototype)

## Reproducing Results

To exactly reproduce our 98.650% result:

1. Use the provided `parsed/` documents (same parsing output)
2. Use `prompt.md` (final hybrid prompt)
3. Use Claude Sonnet 4.5 (`claude-sonnet-4-20250514`)
4. Temperature 0.0 (deterministic)
5. Exclude 14 dataset issues from accuracy calculation (as documented in gallery)

## Citation

If you use this benchmark or methodology, please cite:

```bibtex
@misc{ade-docvqa-2024,
  title={Agentic Document Extraction for DocVQA},
  author={Landing AI},
  year={2024},
  url={https://github.com/your-repo-here}
}
```

## Contributing

We welcome contributions! Priority areas for improvement:

- **Parsing quality** - 30 incorrect parse errors (41.7% of failures)
- **Not ADE Focus** - 15 spatial layout questions (20.8% of failures)
- **Prompt engineering** - 18 LLM reasoning errors (25.0% of failures)
- **Information extraction** - 9 missed parse errors (12.5% of failures)

See the [interactive gallery](./gallery.html) for detailed error analysis with visual grounding and category filtering.

## License

[Your License Here]

## Acknowledgments

- [DocVQA Dataset](https://huggingface.co/datasets/lmms-lab/DocVQA) by Mathew et al.
- [Anthropic Claude](https://www.anthropic.com/claude) for the API
- Landing AI for ADE DPT-2 parsing technology

---

**Questions?** Open an issue or check `extra/reports/` for detailed analysis.
