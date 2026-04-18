from flask import Flask, render_template, request, redirect, session
import sqlite3
from datetime import datetime, timedelta
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.secret_key = "secret123"

# ================= DATABASE =================
def init_db():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS renters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            phone TEXT,
            address TEXT,
            barrow TEXT,
            start_date TEXT,
            due_date TEXT,
            paid TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            renter_id INTEGER,
            amount TEXT,
            payment_date TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT
        )
    """)

    # create admin if not exists
    c.execute("SELECT * FROM users WHERE username=?", ("admin",))
    if not c.fetchone():
        hashed = generate_password_hash("1234")
        c.execute("INSERT INTO users (username, password) VALUES (?, ?)", ("admin", hashed))

    conn.commit()
    conn.close()

init_db()

# ================= ROOT =================
@app.route("/")
def root():
    return redirect("/login")

# ================= LOGIN =================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = sqlite3.connect("database.db")
        c = conn.cursor()

        c.execute("SELECT * FROM users WHERE username=?", (username,))
        user = c.fetchone()
        conn.close()

        if user and check_password_hash(user[2], password):
            session["user"] = username
            return redirect("/home")
        else:
            return "❌ Invalid credentials"

    return render_template("login.html")

# ================= LOGOUT =================
@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect("/login")

# ================= HOME =================
@app.route("/home")
def home():
    if "user" not in session:
        return redirect("/login")
    return render_template("home.html")

# ================= DASHBOARD =================
@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/login")

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    search = request.args.get("search")
    filter_status = request.args.get("filter")

    query = "SELECT * FROM renters"
    params = []

    if search:
        query += " WHERE name LIKE ? OR phone LIKE ? OR address LIKE ?"
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])

    c.execute(query, params)
    renters = c.fetchall()
    conn.close()

    updated_renters = []
    today = datetime.now().date()

    total = len(renters)
    paid_count = 0
    overdue_count = 0
    not_paid_count = 0

    for r in renters:
        start_date = datetime.strptime(r[5], "%Y-%m-%d").date()

        days_passed = (today - start_date).days
        weeks_passed = days_passed // 7

        current_due = start_date + timedelta(days=(weeks_passed + 1) * 7)
        days_left = (current_due - today).days

        if r[7] == "Paid":
            status = "Paid"
            paid_count += 1

        elif days_left < 0:
            status = f"LATE by {abs(days_left)} days"
            overdue_count += 1

        elif days_left == 0:
            status = "DUE TODAY"
            not_paid_count += 1

        else:
            status = f"Due in {days_left} days"
            not_paid_count += 1

        if filter_status:
            if filter_status == "paid" and status != "Paid":
                continue
            if filter_status == "notpaid" and r[7] == "Paid":
                continue
            if filter_status == "overdue" and "LATE" not in status:
                continue

        updated_renters.append(r + (current_due.strftime("%Y-%m-%d"), status))

    return render_template(
        "index.html",
        renters=updated_renters,
        total=total,
        paid=paid_count,
        overdue=overdue_count,
        not_paid=not_paid_count
    )

# ================= ADD =================
@app.route("/add", methods=["GET", "POST"])
def add():
    if "user" not in session:
        return redirect("/login")

    if request.method == "POST":
        name = request.form["name"]
        phone = request.form["phone"]
        address = request.form["address"]
        barrow = request.form["barrow"]
        paid = request.form["paid"]

        start_date = datetime.now()
        due_date = start_date + timedelta(days=7)

        conn = sqlite3.connect("database.db")
        c = conn.cursor()

        c.execute("""
            INSERT INTO renters (name, phone, address, barrow, start_date, due_date, paid)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            name, phone, address, barrow,
            start_date.strftime("%Y-%m-%d"),
            due_date.strftime("%Y-%m-%d"),
            paid
        ))

        conn.commit()
        conn.close()

        return redirect("/dashboard")

    return render_template("add.html")

# ================= EDIT =================
@app.route("/edit/<int:id>", methods=["GET", "POST"])
def edit(id):
    if "user" not in session:
        return redirect("/login")

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    if request.method == "POST":
        name = request.form["name"]
        phone = request.form["phone"]
        address = request.form["address"]
        barrow = request.form["barrow"]
        paid = request.form["paid"]

        c.execute("""
            UPDATE renters
            SET name=?, phone=?, address=?, barrow=?, paid=?
            WHERE id=?
        """, (name, phone, address, barrow, paid, id))

        conn.commit()
        conn.close()
        return redirect("/dashboard")

    c.execute("SELECT * FROM renters WHERE id=?", (id,))
    renter = c.fetchone()
    conn.close()

    return render_template("edit.html", renter=renter)

# ================= DELETE =================
@app.route("/delete/<int:id>")
def delete(id):
    if "user" not in session:
        return redirect("/login")

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute("DELETE FROM renters WHERE id=?", (id,))

    conn.commit()
    conn.close()

    return redirect("/dashboard")

# ================= RENTERS =================
@app.route("/renters")
def renters_page():
    if "user" not in session:
        return redirect("/login")

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute("SELECT * FROM renters")
    renters = c.fetchall()

    conn.close()

    return render_template("renters.html", renters=renters)
# ============ PROFILE ==================
@app.route("/renter/<int:id>")
def renter_profile(id):
    if "user" not in session:
        return redirect("/login")

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute("SELECT * FROM renters WHERE id=?", (id,))
    renter = c.fetchone()

    conn.close()

    return render_template("renter.html", renter=renter)    
# ================= PAYMENT =================
@app.route("/pay/<int:id>", methods=["GET", "POST"])
def pay(id):
    if "user" not in session:
        return redirect("/login")

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    if request.method == "POST":
        amount = request.form["amount"]
        payment_date = datetime.now().strftime("%Y-%m-%d")

        c.execute("""
            INSERT INTO payments (renter_id, amount, payment_date)
            VALUES (?, ?, ?)
        """, (id, amount, payment_date))

        c.execute("UPDATE renters SET paid='Paid' WHERE id=?", (id,))

        conn.commit()
        conn.close()
        return redirect("/dashboard")

    conn.close()
    return render_template("pay.html", renter_id=id)

# ================= MONEY =================
@app.route("/money")
def money():
    if "user" not in session:
        return redirect("/login")

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute("SELECT * FROM renters")
    renters = c.fetchall()
    conn.close()

    total_renters = len(renters)
    weekly_fee = 1000

    paid_renters = len([r for r in renters if r[7] == "Paid"])
    unpaid_renters = total_renters - paid_renters

    expected_money = total_renters * weekly_fee
    collected_money = paid_renters * weekly_fee

    return render_template(
        "money.html",
        total_renters=total_renters,
        paid_renters=paid_renters,
        unpaid_renters=unpaid_renters,
        weekly_fee=weekly_fee,
        expected_money=expected_money,
        collected_money=collected_money
    )

# ================= VERIFY USER (STEP 1) =================
@app.route("/verify-user", methods=["GET", "POST"])
def verify_user():
    if "user" not in session:
        return redirect("/login")

    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]

        if password != confirm_password:
            return "❌ Passwords do not match"

        conn = sqlite3.connect("database.db")
        c = conn.cursor()

        c.execute("SELECT password FROM users WHERE username=?", (username,))
        user = c.fetchone()
        conn.close()

        if user and check_password_hash(user[0], password):
            session["verify_user"] = username
            return redirect("/new-password")
        else:
            return "❌ Incorrect username or password"

    return render_template("verify_user.html")

# ================= NEW PASSWORD (STEP 2) =================
@app.route("/new-password", methods=["GET", "POST"])
def new_password():
    if "verify_user" not in session:
        return redirect("/verify-user")

    if request.method == "POST":
        new_password = request.form["new_password"]
        confirm_password = request.form["confirm_password"]

        if new_password != confirm_password:
            return "❌ New passwords do not match"

        conn = sqlite3.connect("database.db")
        c = conn.cursor()

        hashed = generate_password_hash(new_password)

        c.execute("UPDATE users SET password=? WHERE username=?", (hashed, session["verify_user"]))

        conn.commit()
        conn.close()

        session.pop("verify_user", None)

        return "✅ Password changed successfully"

    return render_template("new_password.html")

# ================= RUN =================
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")