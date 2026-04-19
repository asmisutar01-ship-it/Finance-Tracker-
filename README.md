# 💰 Finance Tracker

A full-stack personal finance management web app built with Flask and MongoDB. This application helps users track expenses, manage income, calculate taxes, and securely handle authentication with OTP verification.

---

## 🚀 Features

### 🔐 Authentication System

* User signup & login
* Email OTP verification (Flask-Mail)
* Forgot password with OTP reset
* Secure session handling

### 📊 Finance Management

* Add income & expenses
* Categorize transactions
* View financial summary

### 🧮 Tax Calculator

* Calculates tax based on user inputs
* Supports:

  * Income
  * Deductions
  * Insurance (health/life)
  * Loan interest (with smart input parsing)

### 🛠 Admin Dashboard (WIP)

* Planned interactive dashboard for admin-only access

---

## 🏗 Tech Stack

* **Backend:** Flask (Python)
* **Database:** MongoDB (PyMongo)
* **Frontend:** HTML, CSS, Jinja2
* **Email Service:** Flask-Mail
* **Version Control:** Git & GitHub

---

## 📂 Project Structure

```
app/
 ├── app.py
 ├── models.py
 ├── routes.py
 ├── utils/
 │    ├── helpers.py
 │    ├── tax.py
 ├── templates/
 │    ├── base.html
 │    ├── login.html
 │    ├── tax.html
 │    ├── verify_otp.html
 │    └── ...
```

## 📄 License

This project is open-source and available under the MIT License.

---

## 👨‍💻 Author

**Asmi Sutar**

---

⭐ If you like this project, consider giving it a star!
