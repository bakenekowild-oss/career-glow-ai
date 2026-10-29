import os, json, hmac, hashlib, base64, sqlite3, urllib.request
from http.cookies import SimpleCookie

DB_PATH = os.environ.get("DB_PATH", "users.db")
SECRET_KEY = os.environ.get("APP_SECRET", "change-this-secret-in-production")
RZP_KEY_ID = os.environ.get("RZP_KEY_ID", "")         # Razorpay Key ID
RZP_KEY_SECRET = os.environ.get("RZP_KEY_SECRET", "") # Razorpay Key Secret

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                email TEXT PRIMARY KEY,
                name TEXT,
                free_used INTEGER DEFAULT 0,
                paid_credits INTEGER DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                payment_id TEXT PRIMARY KEY,
                email TEXT,
                amount INTEGER
            )
        """)

def sign_session(email: str) -> str:
    sig = hmac.new(SECRET_KEY.encode(), email.encode(), hashlib.sha256).hexdigest()[:24]
    return f"{email}|{sig}"

def verify_session(cookie_header: str):
    if not cookie_header:
        return None
    cookie = SimpleCookie()
    cookie.load(cookie_header)
    if "session_user" not in cookie:
        return None
    val = cookie["session_user"].value
    if "|" not in val:
        return None
    email, sig = val.rsplit("|", 1)
    expected = hmac.new(SECRET_KEY.encode(), email.encode(), hashlib.sha256).hexdigest()[:24]
    return email if hmac.compare_digest(sig, expected) else None

def get_or_create_user(email: str, name: str = ""):
    email = email.strip().lower()
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute("SELECT email, name, free_used, paid_credits FROM users WHERE email = ?", (email,))
        row = cur.fetchone()
        if not row:
            conn.execute("INSERT INTO users (email, name, free_used, paid_credits) VALUES (?, ?, 0, 0)", (email, name))
            return {"email": email, "name": name, "free_used": 0, "paid_credits": 0}
        return {"email": row[0], "name": row[1], "free_used": row[2], "paid_credits": row[3]}

def can_generate_resume(email: str) -> bool:
    u = get_or_create_user(email)
    return (u["free_used"] == 0) or (u["paid_credits"] > 0)

def consume_credit(email: str) -> bool:
    u = get_or_create_user(email)
    with sqlite3.connect(DB_PATH) as conn:
        if u["free_used"] == 0:
            conn.execute("UPDATE users SET free_used = 1 WHERE email = ?", (email,))
            return True
        if u["paid_credits"] > 0:
            conn.execute("UPDATE users SET paid_credits = paid_credits - 1 WHERE email = ?", (email,))
            return True
    return False

def create_razorpay_1rs_order(email: str):
    """Creates a ₹1 (100 paise) order using pure urllib.request (no pip needed)."""
    if not RZP_KEY_ID or not RZP_KEY_SECRET:
        # Local test mode when Razorpay keys are not set yet
        return {"id": "order_test_1rs", "amount": 100, "currency": "INR", "test_mode": True}

    payload = json.dumps({
        "amount": 100,  # 100 paise = ₹1.00
        "currency": "INR",
        "receipt": f"rcpt_{hashlib.md5(email.encode()).hexdigest()[:8]}",
        "notes": {"email": email}
    }).encode()

    auth = base64.b64encode(f"{RZP_KEY_ID}:{RZP_KEY_SECRET}".encode()).decode()
    req = urllib.request.Request(
        "https://api.razorpay.com/v1/orders",
        data=payload,
        headers={"Content-Type": "application/json", "Authorization": f"Basic {auth}"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())

def verify_and_credit_payment(email: str, order_id: str, payment_id: str, signature: str) -> bool:
    """Verifies Razorpay signature (or test mode) and adds 1 resume recreation credit."""
    if order_id == "order_test_1rs" and (not RZP_KEY_SECRET):
        verified = True
    else:
        msg = f"{order_id}|{payment_id}".encode()
        expected = hmac.new(RZP_KEY_SECRET.encode(), msg, hashlib.sha256).hexdigest()
        verified = hmac.compare_digest(expected, signature)

    if not verified:
        return False

    with sqlite3.connect(DB_PATH) as conn:
        # Prevent replay of the same payment_id
        cur = conn.execute("SELECT 1 FROM payments WHERE payment_id = ?", (payment_id,))
        if cur.fetchone():
            return False
        conn.execute("INSERT INTO payments (payment_id, email, amount) VALUES (?, ?, 100)", (payment_id, email))
        conn.execute("UPDATE users SET paid_credits = paid_credits + 1 WHERE email = ?", (email,))
    return True
