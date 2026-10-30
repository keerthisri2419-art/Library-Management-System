from flask import Flask, render_template, request, redirect, url_for, flash, session
import sqlite3
from functools import wraps
from datetime import date, datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "replace-this-secret-key-before-deployment"
DB = "library.db"
FINE_PER_DAY = 5

def get_db():
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    return db

def init_db():
    with get_db() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'student'
        );
        CREATE TABLE IF NOT EXISTS books(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            author TEXT NOT NULL,
            category TEXT NOT NULL,
            isbn TEXT,
            quantity INTEGER NOT NULL DEFAULT 1,
            available INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS loans(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            book_id INTEGER NOT NULL,
            issue_date TEXT NOT NULL,
            due_date TEXT NOT NULL,
            return_date TEXT,
            fine REAL NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'Issued',
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(book_id) REFERENCES books(id)
        );
        """)
        admin = db.execute("SELECT id FROM users WHERE email=?", ("admin@library.local",)).fetchone()
        if not admin:
            db.execute("INSERT INTO users(name,email,password,role) VALUES(?,?,?,?)",
                       ("Library Admin", "admin@library.local",
                        generate_password_hash("Admin@123"), "admin"))
        count = db.execute("SELECT COUNT(*) FROM books").fetchone()[0]
        if count == 0:
            sample = [
                ("The Alchemist", "Paulo Coelho", "Fiction", "9780061122415", 5, 5),
                ("Wings of Fire", "A. P. J. Abdul Kalam", "Biography", "9788173711466", 4, 4),
                ("Clean Code", "Robert C. Martin", "Technology", "9780132350884", 3, 3),
                ("Introduction to Algorithms", "Thomas H. Cormen", "Technology", "9780262046305", 2, 2),
                ("Ponniyin Selvan", "Kalki Krishnamurthy", "Tamil Literature", "9788177200128", 3, 3),
            ]
            db.executemany("""INSERT INTO books(title,author,category,isbn,quantity,available)
                              VALUES(?,?,?,?,?,?)""", sample)

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

def admin_required(fn):
    @wraps(fn)
    @login_required
    def wrapper(*args, **kwargs):
        if session.get("role") != "admin":
            flash("Admin access required.", "danger")
            return redirect(url_for("dashboard"))
        return fn(*args, **kwargs)
    return wrapper

@app.route("/")
def index():
    with get_db() as db:
        stats = {
            "books": db.execute("SELECT COALESCE(SUM(quantity),0) FROM books").fetchone()[0],
            "available": db.execute("SELECT COALESCE(SUM(available),0) FROM books").fetchone()[0],
            "students": db.execute("SELECT COUNT(*) FROM users WHERE role='student'").fetchone()[0],
            "issued": db.execute("SELECT COUNT(*) FROM loans WHERE status='Issued'").fetchone()[0]
        }
        books = db.execute("SELECT * FROM books ORDER BY id DESC LIMIT 4").fetchall()
    return render_template("index.html", stats=stats, books=books)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not name or not email or len(password) < 6:
            flash("Complete all fields. Password must be at least 6 characters.", "danger")
        else:
            try:
                with get_db() as db:
                    db.execute("INSERT INTO users(name,email,password) VALUES(?,?,?)",
                               (name, email, generate_password_hash(password)))
                flash("Registration successful. Please log in.", "success")
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                flash("This email is already registered.", "danger")
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        with get_db() as db:
            user = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if user and check_password_hash(user["password"], password):
            session.update(user_id=user["id"], name=user["name"], role=user["role"])
            flash("Login successful.", "success")
            return redirect(url_for("admin") if user["role"] == "admin" else url_for("dashboard"))
        flash("Invalid email or password.", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))

@app.route("/books")
def books():
    q = request.args.get("q", "").strip()
    with get_db() as db:
        rows = db.execute("""SELECT * FROM books
            WHERE title LIKE ? OR author LIKE ? OR category LIKE ?
            ORDER BY title""", (f"%{q}%", f"%{q}%", f"%{q}%")).fetchall()
    return render_template("books.html", books=rows, q=q)

@app.route("/dashboard")
@login_required
def dashboard():
    with get_db() as db:
        loans = db.execute("""SELECT loans.*, books.title, books.author
            FROM loans JOIN books ON books.id=loans.book_id
            WHERE loans.user_id=? ORDER BY loans.id DESC""", (session["user_id"],)).fetchall()
    return render_template("dashboard.html", loans=loans)

@app.route("/issue/<int:book_id>", methods=["POST"])
@login_required
def issue_book(book_id):
    if session.get("role") == "admin":
        flash("Use a student account to borrow books.", "warning")
        return redirect(url_for("books"))
    with get_db() as db:
        book = db.execute("SELECT * FROM books WHERE id=?", (book_id,)).fetchone()
        active = db.execute("SELECT COUNT(*) FROM loans WHERE user_id=? AND status='Issued'",
                            (session["user_id"],)).fetchone()[0]
        if not book:
            flash("Book not found.", "danger")
        elif book["available"] < 1:
            flash("This book is currently unavailable.", "warning")
        elif active >= 3:
            flash("You can have a maximum of 3 active books.", "warning")
        else:
            today = date.today()
            due = today + timedelta(days=14)
            db.execute("INSERT INTO loans(user_id,book_id,issue_date,due_date) VALUES(?,?,?,?)",
                       (session["user_id"], book_id, today.isoformat(), due.isoformat()))
            db.execute("UPDATE books SET available=available-1 WHERE id=?", (book_id,))
            flash(f"Book issued successfully. Due date: {due.isoformat()}", "success")
    return redirect(url_for("dashboard") if session.get("user_id") else url_for("books"))

@app.route("/admin")
@admin_required
def admin():
    with get_db() as db:
        stats = {
            "books": db.execute("SELECT COALESCE(SUM(quantity),0) FROM books").fetchone()[0],
            "available": db.execute("SELECT COALESCE(SUM(available),0) FROM books").fetchone()[0],
            "students": db.execute("SELECT COUNT(*) FROM users WHERE role='student'").fetchone()[0],
            "issued": db.execute("SELECT COUNT(*) FROM loans WHERE status='Issued'").fetchone()[0]
        }
        loans = db.execute("""SELECT loans.*, users.name AS student, users.email,
            books.title FROM loans JOIN users ON users.id=loans.user_id
            JOIN books ON books.id=loans.book_id ORDER BY loans.id DESC""").fetchall()
        book_rows = db.execute("SELECT * FROM books ORDER BY id DESC").fetchall()
    return render_template("admin.html", stats=stats, loans=loans, books=book_rows)

@app.route("/admin/books/add", methods=["POST"])
@admin_required
def add_book():
    title = request.form.get("title", "").strip()
    author = request.form.get("author", "").strip()
    category = request.form.get("category", "").strip()
    isbn = request.form.get("isbn", "").strip()
    quantity = request.form.get("quantity", type=int)
    if not title or not author or not category or not quantity or quantity < 1:
        flash("Enter valid book details and quantity.", "danger")
    else:
        with get_db() as db:
            db.execute("""INSERT INTO books(title,author,category,isbn,quantity,available)
                          VALUES(?,?,?,?,?,?)""", (title, author, category, isbn, quantity, quantity))
        flash("Book added successfully.", "success")
    return redirect(url_for("admin"))

@app.route("/admin/books/delete/<int:book_id>", methods=["POST"])
@admin_required
def delete_book(book_id):
    with get_db() as db:
        active = db.execute("SELECT COUNT(*) FROM loans WHERE book_id=? AND status='Issued'",
                            (book_id,)).fetchone()[0]
        if active:
            flash("Cannot delete a book while copies are issued.", "danger")
        else:
            db.execute("DELETE FROM books WHERE id=?", (book_id,))
            flash("Book deleted.", "success")
    return redirect(url_for("admin"))

@app.route("/admin/return/<int:loan_id>", methods=["POST"])
@admin_required
def return_book(loan_id):
    with get_db() as db:
        loan = db.execute("SELECT * FROM loans WHERE id=? AND status='Issued'", (loan_id,)).fetchone()
        if loan:
            today = date.today()
            due = date.fromisoformat(loan["due_date"])
            fine = max(0, (today - due).days) * FINE_PER_DAY
            db.execute("""UPDATE loans SET status='Returned', return_date=?, fine=?
                          WHERE id=?""", (today.isoformat(), fine, loan_id))
            db.execute("UPDATE books SET available=available+1 WHERE id=?", (loan["book_id"],))
            flash(f"Book returned. Fine: ₹{fine:.2f}", "success")
        else:
            flash("Active loan not found.", "danger")
    return redirect(url_for("admin"))

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
