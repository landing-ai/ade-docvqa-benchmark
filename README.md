# ADE DocVQA Benchmark - Error Analysis

This repository contains an interactive error analysis gallery for the DocVQA benchmark evaluated using ADE (Advanced Document Extraction) with DPT-2 and optimized prompting.

**View the live gallery:** https://landing-ai.github.io/ade-docvqa-benchmark/

## Repository Structure

```
├── wrong_predictions_gallery.html    # Main gallery page
├── index.html                        # Auto-redirects to gallery
├── images/
│   ├── bbox_overlays/               # 56 images with bounding box overlays
│   ├── documents/                   # 56 original document images
│   └── *.svg                        # Logo assets
├── .github/workflows/deploy.yml     # GitHub Actions deployment
└── .nojekyll                        # Bypass Jekyll processing
```

## Benchmark Results

- **Accuracy:** 98.90% (5,287/5,346 questions correct)
- **Errors analyzed:** 59 remaining incorrect predictions

## Gallery Overview

The `incorrect_answers_gallery.html` file provides an interactive visualization of all 59 errors. Each error card displays:

- **Document image** with OCR text extracted by ADE
- **Bounding box overlay** showing ADE's spatial grounding with color-coded text chunks
- **Question** asked about the document
- **Ground truth answer** from the dataset
- **Model prediction** from ADE DPT-2
- **Error category** classification (Parser Issues vs VLM Limitations)
- **Specific error type** (e.g., Ambiguous Reference, Spatial Error, OCR Error, Missing Info)

### Interactive Features

- **3-column grid layout** for browsing all errors
- **Click-to-zoom** on any image to see details
- **Toggle view** between original document and bounding box overlay in zoom mode
- **Category filters** to view Parser Issues (22) or VLM Limitations (37) separately
- **Specific error filters** to drill down by error type

## Error Categories

### Parser Issues (22 errors)
Errors related to document processing, OCR quality, or text extraction that could potentially be improved with better preprocessing or parsing strategies.

### VLM Limitations (37 errors)
Errors stemming from the vision-language model's reasoning capabilities, including:
- **Ambiguous Reference:** Unclear which text span the question refers to
- **Spatial Reasoning:** Difficulty with spatial relationships or locations in the document
- **Missing Information:** Required information not present or not extracted from the document
- **OCR Error:** Text misread or missing from OCR output
- **Complex Reasoning:** Multi-step reasoning failures

## Image Assets

The `images/` directory contains:
- **56 bounding box overlays** (`images/bbox_overlays/`) showing ADE's document understanding
- **56 original document images** (`images/documents/`) for comparison

## Notes

- The gallery uses Tailwind CSS from CDN (no build step required)
- All JavaScript is inline in the HTML file
- Images are served directly from GitHub Pages
- No server-side processing needed
- Gallery works offline if you download the HTML + images folder

---

**View the live gallery:** https://landing-ai.github.io/ade-docvqa-benchmark/
