from flask import Flask, render_template, request, redirect
import sqlite3
import hashlib
from datetime import datetime, timedelta
import secrets


from flask_limiter import Limiter
from flask_limiter.util import get_remote_address



app = Flask(__name__)

@app.route("/decision", methods=["POST"])
def decision():

    decision = request.form.get("decision")
    diagnosis = request.form.get("diagnosis")
    urgency = request.form.get("urgency")

    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    c.execute("""
    INSERT INTO user_decision
    (diagnosis, urgency, decision, created_at)
    VALUES (?, ?, ?, ?)
    """,(
        diagnosis,
        urgency,
        decision,
        datetime.now().strftime("%Y-%m-%d %H:%M")
    ))

    conn.commit()
    conn.close()

    if decision == "yes":
        return redirect(
            "https://maps.app.goo.gl/DpnGHvNXoa6BQTiA9"
        )

    return redirect("/")


# SESSION SECURITY
app.config['SECRET_KEY'] = secrets.token_hex(32)

# RATE LIMIT
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["20 per minute"]
)

DATABASE = "database.db"

# =========================
# DATABASE
# =========================
def init_db():

    conn = sqlite3.connect(DATABASE)

    c = conn.cursor()

    # DIAGNOSIS TABLE
    c.execute("""
    CREATE TABLE IF NOT EXISTS diagnosis (

        id INTEGER PRIMARY KEY AUTOINCREMENT,

        user_hash TEXT,
        symptom TEXT,
        result TEXT,

        urgency TEXT,
        job TEXT,

        created_at TEXT
    )
    """)

    # USER DECISION TABLE
    c.execute("""
    CREATE TABLE IF NOT EXISTS user_decision (

        id INTEGER PRIMARY KEY AUTOINCREMENT,

        diagnosis TEXT,
        urgency TEXT,

        decision TEXT,

        created_at TEXT
    )
    """)

    conn.commit()
    conn.close()

# =========================
# SECURITY
# =========================

@app.after_request
def secure_headers(response):

    response.headers[
        "X-Content-Type-Options"
    ] = "nosniff"

    response.headers[
        "X-Frame-Options"
    ] = "DENY"

    response.headers[
        "X-XSS-Protection"
    ] = "1; mode=block"

    response.headers[
        "Strict-Transport-Security"
    ] = "max-age=31536000"

    return response

import os

SECRET_SALT = os.getenv(
    "SECRET_SALT",
    "iDiagnoSecure2026"
)

def generate_user_hash(ip, user_agent):

    ip = ip or "unknown_ip"
    user_agent = user_agent or "unknown_agent"

    raw = ip + user_agent + SECRET_SALT

    return hashlib.sha256(raw.encode()).hexdigest()




from flask_wtf.csrf import CSRFProtect

csrf = CSRFProtect(app)

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=False,
    SESSION_COOKIE_SAMESITE='Lax'
)


# =========================
# DIAGNOSA ENGINE
# =========================
def diagnose(symptoms):

    if "overheat" in symptoms and "battery_drop" in symptoms:
        return "Kemungkinan IC Power / Battery Bermasalah"

    elif "charger_fail" in symptoms:
        return "Kemungkinan Flex Charging Rusak"

    elif "face_id" in symptoms:
        return "Kemungkinan Kerusakan Face ID"

    elif "bootloop" in symptoms:
        return "Kemungkinan Software / NAND"

    elif "screen_green" in symptoms:
        return "Kemungkinan LCD Bermasalah"

    return "Kerusakan tidak terdeteksi secara spesifik"

def analyze_urgency(result, job):

    urgency = "LOW"
    explanation = ""

    if "Battery" in result or "IC Power" in result:

        if job == "driver":
            urgency = "HIGH"

            explanation = """
            GPS, internet connection,
            and battery reliability are critical
            for online transportation workers.
            Sudden shutdown may interrupt work.
            """

        elif job == "creator":
            urgency = "MEDIUM"

            explanation = """
            High battery usage during recording,
            editing, and social media activity
            may worsen the issue.
            """

        else:
            urgency = "MEDIUM"

    return urgency, explanation

damage_explanations = {

    "IC Power / Battery ": {

        "cause": """
        Kerusakan biasanya terjadi akibat penggunaan
        charger non-original, overheating,
        baterai yang sudah mengalami degradasi,
        atau penggunaan perangkat saat charging.
        """,

        "impact": """
        Jika dibiarkan, perangkat dapat mengalami
        bootloop, mati total, atau kerusakan
        motherboard.
        """

    },

    "Kemungkinan LCD Bermasalah": {

        "cause": """
        Kerusakan LCD dapat terjadi akibat benturan,
        tekanan pada layar, atau kerusakan fleksibel display.
        """,

        "impact": """
        Kerusakan dapat menyebar menjadi green screen,
        ghost touch, atau layar mati total.
        """
    },
    
    "Kemungkinan IC Power / Battery Bermasalah": {

        "cause": """
        Kerusakan dapat terjadi akibat
        penggunaan charger non-original,
        overheating, baterai aus,
        atau penggunaan perangkat saat charging.
        """,

        "impact": """
        Jika dibiarkan, perangkat dapat
        mengalami restart sendiri,
        bootloop, bahkan kerusakan motherboard.
        """,

        "recommendation": """
        Segera lakukan pemeriksaan
        teknisi profesional untuk
        mencegah kerusakan lanjutan.
        """
    }

}

# =========================
# HOME
# =========================
@app.route("/", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def index():

    result = None
    
    urgency = None
    urgency_reason = None

    explanation = {
        "cause": "",
        "impact": "",
        "recommendation": ""
    }
    
    if request.method == "POST":

        symptoms = request.form.getlist("symptom")
        
        job = request.form.get("job", "casual")
        # VALIDASI
        allowed = [
            "overheat",
            "battery_drop",
            "charger_fail",
            "face_id",
            "bootloop",
            "screen_green",
            "touch_issue",
            "camera_fail",
            "speaker_problem",
            "wifi_problem"
        ]

        symptoms = [s for s in symptoms if s in allowed]

        result = diagnose(symptoms)
        urgency, urgency_reason = analyze_urgency(
        result,job)
        
        explanation = damage_explanations.get(
        result,
        {
            "cause": "No explanation available.",
            "impact": "No impact information available.",
            "recommendation": "Please consult technician."
        })

        # USER HASH
        ip = request.remote_addr
        user_agent = request.headers.get("User-Agent")

        user_hash = generate_user_hash(ip, user_agent)

        # SAVE DATABASE
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()

        c.execute("""
        INSERT INTO diagnosis
        (user_hash, symptom, result,
        urgency, job, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (
            user_hash,
            ", ".join(symptoms),
            result,
            urgency,
            job,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))
        conn.commit()
        conn.close()

    return render_template(

    "index.html",

    result=result,

    urgency=urgency,

    urgency_reason=urgency_reason,

    explanation=explanation
)

# =========================
# HISTORY
# =========================
@app.route("/history")
def history():

    ip = request.remote_addr
    user_agent = request.headers.get("User-Agent")

    user_hash = generate_user_hash(ip, user_agent)

    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    c.execute("""
    SELECT
    symptom,
    result,
    urgency,
    job,
    created_at
    FROM diagnosis
    WHERE user_hash=?
    ORDER BY id DESC
    """, (user_hash,))

    data = c.fetchall()

    conn.close()

    return render_template("history.html", data=data)

# =========================
# MAIN
# =========================
if __name__ == "__main__":
    init_db()
    app.run(debug=True)