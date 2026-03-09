from flask import Flask, render_template, request, redirect, session, jsonify
import sqlite3
import csv
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = "agridirect_secret"

UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


def get_db():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        password TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS inventory(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        crop_name TEXT,
        quantity INTEGER,
        farmer TEXT,
        date_received TEXT
    )
    """)

    conn.commit()
    conn.close()


@app.route("/")
def home():
    if "user" in session:
        return redirect("/dashboard")
    return redirect("/login")


# ---------------- LOGIN ----------------

@app.route("/login", methods=["GET","POST"])
def login():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        conn = get_db()
        cur = conn.cursor()

        cur.execute("SELECT * FROM users WHERE username=? AND password=?",
                    (username,password))

        user = cur.fetchone()

        if user:
            session["user"] = username
            return redirect("/dashboard")

    return render_template("login.html")


# ---------------- REGISTER ----------------

@app.route("/register", methods=["GET","POST"])
def register():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        conn = get_db()
        cur = conn.cursor()

        cur.execute("INSERT INTO users(username,password) VALUES (?,?)",
                    (username,password))

        conn.commit()
        conn.close()

        return redirect("/login")

    return render_template("register.html")


# ---------------- DASHBOARD ----------------

@app.route("/dashboard")
def dashboard():

    if "user" not in session:
        return redirect("/login")

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM inventory")
    data = cur.fetchall()

    cur.execute("SELECT SUM(quantity) FROM inventory")
    total = cur.fetchone()[0]

    conn.close()

    return render_template("dashboard.html",
                           inventory=data,
                           total=total)


# ---------------- CSV UPLOAD ----------------

@app.route("/upload", methods=["GET","POST"])
def upload():

    if "user" not in session:
        return redirect("/login")

    if request.method == "POST":

        file = request.files["file"]

        path = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
        file.save(path)

        with open(path) as csvfile:

            reader = csv.DictReader(csvfile)

            conn = get_db()
            cur = conn.cursor()

            for row in reader:

                cur.execute("""
                INSERT INTO inventory(crop_name,quantity,farmer,date_received)
                VALUES(?,?,?,?)
                """,(
                    row["crop_name"],
                    row["quantity"],
                    session["user"],
                    datetime.now()
                ))

            conn.commit()
            conn.close()

        return redirect("/dashboard")

    return render_template("upload.html")


# ---------------- REST API ----------------

@app.route("/api/harvest", methods=["POST"])
def api_harvest():

    data = request.json

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO inventory(crop_name,quantity,farmer,date_received)
    VALUES(?,?,?,?)
    """,(
        data["crop_name"],
        data["quantity"],
        data["farmer"],
        datetime.now()
    ))

    conn.commit()
    conn.close()

    return jsonify({"status":"harvest recorded"})


# ---------------- LOGOUT ----------------

@app.route("/logout")
def logout():

    session.pop("user",None)
    return redirect("/login")


if __name__ == "__main__":
    init_db()
    app.run(debug=True)