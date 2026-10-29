# Termux Resume Analyzer — Zero pip dependencies

A mobile-friendly Python web app to compare resume skills with a job description. Uses only Python's standard library; PDF text extraction is optional and uses Termux Poppler.

## Termux setup
```bash
pkg update
pkg install python poppler unzip
```
No `pip install` command is needed.

1. Download this ZIP to your phone's Download folder.
2. In Termux:
```bash
termux-setup-storage
mkdir -p ~/resume-analyzer
cd ~/resume-analyzer
unzip ~/storage/downloads/ai_resume_analyzer_termux.zip
cd ai_resume_analyzer
python app.py
```
3. Open `http://127.0.0.1:8501` in your phone browser.
4. Keep Termux open. Stop with Ctrl+C.

If the ZIP was saved elsewhere, change the unzip path accordingly.

## Features
- Responsive browser UI
- Paste resume text or upload a text-based PDF
- PDF extraction using `pdftotext`
- Keyword match score, matching skills, skills not detected
- Category summary and downloadable text report
- No external Python packages, API keys, database, or account needed

## Limitations
- Skill detection is keyword-based, not a language model.
- Scanned image-only PDFs may require OCR; paste their text if extraction returns nothing.
- Score is not a hiring probability.
- App binds only to 127.0.0.1 (local phone access).
- Inputs are not saved by the app.

## Resume description (only after testing)
**Resume Analyzer & Job Matcher | Python, HTTPServer, Regular Expressions, Poppler**
- Built a local web application that compares resume skills against job descriptions.
- Implemented keyword matching, missing-skill analysis, category summaries, PDF text extraction, and downloadable reports.
