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
:root{--bg:#f8fafc;--card:#ffffff;--text:#0f172a;--muted:#64748b;--border:#e2e8f0;--primary:#2563eb;--primary-hover:#1d4ed8;--accent:#eff6ff}
body{margin:0;background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;min-height:100vh;line-height:1.5}
main{max-width:1100px;margin:0 auto;padding:32px 20px 60px}
nav{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:15px;margin-bottom:40px;background:#fff;padding:16px 24px;border-radius:12px;border:1px solid var(--border);box-shadow:0 1px 3px rgba(0,0,0,0.05)}
.logo{font-weight:700;font-size:18px;letter-spacing:-0.3px;color:#0f172a}.logo span{color:var(--primary)}
.pill{background:var(--accent);border:1px solid #bfdbfe;border-radius:20px;padding:5px 12px;color:var(--primary);font-size:12px;font-weight:600;display:inline-block}
.hero{background:linear-gradient(135deg,#1e40af 0%,#2563eb 100%);color:#fff;padding:40px 32px;border-radius:16px;margin-bottom:30px;box-shadow:0 10px 25px -5px rgba(37,99,235,0.2)}
.hero h1{font-size:clamp(26px,4vw,38px);letter-spacing:-0.8px;margin:8px 0 12px;font-weight:800}
.hero p{color:#dbeafe;margin:0;font-size:16px;max-width:600px}
.layout{display:grid;grid-template-columns:1fr 1fr;gap:24px;margin-top:20px}
.card{background:var(--card);border:1px solid var(--border);border-radius:16px;padding:28px;box-shadow:0 4px 6px -1px rgba(0,0,0,0.02),0 2px 4px -1px rgba(0,0,0,0.02)}
.wide{grid-column:1/-1}
label{display:block;margin:16px 0 6px;font-weight:600;font-size:14px;color:#334155}
input[type=text],input[type=email],textarea,input[type=file]{width:100%;border:1px solid var(--border);border-radius:10px;background:#f8fafc;color:var(--text);padding:12px 14px;font:inherit;font-size:14px;transition:all 0.2s}
input:focus,textarea:focus{outline:none;border-color:var(--primary);background:#fff;box-shadow:0 0 0 3px rgba(37,99,235,0.1)}
textarea{min-height:140px;resize:vertical}
.drop{border:2px dashed #cbd5e1;border-radius:12px;padding:24px 16px;text-align:center;background:#f8fafc;transition:0.2s}
.drop:hover{border-color:var(--primary);background:var(--accent)}
button,.btn{display:inline-block;border:0;border-radius:10px;padding:12px 20px;background:var(--primary);color:#fff;font-weight:600;font-size:14px;text-decoration:none;cursor:pointer;transition:background 0.2s,transform 0.1s}
button:hover,.btn:hover{background:var(--primary-hover)}
button:disabled{opacity:0.6;cursor:wait}
.secondary{background:#e2e8f0;color:#334155}
.secondary:hover{background:#cbd5e1}
.full{width:100%;margin-top:20px}
small,.muted{color:var(--muted);font-size:13px}
.alert{border:1px solid #fecaca;background:#fef2f2;padding:14px;border-radius:10px;color:#991b1b;margin-bottom:20px;font-size:14px}
.result{white-space:pre-wrap;line-height:1.7;color:#334155;font-size:14px}
.resume-box{background:#fff;color:#0f172a;padding:40px;border-radius:12px;margin-top:20px;font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;font-size:14px;line-height:1.6;white-space:pre-wrap;border:1px solid var(--border);box-shadow:0 10px 15px -3px rgba(0,0,0,0.05)}
.resume-box h2, .resume-box h3 { color:#1e3a8a; }
.spinner{display:none;margin:20px auto;width:30px;height:30px;border:3px solid var(--border);border-top-color:var(--primary);border-radius:50%;animation:spin 0.8s linear infinite}
footer{text-align:center;color:var(--muted);font-size:13px;margin-top:40px}

@media print {
  body * { visibility: hidden; }
  #printableResume, #printableResume * { visibility: visible; }
  #printableResume { position: absolute; left: 0; top: 0; width: 100%; margin: 0; padding: 20px; background: #fff !important; color: #000 !important; border: none; box-shadow: none; }
}

@keyframes spin{to{transform:rotate(360deg)}}
@media(max-width:768px){.layout{grid-template-columns:1fr}.wide{grid-column:auto}}
"""

def page(user=None, analysis_report="", recreated_resume="", error="", filename="", job="", role=""):
    err = f'<div class="alert">{html.escape(error)}</div>' if error else ""
    res = ""
    if analysis_report and recreated_resume:
        res = f"""
        <section class="card wide" style="margin-top:24px">
          <span class="pill">Analysis & Optimization Report</span>
          <h2 style="margin-top:14px;color:#0f172a">1. Strategic Recalibration</h2>
          <div class="result">{html.escape(analysis_report)}</div>

          <hr style="border:0;border-top:1px solid var(--border);margin:30px 0">

          <h2 style="color:#0f172a">2. Precision ATS Resume Template</h2>
          <p class="muted">Formatted for corporate applicant tracking systems and executive review.</p>
          <button class="btn" style="margin:16px 0;background:#0f172a" onclick="window.print()">📥 Download Clean Resume PDF</button>
          
          <div class="resume-box" id="printableResume">{recreated_resume}</div>
        </section>
        """

    if not user:
        body_Section = """
        <section class="card" style="max-width:440px;margin:40px auto">
          <span class="pill">Secure Portal</span>
          <h2 style="margin-top:12px;color:#0f172a">Sign in to your account</h2>
          <p class="muted">Access your 1st free precision resume build and history archive.</p>
          <form method="post" action="/login" style="margin-top:20px">
            <label for="name">Full Name</label>
            <input type="text" name="name" id="name" placeholder="Rahul Sharma" required>
            <label for="email">Email Address</label>
            <input type="email" name="email" id="email" placeholder="rahul@example.com" required>
            <button class="full" type="submit">Continue to Dashboard</button>
          </form>
        </section>
        """
        nav_right = '<span class="pill">Guest Session</span>'
    else:
        u_email = html.escape(user["email"])
        free_left = (user["free_used"] == 0)
        credits = user["paid_credits"]
        can_use = free_left or (credits > 0)

        badge = "🎁 1 Free Build Available" if free_left else f"⚡ Credits: {credits} (₹1/rebuild)"
        nav_right = f'<div style="display:flex;gap:12px;align-items:center"><span class="pill">{badge}</span><span style="font-size:14px;font-weight:600">{u_email}</span><a href="/logout" style="color:#dc2626;text-decoration:none;font-size:13px;font-weight:600">Sign out</a></div>'

        if can_use:
            btn_label = "✦ Generate Precision Resume (1st Free)" if free_left else "✦ Generate Precision Resume (Uses 1 Credit)"
            body_Section = f"""
            <form class="layout" method="post" action="/" enctype="multipart/form-data" id="analyzeForm">
              <section class="card">
                <h3 style="margin-top:0;color:#0f172a">Source Resume</h3>
                <p class="muted">Upload your existing resume file.</p>
                <div class="drop">
                  <div style="font-size:28px;margin-bottom:8px">📄</div>
                  <b style="font-size:14px">Upload PDF or DOCX</b>
                  <p class="muted" style="font-size:12px;margin:4px 0">Maximum file size: 8 MB</p>
                  <input type="file" name="resume" accept=".pdf,.docx" required style="margin-top:10px">
                  <div class="muted" id="fileName" style="margin-top:8px;font-weight:500">{html.escape(filename)}</div>
                </div>
                <label for="role">Target Job Title *</label>
                <input type="text" name="role" id="role" placeholder="e.g. Senior Software Engineer" value="{html.escape(role, quote=True)}" required>
              </section>

              <section class="card">
                <h3 style="margin-top:0;color:#0f172a">Job Description & Alignment</h3>
                <p class="muted">Paste target requirements for keyword matching.</p>
                <label for="job">Job Description (Optional)</label>
                <textarea name="job" id="job" placeholder="Paste job requirements here...">{html.escape(job)}</textarea>
                <button class="full" type="submit" id="submitBtn" style="margin-top:24px">{btn_label}</button>
                <div class="spinner" id="spinner"></div>
                <p class="muted" id="loading" style="text-align:center;margin-top:10px"></p>
              </section>
            </form>
            """
        else:
            body_Section = f"""
            <section class="card" style="max-width:500px;margin:40px auto;text-align:center">
              <span class="pill">Credits Required</span>
              <h2 style="margin-top:12px;color:#0f172a">Unlock Precision Rebuild</h2>
              <p class="muted">You have used your complimentary resume. Add 1 credit for ₹1 to build another tailored version.</p>
              <button class="full" id="pay1RsBtn" onclick="pay1Rs()" style="margin-top:20px">Pay ₹1 via UPI / Card</button>
              <p class="muted" id="payMsg" style="margin-top:12px"></p>
            </section>
            <script src="https://checkout.razorpay.com/v1/checkout.js"></script>
            <script>
            async function pay1Rs() {{
              const btn = document.getElementById('pay1RsBtn');
              const msg = document.getElementById('payMsg');
              btn.disabled = true;
              msg.textContent = 'Initializing secure payment...';
              const res = await fetch('/create-order', {{method:'POST'}});
              const order = await res.json();
              if (order.test_mode) {{
                await fetch('/verify-payment', {{
                  method:'POST',
                  headers:{{'Content-Type':'application/json'}},
                  body: JSON.stringify({{ razorpay_order_id: order.id, razorpay_payment_id: 'pay_test_' + Date.now(), razorpay_signature: 'test' }})
                }});
                window.location.reload();
                return;
              }}
              const rzp = new Razorpay({{
                key: "{paywall.RZP_KEY_ID}",
                amount: order.amount,
                currency: order.currency,
                name: "CareerGlow AI",
                description: "Precision Rebuild Credit",
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
<title>CareerGlow AI · Enterprise Resume Studio</title>
<link rel="manifest" href="/manifest.json">
<style>""" + STYLE + r"""</style></head><body><main>
<nav><div class="logo">Career<span>Glow</span> Enterprise</div>""" + nav_right + r"""</nav>
<section class="hero">
  <span class="pill" style="background:rgba(255,255,255,0.15);color:#fff;border-color:rgba(255,255,255,0.3)">AI Career Studio</span>
  <h1>Precision Resume Engine</h1>
  <p>Engineered for high-ranking corporate ATS screeners and executive recruitment.</p>
</section>
""" + err + res + body_Section + r"""
<footer>CareerGlow Enterprise · Secure Cloud Infrastructure</footer>
</main>
<script>
const file=document.querySelector('input[type=file]');
if (file) {
  file.addEventListener('change',()=>document.getElementById('fileName').textContent=file.files[0]?.name||'Selected');
}
const form=document.getElementById('analyzeForm');
if (form) {
  form.addEventListener('submit',()=>{
   const b=document.getElementById('submitBtn');b.disabled=true;b.textContent='Optimizing resume…';
   document.getElementById('spinner').style.display='block';
   document.getElementById('loading').textContent='Analyzing job requirements and formatting professional template…';
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
            raise ValueError("PDF support requires Poppler package.")
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(data)
            path = f.name
        try:
            p = subprocess.run(["pdftotext", "-layout", path, "-"], capture_output=True, text=True, timeout=25)
            if p.returncode:
                raise ValueError("Could not read PDF. Please use a text-based PDF.")
            return p.stdout.strip()
        finally:
            try: os.unlink(path)
            except OSError: pass
    raise ValueError("Please upload a valid PDF or DOCX file.")

def ask_ai(resume, job, role):
    key = os.environ.get("OLLAMA_API_KEY", "").strip()
    if not key:
        raise ValueError("Ollama API key not configured.")
    prompt = f"""You are an elite executive resume writer. Rebuild this resume for the target role: {role}.
Job Description: {job or 'Optimize for top corporate ATS standards.'}

Return response split into:
---REPORT---
Action items and keyword additions.
---RESUME---
Clean HTML structured resume content (using <h2>, <h3>, <p>, <ul>, <li>, <strong>).

RESUME TEXT:
{resume[:18000]}

JOB DESCRIPTION:
{job[:9000]}"""
    payload = json.dumps({
        "model": MODEL,
        "stream": False,
        "messages": [
            {"role":"system","content":"You are a professional resume writer. Return valid HTML in the ---RESUME--- block."},
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
            raise ValueError("Empty response from AI.")
        return text
    except urllib.error.HTTPError as e:
        raise ValueError(f"AI API error ({e.code})")
    except urllib.error.URLError as e:
        raise ValueError("Network error reaching AI service.")

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
                "name": "CareerGlow Enterprise",
                "short_name": "CareerGlow",
                "start_url": "/",
                "display": "standalone",
                "background_color": "#f8fafc",
                "theme_color": "#2563eb",
                "icons": []
            })
            return
        if self.path == "/sw.js":
            self.send_response(200, content_type="application/javascript")
            self.end_headers()
            self.wfile.write(b"self.addEventListener('fetch', function(e) {});")
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
                self.send_html(page(error="Invalid email address."), 400)
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
                self.send_html(page(user=user, error="Free credit used. Please add credit to proceed."), 402)
                return
            if length <= 0 or length > MAX_FILE + 1_500_000:
                self.send_html(page(user=user, error="File size exceeds 8 MB limit."), 413)
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
                raise ValueError("No resume file uploaded.")
            if not role:
                raise ValueError("Target Job Title is required.")
            
            resume = extract_resume(filename, file_data)
            ai_output = ask_ai(resume, job, role)
            
            if "---RESUME---" in ai_output:
                report_part, resume_part = ai_output.split("---RESUME---", 1)
            else:
                report_part, resume_part = ai_output, ai_output

            paywall.consume_credit(user["email"])
            updated_user = paywall.get_or_create_user(user["email"])
            self.send_html(page(user=updated_user, analysis_report=report_part.strip(), recreated_resume=resume_part.strip(), filename=filename, job=job, role=role))
        except ValueError as e:
            self.send_html(page(user=user, error=str(e)), 400)
        except Exception:
            self.send_html(page(user=user, error="An unexpected server error occurred."), 500)

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args))

if __name__ == "__main__":
    print(f"CareerGlow Enterprise running on http://{HOST}:{PORT}")
    HTTPServer((HOST, PORT), Handler).serve_forever()
