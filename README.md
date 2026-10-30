# Library Management System

A beginner-friendly Library Management System built with Python Flask, SQLite, HTML and CSS.

## Features
- Student registration and login
- Admin login
- Browse and search books by title, author or category
- Admin can add and delete books
- Students can borrow available books
- 14-day borrowing period
- Admin can process book returns
- Automatic late fine calculation (₹5 per overdue day)
- Student borrowing history and admin dashboard

## Requirements
- Python 3.9 or later
- pip

## Run on Windows
1. Extract this ZIP file.
2. Open Command Prompt or VS Code terminal in the project folder.
3. Create a virtual environment: `python -m venv venv`
4. Activate it: `venv\\Scripts\\activate`
5. Install dependencies: `pip install -r requirements.txt`
6. Start the app: `python app.py`
7. Visit `http://127.0.0.1:5000`

The SQLite database `library.db` is created automatically.

## Admin account
Email: `admin@library.local`
Password: `Admin@123`

Change the default admin password, Flask secret key, and debug settings before public deployment.

## Main structure
```
library_management_system/
|-- app.py
|-- requirements.txt
|-- README.md
|-- templates/
|   |-- base.html
|   |-- index.html
|   |-- login.html
|   |-- register.html
|   |-- books.html
|   |-- dashboard.html
|   |-- admin.html
|-- static/
    |-- style.css
```

This is an academic starter project. It does not include production deployment hardening, email delivery, payment collection, or barcode integration.
