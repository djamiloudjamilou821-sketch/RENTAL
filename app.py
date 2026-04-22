from flask import Flask, render_template, request, redirect, session
import sqlite3
from datetime import datetime, timedelta
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.secret_key = "secret123"

WEEKLY_FEE = 1000

ADMIN_PASSWORD = "1234"

def check_admin_password(password):
    return password == ADMIN_PASSWORD
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
            witness TEXT,
            start_date TEXT,
            due_date TEXT,
            paid TEXT,
            last_payment_date TEXT   
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
# ================== DASHBOARD ===========
@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/login")

    search = request.args.get("search")
    filter_status = request.args.get("filter")

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    # 🔍 SEARCH FIX
    if search:
        c.execute("""
            SELECT * FROM renters
            WHERE name LIKE ? OR phone LIKE ? OR address LIKE ?
        """, (f"%{search}%", f"%{search}%", f"%{search}%"))
    else:
        c.execute("SELECT * FROM renters")

    renters = c.fetchall()
    conn.close()

    updated_renters = []
    today = datetime.now().date()

    paid_count = 0
    overdue_count = 0
    not_paid_count = 0

    for r in renters:
        start_date = datetime.strptime(r[5], "%Y-%m-%d").date()

        days_passed = (today - start_date).days
        weeks_passed = days_passed // 7

        current_due = start_date + timedelta(days=(weeks_passed + 1) * 7)

        # 💳 last payment from DB
        conn = sqlite3.connect("database.db")
        c = conn.cursor()

        c.execute("""
            SELECT payment_date FROM payments
            WHERE renter_id=?
            ORDER BY payment_date DESC LIMIT 1
        """, (r[0],))

        last = c.fetchone()
        conn.close()

        last_payment_date = None
        if last:
            last_payment_date = datetime.strptime(last[0], "%Y-%m-%d").date()

        cycle_start = current_due - timedelta(days=7)

        # 🧠 STATUS LOGIC
        if last_payment_date and cycle_start <= last_payment_date <= current_due:
            status = "Paid"
            paid_count += 1

        elif today > current_due:
            status = f"LATE by {(today - current_due).days} days"
            overdue_count += 1

        elif today == current_due:
            status = "DUE TODAY"
            not_paid_count += 1

        else:
            status = f"Due in {(current_due - today).days} days"
            not_paid_count += 1

        # 🔍 FILTER FIX
        if filter_status:
            if filter_status == "paid" and status != "Paid":
                continue
            if filter_status == "notpaid" and status == "Paid":
                continue
            if filter_status == "overdue" and "LATE" not in status:
                continue

        updated_renters.append(r + (current_due.strftime("%Y-%m-%d"), status))

    return render_template(
        "index.html",
        renters=updated_renters,
        total=len(renters),
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

        # ✅ define start here
        start = datetime.now()
        due = start + timedelta(days=7)

        conn = sqlite3.connect("database.db")
        c = conn.cursor()

        c.execute("""
            INSERT INTO renters (name, phone, address, barrow, start_date, due_date, paid, last_payment_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            name,
            phone,
            address,
            barrow,
            start.strftime("%Y-%m-%d"),
            due.strftime("%Y-%m-%d"),
            None,
            None
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

        password = request.form.get("password")

        if not check_admin_password(password):
            return "❌ Wrong admin password"

        name = request.form["name"]
        phone = request.form["phone"]
        address = request.form["address"]
        witness = request.form["witness"]

        c.execute("""
            UPDATE renters
            SET name=?, phone=?, address=?, witness=?
            WHERE id=?
        """, (name, phone, address, witness, id))

        conn.commit()
        conn.close()
        return redirect("/dashboard")
    c.execute("SELECT * FROM renters WHERE id=?", (id,))
    renter = c.fetchone()
    conn.close()

    return render_template("edit.html", renter=renter)

# ================= DELETE =================
@app.route("/delete/<int:id>", methods=["GET", "POST"])
def delete(id):
    if "user" not in session:
        return redirect("/login")

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    if request.method == "POST":

        password = request.form.get("password")

        if not check_admin_password(password):
            conn.close()
            return "❌ Wrong admin password"

        c.execute("DELETE FROM renters WHERE id=?", (id,))
        conn.commit()
        conn.close()

        return redirect("/renters")

    conn.close()
    return render_template("confirm_delete.html", id=id)

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

    updated = []
    today = datetime.now().date()

    for r in renters:
        start_date = datetime.strptime(r[5], "%Y-%m-%d").date()

        days_passed = (today - start_date).days
        weeks_passed = days_passed // 7

        current_due = start_date + timedelta(days=(weeks_passed + 1) * 7)

        last_payment_date = r[8]

        if last_payment_date:
            last_payment_date = datetime.strptime(last_payment_date, "%Y-%m-%d").date()

        if last_payment_date and last_payment_date >= current_due - timedelta(days=7):
            status = "Paid"
        elif today > current_due:
            status = "LATE"
        else:
            status = "Pending"

        updated.append(r + (status,))

    return render_template("renters.html", renters=updated)
# ============ PROFILE ==================
@app.route("/renter/<int:id>")
def renter_profile(id):
    if "user" not in session:
        return redirect("/login")

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    # 👤 renter info
    c.execute("SELECT * FROM renters WHERE id=?", (id,))
    renter = c.fetchone()

    # 💳 payment history
    c.execute("""
        SELECT amount, payment_date
        FROM payments
        WHERE renter_id=?
        ORDER BY payment_date DESC
    """, (id,))
    payments = c.fetchall()

    # 📊 total paid
    total_paid = sum([int(p[0]) for p in payments]) if payments else 0

    # 🔢 number of payments
    total_payments = len(payments)

    # 🕓 last payment
    last_payment = payments[0][1] if payments else None

    conn.close()

    return render_template(
        "renter.html",
        renter=renter,
        payments=payments,
        total_paid=total_paid,
        total_payments=total_payments,
        last_payment=last_payment
    )  
# ================= PAYMENT =================
@app.route("/pay/<int:id>", methods=["GET", "POST"])
def pay(id):
    if "user" not in session:
        return redirect("/login")

    import sqlite3
    from datetime import datetime, timedelta

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    # 🔹 Get renter
    c.execute("SELECT * FROM renters WHERE id=?", (id,))
    renter = c.fetchone()

    if not renter:
        conn.close()
        return "Renter not found"

    today = datetime.now().date()

    # 🔹 Start date
    start_date = datetime.strptime(renter[5], "%Y-%m-%d").date()

    # 🔹 Weeks passed
    weeks_passed = (today - start_date).days // 7

    # 🔹 Get all payments
    c.execute("SELECT amount, payment_date FROM payments WHERE renter_id=?", (id,))
    payments = c.fetchall()

    # 🔹 Total paid
    total_paid = sum(int(p[0]) for p in payments) if payments else 0

    # 🔹 Expected amount
    expected = (weeks_passed + 1) * WEEKLY_FEE

    # 🔹 Debt
    debt = expected - total_paid

    # 🔹 Current week range (Monday → Sunday)
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)

    c.execute("""
        SELECT * FROM payments
        WHERE renter_id=? AND payment_date BETWEEN ? AND ?
    """, (
        id,
        week_start.strftime("%Y-%m-%d"),
        week_end.strftime("%Y-%m-%d")
    ))

    already_paid = c.fetchone()

    # =========================
    # 💳 HANDLE PAYMENT
    # =========================
    if request.method == "POST":

        # 🔐 Admin password
        password = request.form.get("password")

        if not check_admin_password(password):
            conn.close()
            return "❌ Wrong admin password"

        # 🚫 Block if NO debt and already paid this week
        if debt <= 0 and already_paid:
            conn.close()
            return render_template(
                "pay.html",
                renter_id=id,
                already_paid=True,
                debt=debt
            )

        amount = WEEKLY_FEE
        payment_date = today.strftime("%Y-%m-%d")

        # 💳 Save payment
        c.execute("""
            INSERT INTO payments (renter_id, amount, payment_date)
            VALUES (?, ?, ?)
        """, (id, amount, payment_date))

        # 🔥 Update last payment date
        c.execute("""
            UPDATE renters
            SET last_payment_date=?
            WHERE id=?
        """, (payment_date, id))

        conn.commit()
        conn.close()

        return redirect("/dashboard")

    # =========================
    # 📄 SHOW PAGE
    # =========================
    conn.close()
    return render_template(
        "pay.html",
        renter_id=id,
        already_paid=already_paid,
        debt=debt
    )
# ================= MONEY =================
@app.route("/money")
def money():
    if "user" not in session:
        return redirect("/login")

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    # 👥 renters
    c.execute("SELECT * FROM renters")
    renters = c.fetchall()

    total_renters = len(renters)

    # 💳 payments
    c.execute("SELECT renter_id, amount, payment_date FROM payments")
    payments = c.fetchall()

    today = datetime.now().date()

    paid_renters = 0
    overdue_renters = 0

    weekly_fee = 1000

    # 🔥 loop renters for real status
    for r in renters:
        start_date = datetime.strptime(r[5], "%Y-%m-%d").date()

        days_passed = (today - start_date).days
        weeks_passed = days_passed // 7

        current_due = start_date + timedelta(days=(weeks_passed + 1) * 7)

        # get last payment for this renter
        c.execute("""
            SELECT payment_date FROM payments
            WHERE renter_id=?
            ORDER BY payment_date DESC LIMIT 1
        """, (r[0],))
        last = c.fetchone()

        last_payment_date = None
        if last:
            last_payment_date = datetime.strptime(last[0], "%Y-%m-%d").date()

        if last_payment_date and last_payment_date >= current_due - timedelta(days=7):
            paid_renters += 1
        elif today > current_due:
            overdue_renters += 1

    unpaid_renters = total_renters - paid_renters

    # 💰 collected money = 
    collected_money = 0

    for r in renters:
        start_date = datetime.strptime(r[5], "%Y-%m-%d").date()

        days_passed = (today - start_date).days
        weeks_passed = days_passed // 7

        current_due = start_date + timedelta(days=(weeks_passed + 1) * 7)
        cycle_start = current_due - timedelta(days=7)

        # get last payment
        c.execute("""
            SELECT amount, payment_date FROM payments
            WHERE renter_id=?
            ORDER BY payment_date DESC LIMIT 1
        """, (r[0],))
        last = c.fetchone()

        if last:
            payment_amount = int(last[0])
            payment_date = datetime.strptime(last[1], "%Y-%m-%d").date()

            # only count if payment is in THIS WEEK
            if cycle_start <= payment_date <= current_due:
                collected_money += payment_amount

    expected_money = total_renters * weekly_fee

    conn.close()

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
#================== OFFLINE =================
@app.route("/offline")
def offline():
    return render_template("offline.html")
#================ ADMIN PASSWORD =============
@app.route("/change-admin-password", methods=["GET", "POST"])
def change_admin_password():
    if "user" not in session:
        return redirect("/login")

    global ADMIN_PASSWORD

    if request.method == "POST":
        old = request.form["old_password"]
        new = request.form["new_password"]

        if old != ADMIN_PASSWORD:
            return "❌ Wrong current admin password"

        ADMIN_PASSWORD = new
        return "✅ Admin password changed successfully"

    return render_template("change_admin_password.html") 
#=============== TIMELINE ==============
@app.route("/renter-timeline/<int:id>")
def renter_timeline(id):
    if "user" not in session:
        return redirect("/login")

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    # Get renter info
    c.execute("SELECT * FROM renters WHERE id=?", (id,))
    renter = c.fetchone()

    start_date = datetime.strptime(renter[5], "%Y-%m-%d").date()
    today = datetime.now().date()

    weeks_passed = (today - start_date).days // 7

    # Get all payments
    c.execute("""
        SELECT amount, payment_date FROM payments
        WHERE renter_id=?
        ORDER BY payment_date ASC
    """, (id,))

    payments = c.fetchall()

    timeline = []

    paid_total = 0

    for week in range(weeks_passed + 1):
        week_start = start_date + timedelta(days=week * 7)
        week_end = week_start + timedelta(days=7)

        week_paid = 0

        for p in payments:
            pay_date = datetime.strptime(p[1], "%Y-%m-%d").date()

            if week_start <= pay_date < week_end:
                week_paid += int(p[0])

        if week_paid >= WEEKLY_FEE:
            status = "PAID"
        else:
            status = "DEBT"

        timeline.append({
            "week": week + 1,
            "start": week_start,
            "status": status,
            "paid": week_paid
        })

    conn.close()

    return render_template("timeline.html", renter=renter, timeline=timeline)  
# ================= RUN =================
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")