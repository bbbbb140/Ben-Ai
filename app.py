import os
from flask import Flask, render_template, request, jsonify, session, send_file
from openai import OpenAI
import psycopg2
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "secret")

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
DATABASE_URL = os.getenv("DATABASE_URL")

def db():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    conn = db()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id SERIAL PRIMARY KEY,
        username TEXT UNIQUE,
        password TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS chats(
        id SERIAL PRIMARY KEY,
        room TEXT,
        user_name TEXT,
        message TEXT,
        reply TEXT,
        time TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS friends(
        user1 TEXT,
        user2 TEXT
    )
    """)

    conn.commit()
    cur.close()
    conn.close()

init_db()

@app.route("/")
def home():
    return render_template("index.html")

# -------- AUTH --------
@app.route("/signup", methods=["POST"])
def signup():
    d = request.get_json()
    try:
        conn = db()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO users (username,password) VALUES (%s,%s)",
            (d["username"], generate_password_hash(d["password"]))
        )
        conn.commit()
        session["user"] = d["username"]
        return jsonify({"success": True})
    except:
        return jsonify({"error": "User exists"})

@app.route("/login", methods=["POST"])
def login():
    d = request.get_json()
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT password FROM users WHERE username=%s", (d["username"],))
    u = cur.fetchone()

    if u and check_password_hash(u[0], d["password"]):
        session["user"] = d["username"]
        return jsonify({"success": True})

    return jsonify({"error": "Invalid login"})

# -------- CHAT --------
@app.route("/chat", methods=["POST"])
def chat():
    d = request.get_json()
    msg = d["message"]
    room = d.get("room", "default")
    user = session.get("user", "Guest")

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are BenAI."},
            {"role": "user", "content": msg}
        ]
    )

    reply = response.choices[0].message.content

    conn = db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO chats (room,user_name,message,reply,time) VALUES (%s,%s,%s,%s,%s)",
        (room, user, msg, reply, str(datetime.now()))
    )
    conn.commit()

    return jsonify({"reply": reply})

@app.route("/history")
def history():
    room = request.args.get("room", "default")
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT user_name,message,reply FROM chats WHERE room=%s", (room,))
    return jsonify(cur.fetchall())

# -------- FRIENDS --------
@app.route("/add_friend", methods=["POST"])
def add_friend():
    d = request.get_json()
    user = session.get("user")
    friend = d["friend"]

    conn = db()
    cur = conn.cursor()
    cur.execute("INSERT INTO friends (user1,user2) VALUES (%s,%s)", (user, friend))
    conn.commit()

    return jsonify({"success": True})

@app.route("/friends")
def get_friends():
    user = session.get("user")
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT user2 FROM friends WHERE user1=%s", (user,))
    return jsonify(cur.fetchall())

# -------- IMAGE --------
@app.route("/image", methods=["POST"])
def image():
    prompt = request.get_json()["prompt"]
    img = client.images.generate(model="gpt-image-1", prompt=prompt, size="512x512")
    return jsonify({"url": img.data[0].url})

# -------- EXPORT --------
@app.route("/export/<room>")
def export(room):
    filename = f"{room}.pdf"

    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT user_name,message,reply FROM chats WHERE room=%s", (room,))
    rows = cur.fetchall()

    doc = SimpleDocTemplate(filename)
    styles = getSampleStyleSheet()

    content = []
    for r in rows:
        content.append(Paragraph(f"{r[0]}: {r[1]}", styles["Normal"]))
        content.append(Paragraph(f"BenAI: {r[2]}", styles["Normal"]))

    doc.build(content)

    return send_file(filename, as_attachment=True)

# -------- PORT FIX --------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
