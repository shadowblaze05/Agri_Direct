from flask import Flask, render_template, request, redirect, session, jsonify, flash, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import sqlite3
import csv
import os
import logging
from datetime import datetime, timedelta
import jwt
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "agridirect_secret")

UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

API_KEY = os.environ.get("API_KEY", "mysecurekey123")
JWT_SECRET = os.environ.get("JWT_SECRET", "jwt_secret_key_agridirect")

# Ensure upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============= JWT FUNCTIONS =============

def generate_jwt_token(username):
    """Generate JWT token for API authentication"""
    try:
        payload = {
            "user": username,
            "exp": datetime.utcnow() + timedelta(hours=24),
            "iat": datetime.utcnow()
        }
        token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
        return token
    except Exception as e:
        logger.error(f"Error generating token: {e}")
        return None


def verify_jwt_token(token):
    """Verify JWT token and return username if valid"""
    try:
        if token.startswith("Bearer "):
            token = token[7:]
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload.get("user")
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def token_required(f):
    """Decorator to protect API endpoints with JWT"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("Authorization")
        if not token:
            return jsonify({"error": "Missing authorization token"}), 401
        
        username = verify_jwt_token(token)
        if not username:
            return jsonify({"error": "Invalid or expired token"}), 401
        
        return f(*args, **kwargs)
    return decorated


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

    # Create messages table with recipient column
    cur.execute("""
    CREATE TABLE IF NOT EXISTS messages(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sender TEXT,
        recipient TEXT,
        message TEXT,
        timestamp TEXT
    )
    """)

    # Migration: Add recipient column if it doesn't exist (for existing databases)
    try:
        cur.execute("SELECT recipient FROM messages LIMIT 1")
    except sqlite3.OperationalError:
        # Column doesn't exist, need to migrate
        logger.info("Migrating messages table to add recipient column")
        cur.execute("ALTER TABLE messages ADD COLUMN recipient TEXT")
        # For existing messages, set recipient to a default value or handle appropriately
        # For now, we'll leave existing messages without recipient (they were broadcast messages)

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
                        # Strip whitespace from column names and values to handle formatting issues
                        cleaned_row = {k.strip(): (v.strip() if v else '') for k, v in row.items()}
                        
                        crop = cleaned_row.get("crop_name", "").strip()
                        quantity_str = cleaned_row.get("quantity", "").strip()
                        
                        # Validate required fields
                        if not crop:
                            logger.warning(f"Skipped row with empty crop_name")
                            continue
                        
                        try:
                            quantity = int(quantity_str)
                        except ValueError:
                            logger.error(f"Invalid quantity: {quantity_str}")
                            flash(f"Error: Invalid quantity '{quantity_str}' in row")
                            continue

                        if quantity <= 0:
                            logger.warning(f"Skipped row with non-positive quantity: {quantity}")
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

@app.route("/token", methods=["POST"])
def get_token():
    """Generate JWT token for authenticated users"""
    username = request.form.get("username")
    password = request.form.get("password")
    
    if not username or not password:
        return jsonify({"error": "Missing username or password"}), 400
    
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE username=?", (username,))
    user = cur.fetchone()
    conn.close()
    
    if not user or not check_password_hash(user["password"], password):
        return jsonify({"error": "Invalid credentials"}), 401
    
    token = generate_jwt_token(username)
    if not token:
        return jsonify({"error": "Failed to generate token"}), 500
    
    logger.info(f"Token generated for user {username}")
    return jsonify({"token": token, "expires_in": 86400})


@app.route("/api/harvest", methods=["POST"])
@token_required
def api_harvest():
    """POST harvest data - Protected with JWT"""
    try:
        data = request.json
        
        # Validate input
        if not data.get("crop_name") or not data.get("quantity"):
            return jsonify({"error": "Missing crop_name or quantity"}), 400
        
        try:
            quantity = int(data["quantity"])
            if quantity <= 0:
                return jsonify({"error": "Quantity must be positive"}), 400
        except ValueError:
            return jsonify({"error": "Quantity must be a number"}), 400
        
        token = request.headers.get("Authorization")
        username = verify_jwt_token(token)
        
        conn = get_db()
        cur = conn.cursor()
        
        cur.execute("""
        INSERT INTO inventory(crop_name,quantity,farmer,date_received)
        VALUES(?,?,?,?)
        """, (
            data["crop_name"].strip(),
            quantity,
            data.get("farmer", username),
            datetime.now()
        ))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Harvest recorded via API: {data['crop_name']} x{quantity} by {username}")
        return jsonify({"status": "harvest recorded", "crop": data["crop_name"], "quantity": quantity}), 201
    
    except Exception as e:
        logger.error(f"API Error: {str(e)}")
        return jsonify({"error": str(e)}), 500


# ============= REAL-TIME DATA ENDPOINTS =============

@app.route("/dashboard-data")
def dashboard_data():
    """Return only the inventory table HTML for real-time updates"""
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute("SELECT * FROM inventory ORDER BY date_received DESC LIMIT 50")
    data = cur.fetchall()
    
    conn.close()
    
    return render_template("inventory_table.html", inventory=data)


@app.route("/api/stats")
def api_stats():
    """Get inventory statistics"""
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    conn = get_db()
    cur = conn.cursor()
    
    # Total quantity
    cur.execute("SELECT SUM(quantity) as total FROM inventory")
    total = cur.fetchone()["total"] or 0
    
    # Crop summary
    cur.execute("SELECT crop_name, SUM(quantity) as total FROM inventory GROUP BY crop_name ORDER BY total DESC")
    crops = cur.fetchall()
    
    # Top crop
    top_crop = crops[0]["crop_name"] if crops else "N/A"
    
    # Number of entries
    cur.execute("SELECT COUNT(*) as count FROM inventory")
    entry_count = cur.fetchone()["count"]
    
    conn.close()
    
    return jsonify({
        "total_quantity": total,
        "top_crop": top_crop,
        "crops_count": len(crops),
        "entry_count": entry_count,
        "crops": [{"name": crop["crop_name"], "quantity": crop["total"]} for crop in crops]
    })


# ---------------- CHAT API ----------------

@app.route("/api/users", methods=["GET"])
def get_users():
    """Get list of all users for chat recipient selection"""
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute("SELECT username FROM users WHERE username != ? ORDER BY username", (session["user"],))
    users = cur.fetchall()
    
    conn.close()
    
    users_list = [user["username"] for user in users]
    
    return jsonify(users_list)


@app.route("/api/messages", methods=["GET"])
def get_messages():
    """Get chat messages for current conversation"""
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    recipient = request.args.get("recipient")
    if not recipient:
        return jsonify({"error": "Recipient required"}), 400
    
    current_user = session["user"]
    
    conn = get_db()
    cur = conn.cursor()
    
    # Get messages between current user and recipient (both directions)
    cur.execute("""
        SELECT sender, recipient, message, timestamp 
        FROM messages 
        WHERE (sender = ? AND recipient = ?) OR (sender = ? AND recipient = ?)
        ORDER BY timestamp DESC LIMIT 50
    """, (current_user, recipient, recipient, current_user))
    
    messages = cur.fetchall()
    conn.close()
    
    # Reverse to show oldest first
    messages_list = [{
        "sender": msg["sender"], 
        "recipient": msg["recipient"],
        "message": msg["message"], 
        "timestamp": msg["timestamp"]
    } for msg in reversed(messages)]
    
    return jsonify(messages_list)


@app.route("/api/messages", methods=["POST"])
def send_message():
    """Send a chat message"""
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.json
    message = data.get("message", "").strip()
    recipient = data.get("recipient", "").strip()
    
    if not message:
        return jsonify({"error": "Message cannot be empty"}), 400
    
    if not recipient:
        return jsonify({"error": "Recipient required"}), 400
    
    # Prevent sending messages to self
    if recipient == session["user"]:
        return jsonify({"error": "Cannot send message to yourself"}), 400
    
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute("INSERT INTO messages(sender, recipient, message, timestamp) VALUES (?, ?, ?, ?)",
                (session["user"], recipient, message, datetime.now()))
    
    conn.commit()
    conn.close()
    
    logger.info(f"Message sent from {session['user']} to {recipient}: {message}")
    return jsonify({"status": "success"})


# ---------------- LOGOUT ----------------

@app.route("/logout")
@app.route("/logout/")
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))


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