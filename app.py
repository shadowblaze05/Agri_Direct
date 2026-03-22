from flask import Flask, render_template, request, redirect, session, jsonify, flash
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import sqlite3
import csv
import os
import logging
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "agridirect_secret")

UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

API_KEY = os.environ.get("API_KEY", "mysecurekey123")

# Ensure upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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
        username TEXT UNIQUE,
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

    # Insert default user if not exists
    cur.execute("SELECT * FROM users WHERE username=?", ("admin",))
    if not cur.fetchone():
        cur.execute("INSERT INTO users(username,password) VALUES (?,?)",
                    ("admin", generate_password_hash("admin")))

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

        cur.execute("SELECT * FROM users WHERE username=?", (username,))
        user = cur.fetchone()

        if user:
            if check_password_hash(user["password"], password):
                session["user"] = username
                logger.info(f"User {username} logged in")
                return redirect("/dashboard")
            else:
                logger.warning(f"Invalid password for {username}")
        else:
            logger.warning(f"User {username} not found")

        flash("Invalid username or password")

    return render_template("login.html")


# ---------------- REGISTER ----------------

@app.route("/register", methods=["GET","POST"])
def register():

    if request.method == "POST":

        username = request.form["username"]
        password = generate_password_hash(request.form["password"])

        conn = get_db()
        cur = conn.cursor()

        try:
            cur.execute("INSERT INTO users(username,password) VALUES (?,?)",
                        (username,password))
            conn.commit()
            logger.info(f"User {username} registered")
            flash("Registration successful! Please login.")
            return redirect("/login")
        except sqlite3.IntegrityError:
            flash("Username already exists")
            logger.warning(f"Registration failed: username {username} already exists")
        finally:
            conn.close()

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

    cur.execute("""SELECT crop_name, SUM(quantity) as total FROM inventory GROUP BY crop_name""")
    crops = cur.fetchall()

    conn.close()

    total = sum(row['quantity'] for row in data)

    return render_template("dashboard.html",
                       inventory=data,
                       total=total,
                       crops=crops)


# ---------------- CSV UPLOAD ----------------

@app.route("/upload", methods=["GET","POST"])
def upload():

    if "user" not in session:
        return redirect("/login")

    if request.method == "POST":

        file = request.files["file"]

        if file.filename == '':
            flash("No file selected")
            return redirect(request.url)

        if not file.filename.endswith('.csv'):
            flash("Only CSV files are allowed")
            return redirect(request.url)

        filename = secure_filename(file.filename)
        path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(path)

        try:
            with open(path) as csvfile:

                reader = csv.DictReader(csvfile)

                conn = get_db()
                cur = conn.cursor()

                for row in reader:
                    try:
                        crop = row["crop_name"]
                        quantity = int(row["quantity"])

                        if quantity <= 0:
                            continue

                        cur.execute("""
                        INSERT INTO inventory(crop_name,quantity,farmer,date_received)
                        VALUES(?,?,?,?)
                        """, (crop, quantity, session["user"], datetime.now()))

                    except Exception as e:
                        logger.error(f"Error processing row: {row}, {e}")
                        flash(f"Error processing row: {row}")

                conn.commit()
                conn.close()

            flash("Upload successful!")
            logger.info(f"User {session['user']} uploaded {filename}")

        except Exception as e:
            flash(f"Error processing file: {str(e)}")
            logger.error(f"Upload error: {str(e)}")

        return redirect("/dashboard")

    return render_template("upload.html")


# ---------------- REST API ----------------

@app.route("/api/harvest", methods=["POST"])
def api_harvest():

    key = request.headers.get("x-api-key")

    if key != API_KEY:
        return jsonify({"error": "Unauthorized"}), 403

    data = request.json

    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
        INSERT INTO inventory(crop_name,quantity,farmer,date_received)
        VALUES(?,?,?,?)
        """, (
            data["crop_name"],
            int(data["quantity"]),
            data.get("farmer", "API"),
            datetime.now()
        ))

        conn.commit()
        conn.close()

        return jsonify({"status": "harvest recorded"})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------- LOGOUT ----------------

@app.route("/logout")
def logout():

    session.pop("user",None)
    return redirect("/login")


# ---------------- ERROR HANDLERS ----------------

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(e):
    return render_template('500.html'), 500


if __name__ == "__main__":
    init_db()
    app.run(debug=True)