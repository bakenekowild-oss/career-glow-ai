#!/usr/bin/env python3
"""Termux-friendly Resume Analyzer using only Python's standard library."""
import html
import re
import subprocess
import tempfile
import os
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs
from email.parser import BytesParser
from email.policy import default

HOST = "127.0.0.1"
PORT = 8501
MAX_BODY = 8 * 1024 * 1024  # 8 MiB upload limit

SKILL_GROUPS = {
    "Programming": ["python", "java", "c++", "c#", "javascript", "typescript", "php", "go", "rust"],
    "Web Development": ["html", "css", "react", "angular", "vue", "node.js", "express", "django", "flask", "fastapi"],
    "Data & AI": ["sql", "pandas", "numpy", "matplotlib", "machine learning", "deep learning",
                  "tensorflow", "pytorch", "scikit-learn", "power bi", "tableau", "excel", "data analysis"],
    "Cloud & DevOps": ["aws", "azure", "google cloud", "docker", "kubernetes", "git", "github",
                       "linux", "jenkins", "ci/cd"],
    "Cybersecurity": ["network security", "penetration testing", "nmap", "wireshark", "kali linux",
                      "owasp", "cryptography", "incident response"],
    "Databases": ["mysql", "postgresql", "mongodb", "sqlite", "oracle", "redis"],
    "Core CS": ["data structures", "algorithms", "object-oriented programming", "oop",
                "operating systems", "computer networks", "dbms", "software testing"]
}
ALL_SKILLS = sorted({s for group in SKILL_GROUPS.values() for s in group}, key=len, reverse=True)


def normalize(text):
    text = text.lower().replace("nodejs", "node.js").replace("powerbi", "power bi")
    text = re.sub(r"[\u2010-\u2015]", "-", text)
    return re.sub(r"\s+", " ", text)


def find_skills(text):
    content = normalize(text)
    found = set()
    for skill in ALL_SKILLS:
        pattern = rf"(?<![a-z0-9+#]){re.escape(skill)}(?![a-z0-9+#])"
        if re.search(pattern, content):
            found.add(skill)
    return found


def extract_pdf_text(pdf_bytes):
    """Extract text with Termux Poppler's pdftotext command."""
    path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(pdf_bytes)
            path = f.name
        result = subprocess.run(
            ["pdftotext", "-layout", path, "-"],
            capture_output=True, text=True, timeout=30, check=False
        )
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or "pdftotext could not read the PDF")
        return result.stdout.strip()
    except FileNotFoundError:
        raise RuntimeError("PDF tool missing. In Termux run: pkg install poppler")
    finally:
        if path:
            try:
                os.unlink(path)
            except OSError:
                pass


def esc(value):
    return html.escape(value, quote=True)


def page(body, title="Resume Analyzer"):
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<style>
:root{{color-scheme:dark}}*{{box-sizing:border-box}}
body{{margin:0;background:#10131b;color:#edf0f7;font:16px/1.5 system-ui,Arial,sans-serif}}
main{{max-width:980px;margin:auto;padding:22px}}
.hero,.panel{{background:#191e2a;border:1px solid #30394c;border-radius:16px;padding:20px;margin-bottom:16px}}
h1{{margin:0 0 6px;font-size:clamp(25px,5vw,36px)}}h2{{font-size:20px;margin-top:0}}
.muted{{color:#aeb8cb}}label{{display:block;font-weight:650;margin:12px 0 6px}}
textarea,input[type=file]{{width:100%;background:#0f1420;color:#f3f5fb;border:1px solid #46516a;border-radius:10px;padding:12px}}
textarea{{min-height:190px;resize:vertical}}
button,.download{{display:inline-block;background:#7c9cff;color:#0b1020;border:0;border-radius:10px;padding:12px 16px;font-weight:750;text-decoration:none;margin-top:12px;cursor:pointer}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}}
.metric{{background:#111725;padding:15px;border-radius:12px;border:1px solid #333d51}}
.big{{font-size:30px;font-weight:800}}
.pill{{display:inline-block;background:#28334a;border-radius:20px;padding:5px 9px;margin:3px;font-size:14px}}
.warn{{background:#3a2c16;border:1px solid #795b26;padding:12px;border-radius:10px}}
.good{{background:#15372d;border:1px solid #28664f;padding:12px;border-radius:10px}}
table{{width:100%;border-collapse:collapse}}td,th{{text-align:left;padding:9px;border-bottom:1px solid #394258}}
@media(max-width:600px){{main{{padding:12px}}.hero,.panel{{padding:15px}}}}
</style></head><body><main>{body}
<p class="muted">Educational keyword comparison only; not a hiring prediction. Only claim skills you genuinely have.</p>
</main></body></html>"""


def render_form(resume="", job="", message=""):
    msg = f'<div class="warn">{esc(message)}</div>' if message else ""
    body = f"""
<section class="hero"><h1>📄 Resume Analyzer</h1>
<p class="muted">Compare resume skills with a job description. Built with Python's standard library; no pip packages or API keys required.</p></section>
{msg}
<form class="panel" method="post" action="/analyze" enctype="multipart/form-data">
<h2>1. Resume</h2>
<label for="pdf">Optional: upload a text-based PDF</label>
<input id="pdf" type="file" name="resume_pdf" accept=".pdf,application/pdf">
<p class="muted">PDF extraction uses Poppler. Or paste resume text below, which works without extra packages.</p>
<label for="resume">Resume text</label>
<textarea id="resume" name="resume_text" placeholder="Paste your resume text here...">{esc(resume)}</textarea>
<h2 style="margin-top:22px">2. Job description</h2>
<label for="job">Required skills and responsibilities</label>
<textarea id="job" name="job_text" placeholder="Paste the job description here..." required>{esc(job)}</textarea>
<button type="submit">Analyze resume</button>
</form>
<section class="panel"><h2>How scoring works</h2>
<p>Match score = detected job skills also found in your resume ÷ all supported skills detected in the job description × 100.</p>
<p class="muted">The score is keyword overlap, not the probability of getting hired. The app does not save your inputs.</p></section>
"""
    return page(body)


def render_results(resume_text, job_text):
    resume_skills = find_skills(resume_text)
    job_skills = find_skills(job_text)
    matched = sorted(resume_skills & job_skills)
    missing = sorted(job_skills - resume_skills)
    extra = sorted(resume_skills - job_skills)
    score = round(100 * len(matched) / len(job_skills), 1) if job_skills else 0.0

    def pills(items, empty):
        return "".join(f'<span class="pill">{esc(s)}</span>' for s in items) if items else f'<p class="muted">{empty}</p>'

    rows = []
    for category, skills in SKILL_GROUPS.items():
        required = set(skills) & job_skills
        if required:
            got = required & resume_skills
            rows.append(f"<tr><td>{esc(category)}</td><td>{len(required)}</td><td>{len(got)}</td><td>{len(required-got)}</td></tr>")

    suggestions = []
    if missing:
        suggestions.append("Practise missing skills that are relevant to the role and build a project to demonstrate them.")
    if not re.search(r"\bprojects?\b", normalize(resume_text)):
        suggestions.append("If applicable, add a Projects section describing your contribution, technologies, and outcome.")
    if not re.search(r"\b(github|portfolio|linkedin)\b", normalize(resume_text)):
        suggestions.append("Consider adding a relevant GitHub, portfolio, or LinkedIn link.")
    suggestions.append("Review spelling, dates, and formatting manually; only list skills you can demonstrate.")
    suggestion_html = "".join(f"<li>{esc(s)}</li>" for s in suggestions)
    table = ("<table><tr><th>Category</th><th>In job</th><th>Matched</th><th>Not detected</th></tr>" +
             "".join(rows) + "</table>") if rows else "<p>No supported skills found in the job description.</p>"
    status = ('<div class="good">Strong keyword overlap. Review the role requirements manually too.</div>' if score >= 75
              else '<div class="warn">Moderate or low keyword overlap. Review missing skills and the actual job requirements.</div>')

    report_lines = [
        "RESUME ANALYSIS REPORT", f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"Keyword match score: {score}%", "", "MATCHING SKILLS:", *(matched or ["None detected"]),
        "", "SKILLS NOT DETECTED IN RESUME:", *(missing or ["None detected"]),
        "", "OTHER DETECTED RESUME SKILLS:", *(extra or ["None detected"]),
        "", "This is keyword matching, not a hiring prediction."
    ]
    report = esc("\n".join(report_lines))
    body = f"""
<section class="hero"><h1>Analysis results</h1><p class="muted">Your input is analyzed in memory and is not stored by this app.</p></section>
<section class="panel"><div class="grid">
<div class="metric"><div class="muted">Keyword match score</div><div class="big">{score}%</div></div>
<div class="metric"><div class="muted">Skills found in job description</div><div class="big">{len(job_skills)}</div></div>
<div class="metric"><div class="muted">Matching skills</div><div class="big">{len(matched)}</div></div>
</div><p>{status}</p></section>
<section class="panel"><h2>✅ Matching skills</h2>{pills(matched, "No matching skills detected.")}</section>
<section class="panel"><h2>📌 Skills not detected in resume</h2>{pills(missing, "No supported missing skills detected.")}<p class="muted">These are suggestions to learn or verify, not skills to claim automatically.</p></section>
<section class="panel"><h2>Other detected resume skills</h2>{pills(extra, "None detected.")}</section>
<section class="panel"><h2>Skills by category</h2>{table}</section>
<section class="panel"><h2>Improvement suggestions</h2><ul>{suggestion_html}</ul></section>
<section class="panel"><h2>Download report</h2><form method="post" action="/report">
<input type="hidden" name="report" value="{esc(chr(10).join(report_lines))}">
<button type="submit">Download text report</button></form>
<p><a class="download" href="/">Analyze another resume</a></p></section>
"""
    return page(body, "Analysis Results")


class Handler(BaseHTTPRequestHandler):
    def send_html(self, content, status=200):
        raw = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def read_body(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length < 0 or length > MAX_BODY:
            raise ValueError("Request is too large. Please use a smaller resume (under 8 MB).")
        return self.rfile.read(length)

    def do_GET(self):
        self.send_html(render_form())

    def do_POST(self):
        try:
            body = self.read_body()
            content_type = self.headers.get("Content-Type", "")
            if self.path == "/report":
                data = parse_qs(body.decode("utf-8", errors="replace"))
                report = data.get("report", [""])[0].encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Disposition", 'attachment; filename="resume_analysis_report.txt"')
                self.send_header("Content-Length", str(len(report)))
                self.end_headers()
                self.wfile.write(report)
                return

            resume_text = ""
            job_text = ""
            pdf_bytes = None
            if "multipart/form-data" in content_type:
                message = BytesParser(policy=default).parsebytes(
                    b"Content-Type: " + content_type.encode() + b"\r\nMIME-Version: 1.0\r\n\r\n" + body
                )
                for part in message.iter_parts():
                    name = part.get_param("name", header="content-disposition")
                    payload = part.get_payload(decode=True) or b""
                    filename = part.get_filename()
                    if name == "resume_text":
                        resume_text = payload.decode("utf-8", errors="replace").strip()
                    elif name == "job_text":
                        job_text = payload.decode("utf-8", errors="replace").strip()
                    elif name == "resume_pdf" and filename and payload:
                        pdf_bytes = payload
            else:
                data = parse_qs(body.decode("utf-8", errors="replace"))
                resume_text = data.get("resume_text", [""])[0].strip()
                job_text = data.get("job_text", [""])[0].strip()

            if pdf_bytes:
                try:
                    extracted = extract_pdf_text(pdf_bytes)
                    if extracted:
                        resume_text = extracted
                    elif not resume_text:
                        self.send_html(render_form(resume_text, job_text, "No text found in PDF. It may be scanned; paste the resume text instead."), 400)
                        return
                except RuntimeError as exc:
                    if not resume_text:
                        self.send_html(render_form(resume_text, job_text, str(exc)), 400)
                        return

            if not resume_text:
                self.send_html(render_form(resume_text, job_text, "Please paste resume text or upload a readable PDF."), 400)
                return
            if not job_text:
                self.send_html(render_form(resume_text, job_text, "Please paste a job description."), 400)
                return
            self.send_html(render_results(resume_text, job_text))
        except ValueError as exc:
            self.send_html(render_form(message=str(exc)), 413)
        except Exception as exc:
            self.send_html(render_form(message=f"Unexpected error: {exc}"), 500)

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args))


if __name__ == "__main__":
    server = HTTPServer((HOST, PORT), Handler)
    print(f"Resume Analyzer running at http://{HOST}:{PORT}")
    print("Keep Termux open. Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server...")
    finally:
        server.server_close()
