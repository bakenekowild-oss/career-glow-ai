#!/usr/bin/env python3
import os, re, json, html, shutil, subprocess, tempfile, zipfile
import urllib.request, urllib.error
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import quote, parse_qs
from email.parser import BytesParser
from email.policy import default
from xml.etree import ElementTree as ET

import paywall

HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8501"))
API_URL = "https://ollama.com/api/chat"
MODEL = os.environ.get("OLLAMA_MODEL", "gemma4:31b")
MAX_FILE = 8 * 1024 * 1024

paywall.init_db()

STYLE = r"""
*{box-sizing:border-box}
:root{color-scheme:dark;--bg:#090b16;--panel:#13172a;--line:#292f4c;--muted:#a3abc6;--white:#f5f6ff;--purple:#a78bfa;--cyan:#67e8f9}
body{margin:0;background:radial-gradient(ellipse at 15% 0%,#282050 0,transparent 40%),radial-gradient(ellipse at 100% 40%,#102f49 0,transparent 38%),var(--bg);color:var(--white);font:15px system-ui,sans-serif;min-height:100vh}
main{max-width:1050px;margin:auto;padding:24px 16px 60px}
nav{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px;margin-bottom:30px}
.logo{font-weight:850;letter-spacing:-.5px;font-size:19px}.logo b{color:var(--cyan)}
.pill{border:1px solid #3b4260;border-radius:999px;padding:7px 12px;color:#c7d2fe;font-size:12px;display:inline-block}
.hero{position:relative;overflow:hidden;padding:30px 24px;border:1px solid #38365d;border-radius:25px;background:linear-gradient(120deg,#211a42d9,#102a3ad9);box-shadow:0 20px 70px #0005;animation:rise .65s ease both}
.hero:after{content:"✦";position:absolute;right:28px;top:10px;font-size:120px;color:#a78bfa22;animation:float 5s ease-in-out infinite}
h1{font-size:clamp(30px,6vw,50px);letter-spacing:-1.8px;line-height:1.08;margin:12px 0}
h2{font-size:20px;margin:0 0 14px}p{line-height:1.6;color:#c2c9df}
.grad{background:linear-gradient(90deg,#c4b5fd,#67e8f9);color:transparent;background-clip:text}
.sub{color:var(--muted);max-width:650px}.layout{display:grid;grid-template-columns:1.05fr .95fr;gap:16px;margin-top:18px}
.card{background:#121629eF;border:1px solid var(--line);border-radius:20px;padding:21px;box-shadow:0 12px 35px #0002;animation:rise .7s ease both}
.card:nth-child(2){animation-delay:.1s}.wide{grid-column:1/-1}
label{display:block;margin:16px 0 8px;font-weight:700}
input[type=text],input[type=email],textarea,input[type=file]{width:100%;border:1px solid #353c5b;border-radius:12px;background:#0b1020;color:#fff;padding:12px;font:inherit}
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
.resume-box{background:#fff;color:#111;padding:32px;border-radius:12px;margin-top:15px;font-family:Arial,sans-serif;font-size:14px;line-height:1.6;white-space:pre-wrap;box-shadow:0 4px 20px #0004}
.spinner{display:none;margin:15px auto;width:27px;height:27px;border:3px solid #343b59;border-top-color:var(--cyan);border-radius:50%;animation:spin .8s linear infinite}
footer{text-align:center;color:#858eac;font-size:12px;margin-top:25px}

@media print {
  body * { visibility: hidden; }
  #printableResume, #printableResume * { visibility: visible; }
  #printableResume { position: absolute; left: 0; top: 0; width: 100%; margin: 0; padding: 20px; background: #fff !important; color: #000 !important; box-shadow: none; }
}

@keyframes rise{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:translateY(0)}}
@keyframes float{0%,100%{transform:translateY(0) rotate(0)}50%{transform:translateY(10px) rotate(8deg)}}
@keyframes spin{to{transform:rotate(360deg)}}
@media(max-width:700px){.layout{grid-template-columns:1fr}.wide{grid-column:auto}.hero{padding:25px 19px}.features{grid-template-columns:1fr}.card{padding:17px}}
"""

def page(user=None, analysis_report="", recreated_resume="", error="", filename="", job="", role=""):
    err = '<div class="alert">' + html.escape(error) + '</div>' if error else ""
    res = ""
    if analysis_report and recreated_resume:
        res = f"""
        <section class="card wide" id="results" style="margin-top:18px">
          <div class="pill">✦ AI CAREER COACH & RESUME RECREATION</div>
          <h2 style="margin-top:16px">1. Actions Taken to Recreate Your Resume</h2>
          <div class="result">{html.escape(analysis_report)}</div>

          <h2 style="margin-top:30px">2. Your Perfectly Recreated ATS-Ready Resume</h2>
          <p class="muted">Click below to print or save *only* this clean resume as a PDF.</p>
          <button class="full" style="margin-bottom:15px" onclick="printResume()">📄 Download Clean ATS Resume (PDF)</button>
          
          <div class="resume-box" id="printableResume">{html.escape(recreated_resume)}</div>
        </section>
        <script>
        function printResume() {{
          window.print();
        }}
        </script>
        """

    if not user:
        body_Section = """
        <section class="card" style="max-width:480px;margin:22px auto">
          <div class="pill">🎁 1ST RESUME 100% FREE</div>
          <h2 style="margin-top:12px">Sign in to build & analyze your resume</h2>
          <p class="muted">Your first AI resume analysis & recreation is free. Recreating again later costs just ₹1.</p>
          <form method="post" action="/login">
            <label for="name">Your Name</label>
            <input type="text" name="name" id="name" placeholder="e.g. Rahul Sharma" required>
            <label for="email">Email Address</label>
            <input type="email" name="email" id="email" placeholder="you@example.com" required>
            <button class="full" type="submit">✦ Continue Free</button>
          </form>
        </section>
        """
        nav_right = '<span class="pill">● FREE LOGIN</span>'
    else:
        u_email = html.escape(user["email"])
        free_left = (user["free_used"] == 0)
        credits = user["paid_credits"]
        can_use = free_left or (credits > 0)

        badge = "🎁 1 Free Resume Left" if free_left else f"⚡ Credits: {credits} (₹1/recreate)"
        nav_right = f'<div style="display:flex;gap:8px;align-items:center"><span class="pill">{badge}</span><span class="pill">{u_email}</span><a href="/logout" class="pill" style="text-decoration:none;color:#fca5a5">Logout</a></div>'

        if can_use:
            btn_label = "✦ Recreate & Analyze Resume (1st FREE)" if free_left else f"✦ Recreate & Analyze Resume (Uses 1 Credit)"
            body_Section = f"""
            <form class="layout" method="post" action="/" enctype="multipart/form-data" id="analyzeForm">
            <section class="card">
            <h2>01 · Your resume</h2><p class="muted">Upload your current resume to analyze and recreate.</p>
            <div class="drop"><div style="font-size:32px">☁️</div><b>Choose your resume</b>
            <p class="muted">PDF or DOCX · Maximum 8 MB</p>
            <input type="file" name="resume" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" required>
            <div class="muted" id="fileName">{html.escape(filename)}</div></div>
            <label for="role">Target job title (optional)</label>
            <input type="text" name="role" id="role" placeholder="e.g. Python Developer" value="{html.escape(role, quote=True)}">
            </section>
            <section class="card">
            <h2>02 · Your next opportunity</h2><p class="muted">Add the job details so the AI can tailor & recreate your resume.</p>
            <label for="job">Job description (optional)</label>
            <textarea name="job" id="job" placeholder="Paste the job description here for a more accurate match...">{html.escape(job)}</textarea>
            <div class="muted">Leave this empty for a general ATS resume recreation.</div>
            <button class="full" type="submit" id="submitBtn">{btn_label}</button>
            <div class="spinner" id="spinner"></div>
            <p class="muted" id="loading" style="text-align:center"></p>
            </section>
            </form>
            """
        else:
            body_Section = f"""
            <section class="card" style="max-width:540px;margin:22px auto;text-align:center">
              <div class="pill">⚡ RECREATE RESUME UNLOCK</div>
              <h2 style="margin-top:14px">Recreate Your Resume for Just ₹1</h2>
              <p class="muted">You have already used your 1st free resume. Unlock another AI resume recreation and full job match report for ₹1.</p>
              <button class="full" id="pay1RsBtn" onclick="pay1Rs()">💳 Pay ₹1 to Recreate Resume</button>
              <p class="muted" id="payMsg" style="margin-top:10px"></p>
            </section>
            <script src="https://checkout.razorpay.com/v1/checkout.js"></script>
            <script>
            async function pay1Rs() {{
              const btn = document.getElementById('pay1RsBtn');
              const msg = document.getElementById('payMsg');
              btn.disabled = true;
              msg.textContent = 'Creating ₹1 payment order...';
              const res = await fetch('/create-order', {{method:'POST'}});
              const order = await res.json();
              if (order.test_mode) {{
                msg.textContent = 'Test Mode active (no Razorpay keys set): Crediting ₹1...';
                await fetch('/verify-payment', {{
                  method:'POST',
                  headers:{{'Content-Type':'application/json'}},
                  body: JSON.stringify({{
                    razorpay_order_id: order.id,
                    razorpay_payment_id: 'pay_test_' + Date.now(),
                    razorpay_signature: 'test_sig'
                  }})
                }});
                window.location.reload();
                return;
              }}
              const rzp = new Razorpay({{
                key: "{paywall.RZP_KEY_ID}",
                amount: order.amount,
                currency: order.currency,
                name: "CareerGlow AI",
                description: "Recreate Resume (₹1)",
                order_id: order.id,
                handler: async function (response) {{
                  await fetch('/verify-payment', {{
                    method:'POST',
                    headers:{{'Content-Type':'application/json'}},
                    body: JSON.stringify(response)
                  }});
                  window.location.reload();
                }}
              }});
              rzp.open();
              btn.disabled = false;
            }}
            </script>
            """

    return r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#090b16"><title>CareerGlow AI</title>
<link rel="manifest" href="/manifest.json">
<style>""" + STYLE + r"""</style></head><body><main>
<nav><div class="logo">✦ Career<b>Glow</b> AI</div>""" + nav_right + r"""</nav>
<section class="hero"><div class="pill">YOUR PERSONAL AI CAREER COACH</div>
<h1>Make your next move<br><span class="grad">your best move.</span></h1>
<p class="sub">1st Resume Free · Recreate tailored ATS resumes anytime for just ₹1.</p>
</section>
""" + err + res + body_Section + r"""
<div class="features">
<div class="feature"><span class="ico">🧠</span><b>AI resume recreation</b><small>ATS-optimized rewrite + actionable improvements.</small></div>
<div class="feature"><span class="ico">🎯</span><b>Job fit insights</b><small>Strengths, missing skills, and targeted recommendations.</small></div>
<div class="feature"><span class="ico">🎤</span><b>Interview prep</b><small>Role-specific questions and practice answers.</small></div>
</div>
<footer>CareerGlow AI · 1st Resume Free · ₹1 Per Recreation</footer>
</main>
<script>
if ('serviceWorker' in navigator) { navigator.serviceWorker.register('/sw.js').catch(()=>{}); }
const file=document.querySelector('input[type=file]');
if (file) {
  file.addEventListener('change',()=>document.getElementById('fileName').textContent=file.files[0]?.name||'No file selected');
}
const form=document.getElementById('analyzeForm');
if (form) {
  form.addEventListener('submit',()=>{
   const b=document.getElementById('submitBtn');b.disabled=true;b.textContent='Recreating & analyzing your resume…';
   document.getElementById('spinner').style.display='block';
   document.getElementById('loading').textContent='Reading your resume and preparing your tailored ATS version…';
  });
}
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
        raise ValueError("Ollama API key is not set.")
    prompt = f"""You are an expert ATS resume writer and career coach. Analyze the user's resume and recreate it.
Target role: {role or 'Infer a suitable role from the resume'}
Job description: {job or 'No job description provided; optimize for general industry ATS standards.'}

You must return your response split into EXACTLY these two labeled sections:
---REPORT---
Detail exactly what actions you took to recreate this resume (e.g., restructured bullet points with action verbs, embedded missing keyword skills from the job description, improved summary impact for ATS compatibility, etc.).
---RESUME---
Write the complete, clean, professional, ATS-optimized text of the recreated resume (Contact info, Summary, Experience, Education, Skills) ready to be copied and printed. Do not include conversational filler in this section.

RESUME TEXT:
{resume[:18000]}

JOB DESCRIPTION:
{job[:9000]}"""
    payload = json.dumps({
        "model": MODEL,
        "stream": False,
        "messages": [
            {"role":"system","content":"You are a professional resume writer and career coach. Return the report and the clean resume separated by ---RESUME---."},
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
            raise ValueError("The AI service returned an empty response.")
        return text
    except urllib.error.HTTPError as e:
        detail = e.read(1200).decode("utf-8", "replace")
        raise ValueError(f"Ollama API error ({e.code}): {detail}")
    except urllib.error.URLError as e:
        raise ValueError("Could not reach Ollama Cloud: " + str(e.reason))

class Handler(BaseHTTPRequestHandler):
    def get_current_user(self):
        email = paywall.verify_session(self.headers.get("Cookie", ""))
        return paywall.get_or_create_user(email) if email else None

    def send_html(self, body, status=200, cookie=None):
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(data)

    def send_json(self, obj, status=200):
        data = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/logout":
            self.send_response(303)
            self.send_header("Set-Cookie", "session_user=; Path=/; Max-Age=0")
            self.send_header("Location", "/")
            self.end_headers()
            return
        if self.path == "/manifest.json":
            self.send_json({
                "name": "CareerGlow AI Resume Builder",
                "short_name": "CareerGlow",
                "start_url": "/",
                "display": "standalone",
                "background_color": "#090b16",
                "theme_color": "#090b16",
                "icons": [{"src": "/icon.svg", "sizes": "512x512", "type": "image/svg+xml", "purpose": "any maskable"}]
            })
            return
        if self.path == "/sw.js":
            sw = b"self.addEventListener('fetch', function(e) {});"
            self.send_response(200)
            self.send_header("Content-Type", "application/javascript")
            self.send_header("Content-Length", str(len(sw)))
            self.end_headers()
            self.wfile.write(sw)
            return
        if self.path == "/icon.svg":
            svg = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><rect width="512" height="512" rx="110" fill="#090b16"/><text x="50%" y="56%" dominant-baseline="middle" text-anchor="middle" font-size="260" fill="#67e8f9">&#10022;</text></svg>'
            self.send_response(200)
            self.send_header("Content-Type", "image/svg+xml")
            self.send_header("Content-Length", str(len(svg)))
            self.end_headers()
            self.wfile.write(svg)
            return

        user = self.get_current_user()
        self.send_html(page(user=user))

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length > 0 else b""

        if self.path == "/login":
            params = parse_qs(raw.decode("utf-8", "replace"))
            email = (params.get("email", [""])[0]).strip().lower()
            name = (params.get("name", [""])[0]).strip()
            if not email or "@" not in email:
                self.send_html(page(error="Please enter a valid email address."), 400)
                return
            paywall.get_or_create_user(email, name)
            token = paywall.sign_session(email)
            self.send_response(303)
            self.send_header("Set-Cookie", f"session_user={token}; Path=/; HttpOnly; Max-Age=2592000")
            self.send_header("Location", "/")
            self.end_headers()
            return

        user = self.get_current_user()
        if not user:
            self.send_html(page(error="Please sign in first."), 401)
            return

        if self.path == "/create-order":
            order = paywall.create_razorpay_1rs_order(user["email"])
            self.send_json(order)
            return

        if self.path == "/verify-payment":
            body = json.loads(raw.decode("utf-8", "replace") or "{}")
            ok = paywall.verify_and_credit_payment(
                user["email"],
                body.get("razorpay_order_id", ""),
                body.get("razorpay_payment_id", ""),
                body.get("razorpay_signature", "")
            )
            self.send_json({"ok": ok})
            return

        try:
            if not paywall.can_generate_resume(user["email"]):
                self.send_html(page(user=user, error="Free resume already used. Please pay ₹1 to recreate your resume."), 402)
                return
            if length <= 0 or length > MAX_FILE + 1_500_000:
                self.send_html(page(user=user, error="Request too large or empty. Use a file under 8 MB."), 413)
                return
            ctype = self.headers.get("Content-Type", "")
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
            resume = extract_resume(filename, file_data)
            if len(resume.strip()) < 40:
                raise ValueError("Very little text was extracted. Try a text-based PDF or DOCX.")

            ai_output = ask_ai(resume, job, role)
            
            if "---RESUME---" in ai_output:
                report_part, resume_part = ai_output.split("---RESUME---", 1)
            else:
                report_part = ai_output
                resume_part = ai_output

            paywall.consume_credit(user["email"])
            updated_user = paywall.get_or_create_user(user["email"])
            self.send_html(page(user=updated_user, analysis_report=report_part.strip(), recreated_resume=resume_part.strip(), filename=filename, job=job, role=role))
        except ValueError as e:
            self.send_html(page(user=user, error=str(e)), 400)
        except Exception:
            self.send_html(page(user=user, error="Something went wrong while processing the file."), 500)

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args))

if __name__ == "__main__":
    print(f"CareerGlow AI running on http://{HOST}:{PORT}")
    HTTPServer((HOST, PORT), Handler).serve_forever()
