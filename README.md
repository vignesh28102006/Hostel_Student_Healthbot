# 🏥 Hostel Student Health Bot

A Python CLI application that provides intelligent health advice using **Google Gemini AI**, designed specifically for hostel students.

---

## 🚀 Features

### 🤖 AI-Powered Health Advice

* Integration with Google Gemini AI
* Context-aware responses based on symptoms
* Personalized advice for student lifestyle
* 🚨 Emergency situation detection

---

### 🧠 Symptom Analysis System

* Keyword-based analysis with weighted scoring
* Multi-factor severity assessment
* Pattern recognition for symptom clusters
* Real-time severity calculation

---

### 🗂 Health History Management

* SQLite database for persistent storage
* Timestamped logs with metadata
* Export functionality for medical tracking

---

### 💻 User Interface

* Rich CLI interface with colors and formatting
* Interactive menus and prompts
* Progress indicators and loading animations
* 🚨 Visual severity indicators

---

### 🔐 Security & Configuration

* API key management using `.env`
* Input validation and sanitization
* Secure configuration handling

---

## 🛠 Tech Stack

* Python
* SQLite
* Google Gemini AI
* SQLAlchemy
* Rich (CLI UI)
* JSON

---

## ⚙️ Setup

```bash
pip install -r requirements.txt
```

Create a `.env` file:

```env
GEMINI_API_KEY=your_api_key_here
```

---

## ▶️ Usage

```bash
python health_bot.py
```

---

## 📌 Notes

* Health suggestions are AI-generated (not medical advice)
* Data is stored locally in SQLite
* Designed for quick hostel-friendly health support

---

## 🔮 Future Improvements

* Mobile app integration
* Voice input support
* Doctor consultation API
* Notification system

---
