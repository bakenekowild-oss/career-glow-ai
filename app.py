#!/usr/bin/env python3
import os, re, json, html, shutil, subprocess, tempfile, zipfile
import urllib.request, urllib.error
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import quote
from email.parser import BytesParser
from email.policy import default
from xml.etree import ElementTree as ET

HOST, PORT = "127.0.0.1", 8501
API_URL = "https://ollama.com/api/chat"
MODEL = os.environ.get("OLLAMA_MODEL", "gemma4:31b")
MAX_FILE = 8 * 1024 * 1024

STYLE = r"""
*{box-sizing:border-box}
:root{color-scheme:dark;--bg:#090b16;--panel:#13172a;--line:#292f4c;--muted:#a3abc6;--white:#f5f6ff;--purple:#a78bfa;--cyan:#67e8f9}
body{margin:0;background:radial-gradient(ellipse at 15% 0%,#282050 0,transparent 40%),radial-gradient(ellipse at 100% 40%,#102f49 0,transparent 38%),var(--bg);color:var(--white);font:15px system-ui,sans-serif;min-height:100vh}
main{max-width:1050px;margin:auto;padding:24px 16px 60px}
nav{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:30px}
.logo{font-weight:850;letter-spacing:-.5px;font-size:19px}.logo b{color:var(--cyan)}
.pill{border:1px solid #3b4260;border-radius:999px;padding:7px 12px;color:#c7d2fe;font-size:12px}
.hero{position:relative;overflow:hidden;padding:30px 24px;border:1px solid #38365d;border-radius:25px;background:linear-gradient(120deg,#211a42d9,#102a3ad9);box-shadow:0 20px 70px #0005;animation:rise .65s ease both}
.hero:after{content:"✦";position:absolute;right:28px;top:10px;font-size:120px;color:#a78bfa22;animation:float 5s ease-in-out infinite}
h1{font-size:clamp(30px,6vw,50px);letter-spacing:-1.8px;line-height:1.08;margin:12px 0}
h2{font-size:20px;margin:0 0 14px}p{line-height:1.6;color:#c2c9df}
.grad{background:linear-gradient(90deg,#c4b5fd,#67e8f9);color:transparent;background-clip:text}
.sub{color:var(--muted);max-width:650px}.layout{display:grid;grid-template-columns:1.05fr .95fr;gap:16px;margin-top:18px}
.card{background:#121629eF;border:1px solid var(--line);border-radius:20px;padding:21px;box-shadow:0 12px 35px #0002;animation:rise .7s ease both}
.card:nth-child(2){animation-delay:.1s}.wide{grid-column:1/-1}
label{display:block;margin:16px 0 8px;font-weight:700}
input[type=text],textarea,input[type=file]{width:100%;border:1px solid #353c5b;border-radius:12px;background:#0b1020;color:#fff;padding:12px;font:inherit}
textarea{min-height:150px;resize:vertical}
.drop{border:1.5px dashed #6460a0;border-radius:16px;padding:22px 12px;text-align:center;background:#17172c;transition:.25s}
.drop:hover{border-color:var(--cyan);background:#1a2038}
.drop input{max-width:100%;margin-top:12px}
button,.btn{display:inline-block;border:0;border-radius:12px;padding:13px 17px;background:linear-gradient(100deg,#a78bfa,#67e8f9);color:#090b16;font-weight:850;font-size:15px;text-decoration:none;cursor:pointer;transition:transform .2s,filter .2s}
button:hover,.btn:hover{transform:translateY(-2px);filter:brightness(1.1)}
button:disabled{opacity:.6;cursor:wait}
.secondary{background:#252b45;color:#edf0ff;border:1px solid #414967}
.full{width:100%;margin-top:18px}
small,.muted{color:var(--muted);font-size:12px}
.features{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:18px}
.feature{padding:14px 12px;border:1px solid #292f4c;border-radius:14px;background:#111528a8}
.ico{font-size:23px}.feature b{display:block;margin:7px 0 4px}.feature small{line-height:1.4}
.alert{border:1px solid #705d36;background:#2b2519;padding:13px;border-radius:12px;color:#ffe2a4;margin-top:15px;white-space:pre-wrap;overflow-wrap:anywhere}
.result{white-space:pre-wrap;line-height:1.75;color:#e1e7fb;overflow-wrap:anywhere}
.score{font-size:48px;font-weight:900;background:linear-gradient(120deg,#c4b5fd,#67e8f9);background-clip:text;color:transparent}
.spinner{display:none;margin:15px auto;width:27px;height:27px;border:3px solid #343b59;border-top-color:var(--cyan);border-radius:50%;animation:spin .8s linear infinite}
footer{text-align:center;color:#858eac;font-size:12px;margin-top:25px}
@keyframes rise{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:translateY(0)}}
@keyframes float{0%,100%{transform:translateY(0) rotate(0)}50%{transform:translateY(10px) rotate(8deg)}}
@keyframes spin{to{transform:rotate(360deg)}}
@media(max-width:700px){.layout{grid-template-columns:1fr}.wide{grid-column:auto}.hero{padding:25px 19px}.features{grid-template-columns:1fr}.card{padding:17px}}
"""


def page(result="", error="", filename="", job="", role=""):
    err = '<div class="alert">' + html.escape(error) + '</div>' if error else ""
    res = ""
    if result:
        res = (
            '<section class="card wide" id="results">'
            '<div class="pill">✦ AI ANALYSIS COMPLETE</div>'
            '<h2 style="margin-top:16px">Your career intelligence report</h2>'
            '<div class="result">' + html.escape(result) + '</div>'
            '<button class="secondary" onclick="window.print()">Print / Save as PDF</button>'
            '</section>'
        )
    return r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#090b16"><title>CareerGlow AI</title>
<style>""" + STYLE + r"""</style></head><body><main>
<nav><div class="logo">✦ Career<b>Glow</b> AI</div><span class="pill">● PRIVATE LOCAL APP</span></nav>
<section class="hero"><div class="pill">YOUR PERSONAL AI CAREER COACH</div>
<h1>Make your next move<br><span class="grad">your best move.</span></h1>
<p class="sub">Turn your resume into a career strategy. Discover your strengths, understand job requirements, and prepare to stand out.</p>
</section>
""" + err + r"""
<form class="layout" method="post" enctype="multipart/form-data" id="analyzeForm">
<section class="card">
<h2>01 · Your resume</h2><p class="muted">Upload a file. No resume text box required.</p>
<div class="drop"><div style="font-size:32px">☁️</div><b>Choose your resume</b>
<p class="muted">PDF or DOCX · Maximum 8 MB</p>
<input type="file" name="resume" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" required>
<div class="muted" id="fileName">""" + html.escape(filename) + r"""</div></div>
<label for="role">Target job title (optional)</label>
<input type="text" name="role" id="role" placeholder="e.g. Python Developer" value=\"""" + html.escape(role, quote=True) + r"""">
</section>
<section class="card">
<h2>02 · Your next opportunity</h2><p class="muted">Add the job details so the AI can tailor its advice.</p>
<label for="job">Job description (optional)</label>
<textarea name="job" id="job" placeholder="Paste the job description here for a more accurate match...">""" + html.escape(job) + r"""</textarea>
<div class="muted">Leave this empty for a general resume review.</div>
<button class="full" type="submit" id="submitBtn">✦ Analyze my career profile</button>
<div class="spinner" id="spinner"></div>
<p class="muted" id="loading" style="text-align:center"></p>
</section>
</form>
<div class="features">
<div class="feature"><span class="ico">🧠</span><b>AI resume review</b><small>Clarity, impact, structure, and actionable improvements.</small></div>
<div class="feature"><span class="ico">🎯</span><b>Job fit insights</b><small>Strengths, missing skills, and targeted recommendations.</small></div>
<div class="feature"><span class="ico">🎤</span><b>Interview prep</b><small>Role-specific questions and practice answers.</small></div>
</div>
""" + res + r"""
<footer>CareerGlow AI · Ollama Cloud · Keep your API key private · AI feedback can be imperfect</footer>
</main>
<script>
const file=document.querySelector('input[type=file]');
file.addEventListener('change',()=>document.getElementById('fileName').textContent=file.files[0]?.name||'No file selected');
document.getElementById('analyzeForm').addEventListener('submit',()=>{
 const b=document.getElementById('submitBtn');b.disabled=true;b.textContent='Analyzing your profile…';
 document.getElementById('spinner').style.display='block';
 document.getElementById('loading').textContent='Reading your resume and preparing personalized feedback…';
});
</script></body></html>"""

def extract_docx(data):
    try:
        import io
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            root = ET.fromstring(z.read("word/document.xml"))
        ns = {"w":"http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        return "\n".join("".join(t.text or "" for t in p.findall(".//w:t", ns))
                         for p in root.findall(".//w:p", ns))
    except Exception:
        return ""

def extract_resume(filename, data):
    ext = os.path.splitext(filename.lower())[1]
    if ext == ".docx":
        return extract_docx(data)
    if ext == ".pdf":
        if not shutil.which("pdftotext"):
            raise ValueError("PDF support needs Poppler. Run: pkg install poppler")
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(data)
            path = f.name
        try:
            p = subprocess.run(["pdftotext", "-layout", path, "-"],
                               capture_output=True, text=True, timeout=25)
            if p.returncode:
                raise ValueError("Could not read this PDF. Try exporting it as a text-based PDF.")
            return p.stdout.strip()
        finally:
            try: os.unlink(path)
            except OSError: pass
    raise ValueError("Please upload a PDF or DOCX file.")

def ask_ai(resume, job, role):
    key = os.environ.get("OLLAMA_API_KEY", "").strip()
    if not key:
        raise ValueError("Ollama API key is not set. In Termux run: export OLLAMA_API_KEY='YOUR_KEY' then restart the app.")
    prompt = f"""You are a thoughtful, honest career coach. Analyze this resume.
Target role: {role or 'Infer a suitable role from the resume'}
Job description: {job or 'No job description provided; give a general resume review.'}

Return a well-structured report with these headings:
1. EXECUTIVE SUMMARY
2. RESUME STRENGTHS
3. IMPROVEMENTS WITH EXAMPLES
4. JOB MATCH (if job description supplied; distinguish evidence from assumptions)
5. SKILLS TO DEVELOP
6. ATS AND FORMATTING TIPS
7. INTERVIEW PRACTICE (5 role-specific questions and brief answer guidance)
8. ACTION PLAN (top 5 next steps)

Do not invent qualifications, employers, degrees, or achievements. Clearly mark any example wording that the user must verify. Be specific and constructive. Do not guarantee hiring outcomes.

RESUME TEXT:
{resume[:18000]}

JOB DESCRIPTION:
{job[:9000]}"""
    payload = json.dumps({
        "model": MODEL,
        "stream": False,
        "messages": [
            {"role":"system","content":"You are a professional resume reviewer and career coach. Be accurate and constructive."},
            {"role":"user","content":prompt}
        ],
        "options":{"temperature":0.3}
    }).encode()
    req = urllib.request.Request(API_URL, data=payload, method="POST", headers={
        "Authorization":"Bearer " + key,
        "Content-Type":"application/json",
        "Accept":"application/json"
    })
    try:
        with urllib.request.urlopen(req, timeout=150) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        text = data.get("message", {}).get("content", "")
        if not text:
            raise ValueError("The AI service returned an empty response. Check the selected model and API access.")
        return text
    except urllib.error.HTTPError as e:
        detail = e.read(1200).decode("utf-8", "replace")
        if e.code in (401, 403):
            raise ValueError("Ollama rejected the API key or access. Verify your key and model permissions.")
        if e.code == 404:
            raise ValueError("Ollama could not find the model. Set OLLAMA_MODEL to a model available to your account.")
        raise ValueError(f"Ollama API error ({e.code}): {detail}")
    except urllib.error.URLError as e:
        raise ValueError("Could not reach Ollama Cloud. Check your internet connection. Details: " + str(e.reason))

class Handler(BaseHTTPRequestHandler):
    def send_html(self, body, status=200):
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        self.send_html(page())

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > MAX_FILE + 1_500_000:
                self.send_html(page(error="Request too large or empty. Use a file under 8 MB."), 413)
                return
            raw = self.rfile.read(length)
            ctype = self.headers.get("Content-Type", "")
            if "multipart/form-data" not in ctype:
                self.send_html(page(error="Please submit the upload form."), 400)
                return
            msg = BytesParser(policy=default).parsebytes(
                b"Content-Type: " + ctype.encode() + b"\r\nMIME-Version: 1.0\r\n\r\n" + raw
            )
            file_data, filename, job, role = b"", "", "", ""
            for part in msg.iter_parts():
                name = part.get_param("name", header="content-disposition")
                payload = part.get_payload(decode=True) or b""
                if name == "resume":
                    filename = part.get_filename() or ""
                    file_data = payload
                elif name == "job":
                    job = payload.decode("utf-8", "replace").strip()
                elif name == "role":
                    role = payload.decode("utf-8", "replace").strip()[:200]
            if not filename or not file_data:
                raise ValueError("Choose a resume file first.")
            if len(file_data) > MAX_FILE:
                raise ValueError("File exceeds the 8 MB limit.")
            resume = extract_resume(filename, file_data)
            if len(resume.strip()) < 40:
                raise ValueError("Very little text was extracted. This may be a scanned PDF. Try a text-based PDF or DOCX.")
            result = ask_ai(resume, job, role)
            self.send_html(page(result=result, filename=filename, job=job, role=role) + "")
        except ValueError as e:
            self.send_html(page(error=str(e)), 400)
        except Exception:
            self.send_html(page(error="Something went wrong while processing the file. Check the file format, internet connection, API key, and Termux output."), 500)

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args))

if __name__ == "__main__":
    print("CareerGlow AI starting...")
    print("Open http://127.0.0.1:8501 in your phone browser.")
    print("AI calls use Ollama Cloud; keep your API key private.")
    HTTPServer((HOST, PORT), Handler).serve_forever()
