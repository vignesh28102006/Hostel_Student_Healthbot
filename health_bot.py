import os
import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Tuple
import google.generativeai as genai
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import print as rprint
from rich.box import DOUBLE
from rich.layout import Layout
from rich.live import Live
from rich.text import Text
from rich.columns import Columns
from rich.align import Align
import time
import sys
import argparse

# Load environment variables
load_dotenv()

# Initialize Gemini AI
try:
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    # Try different model names
    try:
        model = genai.GenerativeModel('gemini-1.5-pro')
    except:
        try:
            model = genai.GenerativeModel('gemini-pro')
        except:
            model = genai.GenerativeModel('gemini-1.0-pro')
except Exception as e:
    console = Console()
    console.print(f"[red]Error initializing Gemini AI: {str(e)}[/red]")
    console.print("[yellow]Please check your API key and internet connection.[/yellow]")
    exit(1)

# Initialize Rich console
console = Console()

# Constants
DB_FILE = "health_logs.db"
SYMPTOMS_DB = "symptoms_db.json"
SESSION_START_TIME = time.time()

# ASCII Art for body map
BODY_MAP = """
    ┌─────┐   1. Head
    │  O  │   2. Neck
    └──┬──┘   3. Chest
     ┌─┴─┐    4. Stomach
     │   │    5. Arms
    ┌┴─┐ │    6. Legs
    │ │ │ │   
    └─┘ └─┘   
"""

# Seasonal health alerts
SEASONAL_ALERTS = {
    "summer": [
        "🌞 Stay hydrated! Aim for 8-10 glasses of water daily",
        "🌡️ Heat exhaustion risk - limit outdoor activity between 11AM-3PM"
    ],
    "monsoon": [
        "🦟 Dengue risk increased - use mosquito nets and repellents",
        "💧 Avoid walking through stagnant water"
    ],
    "winter": [
        "🧣 Keep warm! Cold temperatures can lower immunity",
        "🫁 Indoor air quality matters - ventilate your room daily"
    ]
}

# Health research topics
HEALTH_TOPICS = {
    "dengue": {
        "prevention": [
            "• Use mosquito nets and repellents",
            "• Eliminate stagnant water sources",
            "• Wear full-sleeve clothing",
            "• Keep surroundings clean",
            "• Use window screens"
        ],
        "first_aid": [
            "1. Rest and stay hydrated",
            "2. Take paracetamol for fever",
            "3. Avoid aspirin",
            "4. Monitor for warning signs",
            "5. Seek medical help if symptoms worsen"
        ]
    },
    "fever": {
        "prevention": [
            "• Maintain good hygiene",
            "• Get adequate rest",
            "• Stay hydrated",
            "• Eat nutritious food",
            "• Avoid close contact with sick people"
        ],
        "first_aid": [
            "1. Take temperature regularly",
            "2. Use fever reducer if >101°F",
            "3. Apply cool compress",
            "4. Rest and hydrate",
            "5. Monitor symptoms"
        ]
    },
    "common cold": {
        "prevention": [
            "• Wash hands frequently",
            "• Avoid touching face",
            "• Stay away from sick people",
            "• Get adequate sleep",
            "• Maintain good ventilation"
        ],
        "first_aid": [
            "1. Drink warm fluids",
            "2. Use saline nasal drops",
            "3. Gargle with warm salt water",
            "4. Take vitamin C supplements",
            "5. Rest and stay warm"
        ]
    },
    "heat stroke": {
        "prevention": [
            "• Stay hydrated",
            "• Wear light, loose clothing",
            "• Avoid peak sun hours",
            "• Use sunscreen",
            "• Take frequent breaks in shade"
        ],
        "first_aid": [
            "1. Move to cool place",
            "2. Remove excess clothing",
            "3. Apply cool compresses",
            "4. Drink cool water",
            "5. Seek medical help if severe"
        ]
    },
    "seasonal allergies": {
        "prevention": [
            "• Keep windows closed",
            "• Use air purifiers",
            "• Wash clothes after outdoor activities",
            "• Take allergy medication",
            "• Monitor pollen count"
        ],
        "first_aid": [
            "1. Use antihistamines",
            "2. Apply cold compress for eye irritation",
            "3. Use saline nasal spray",
            "4. Take warm showers",
            "5. Keep emergency medication handy"
        ]
    }
}

# Loading animations
LOADING_FRAMES = [
    "╔════╗\n║ 🏥 ║\n╚════╝",
    "╔════╗\n║ ⚕️  ║\n╚════╝",
    "╔════╗\n║ 💊 ║\n╚════╝",
    "╔════╗\n║ 🩺 ║\n╚════╝"
]

def init_db():
    """Initialize SQLite database."""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        
        # Users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                student_id TEXT PRIMARY KEY,
                full_name TEXT NOT NULL,
                age INTEGER NOT NULL,
                gender TEXT NOT NULL,
                hostel_room TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_login TEXT NOT NULL
            )
        """)
        
        # Existing sessions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                symptoms TEXT NOT NULL,
                keywords TEXT NOT NULL,
                score INTEGER NOT NULL,
                verdict TEXT NOT NULL,
                gemini_response TEXT NOT NULL,
                FOREIGN KEY (student_id) REFERENCES users(student_id)
            )
        """)
        
        # Medical history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS medical_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                condition TEXT NOT NULL,
                description TEXT,
                start_date TEXT,
                end_date TEXT,
                is_ongoing INTEGER DEFAULT 1,
                created_at TEXT NOT NULL,
                FOREIGN KEY (student_id) REFERENCES users(student_id)
            )
        """)
        
        # Allergies table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS allergies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                type TEXT NOT NULL,
                name TEXT NOT NULL,
                severity TEXT NOT NULL,
                notes TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (student_id) REFERENCES users(student_id)
            )
        """)
        
        # Emergency contacts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS emergency_contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                name TEXT NOT NULL,
                relationship TEXT NOT NULL,
                phone TEXT NOT NULL,
                email TEXT,
                is_primary INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY (student_id) REFERENCES users(student_id)
            )
        """)
        
        conn.commit()
    
    console.print("[green]✅ Database initialized successfully![/green]")

def load_symptoms_db() -> Dict:
    """Load symptoms database from JSON file."""
    try:
        with open(SYMPTOMS_DB, 'r') as f:
            console.print("[green]✅ Symptoms database loaded successfully![/green]")
            return json.load(f)
    except Exception as e:
        console.print(f"[red]❌ Error loading symptoms database: {str(e)}[/red]")
        return {}

def analyze_symptoms(symptoms: str, symptoms_db: Dict) -> Tuple[List[str], int]:
    """Analyze symptoms and return matched keywords and score."""
    keywords = []
    score = 0
    symptoms_lower = symptoms.lower()
    
    for condition, data in symptoms_db.items():
        for keyword in data['keywords']:
            if keyword in symptoms_lower:
                keywords.append(keyword)
                score += data['weight']
    
    if not keywords:
        console.print("[yellow]⚠️ No matching keywords found in symptoms.[/yellow]")
    else:
        console.print(f"[green]✅ Found {len(keywords)} matching keywords.[/green]")
    
    return keywords, score

def get_verdict(score: int) -> str:
    """Determine verdict based on score."""
    if score < 3:
        return "🟢 Home Care"
    elif 3 <= score <= 5:
        return "🟡 Monitor"
    else:
        return "🔴 Urgent Care"

def get_gemini_response(symptoms: str, keywords: List[str]) -> Dict:
    """Get response from Gemini AI for given symptoms."""
    prompt = f"""Given these symptoms from a college student: "{symptoms}".
    Detected keywords: {', '.join(keywords)}.
    Please provide health advice in exactly this format:
    💊 Remedy: [provide a clear, concise home remedy]
    👨‍⚕️ When to see doctor: [explain when medical attention is needed]
    
    Make sure to include EXACTLY these two sections with the exact headings '💊 Remedy:' and '👨‍⚕️ When to see doctor:'"""
    
    try:
        response = model.generate_content(prompt)
        text = response.text
        
        # More robust parsing
        try:
            remedy = text.split("💊 Remedy:")[1].split("👨‍⚕️ When to see doctor:")[0].strip()
        except:
            remedy = "Unable to parse remedy from AI response"
            
        try:
            doctor_advice = text.split("👨‍⚕️ When to see doctor:")[1].strip()
        except:
            doctor_advice = "If symptoms persist or worsen, please consult a healthcare provider"
            
        return {
            "remedy": remedy,
            "doctor_advice": doctor_advice
        }
    except Exception as e:
        console.print(f"[red]❌ Error getting AI response: {str(e)}[/red]")
        return {
            "remedy": "Error getting AI response. Please try again.",
            "doctor_advice": "If symptoms persist, please consult a healthcare provider."
        }

def save_log(symptoms: str, keywords: List[str], score: int, verdict: str, response: Dict, student_id: str):
    """Save the health log entry to SQLite database."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO sessions (student_id, timestamp, symptoms, keywords, score, verdict, gemini_response)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (student_id, timestamp, symptoms, json.dumps(keywords), score, verdict, json.dumps(response)))
        conn.commit()
    
    console.print("[green]✅ Health log saved successfully![/green]")
    console.print("[yellow]📝 You can view your health history later.[/yellow]")

def display_response(symptoms: str, keywords: List[str], score: int, verdict: str, response: Dict):
    """Display the response in a rich table."""
    table = Table(show_header=True, header_style="bold magenta", box=DOUBLE)
    table.add_column("📋 Category", style="cyan")
    table.add_column("📝 Details", style="green")
    
    table.add_row("🤒 Symptoms", symptoms)
    table.add_row("🔑 Detected Keywords", ", ".join(keywords))
    table.add_row("📊 Severity Score", str(score))
    table.add_row("⚖️ Verdict", verdict)
    table.add_row("💊 Suggested Remedy", response['remedy'])
    table.add_row("👨‍⚕️ When to see doctor", response['doctor_advice'])
    
    if score > 5:
        console.print(Panel(table, title="🚨 URGENT: Health Advice", border_style="red"))
        console.print("[red]⚠️ Please seek medical attention immediately![/red]")
    else:
        console.print(Panel(table, title="💊 Health Advice", border_style="blue"))
        console.print("[green]✅ Follow the suggested remedy and monitor your symptoms.[/green]")

def validate_symptoms(symptoms: str) -> bool:
    """Validate the symptoms input."""
    if len(symptoms) < 3:
        console.print("[red]❌ Please provide at least 3 characters.[/red]")
        return False
    if any(char.isdigit() for char in symptoms):
        console.print("[red]❌ Please avoid using numbers in your symptoms description.[/red]")
        return False
    return True

def report_symptoms(student_id: str):
    """Handle symptom reporting flow."""
    symptoms_db = load_symptoms_db()
    
    while True:
        console.print(Panel("🤒 Report your symptoms", style="bold blue"))
        symptoms = Prompt.ask("📝 Describe your symptoms")
        
        if not validate_symptoms(symptoms):
            console.print("[red]❌ Invalid input! Please provide at least 3 characters and avoid numbers.[/red]")
            continue
        
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}")) as progress:
            progress.add_task(description="🔄 Analyzing symptoms...", total=None)
            keywords, score = analyze_symptoms(symptoms, symptoms_db)
            verdict = get_verdict(score)
            response = get_gemini_response(symptoms, keywords)
        
        display_response(symptoms, keywords, score, verdict, response)
        save_log(symptoms, keywords, score, verdict, response, student_id)
        break

def view_history(student_id: str):
    """Display recent health history from database."""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT timestamp, symptoms, score, verdict 
            FROM sessions 
            WHERE student_id = ? 
            ORDER BY timestamp DESC 
            LIMIT 5
        """, (student_id,))
        logs = cursor.fetchall()
    
    if not logs:
        console.print("[yellow]📭 No health logs found.[/yellow]")
        console.print("[yellow]📝 Start by reporting your symptoms.[/yellow]")
        return
    
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("📅 Date", style="cyan")
    table.add_column("🤒 Symptoms", style="green")
    table.add_column("📊 Score", style="yellow")
    table.add_column("⚖️ Verdict", style="blue")
    
    for log in logs:
        verdict_emoji = "🟢" if log[3] == "Home Care" else "🟡" if log[3] == "Monitor" else "🔴"
        table.add_row(log[0], log[1], str(log[2]), f"{verdict_emoji} {log[3]}")
    
    console.print(Panel(table, title="📋 Recent Health History", border_style="green"))
    console.print("[yellow]📝 Showing last 5 entries. Use export to see more.[/yellow]")

def delete_last_entry(student_id: str):
    """Delete the most recent health log entry."""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id FROM sessions 
            WHERE student_id = ? 
            ORDER BY timestamp DESC 
            LIMIT 1
        """, (student_id,))
        last_id = cursor.fetchone()
        
        if last_id:
            if Confirm.ask("🗑️ Are you sure you want to delete the last entry?"):
                cursor.execute("DELETE FROM sessions WHERE id = ? AND student_id = ?", (last_id[0], student_id))
                conn.commit()
                console.print("[green]✅ Last entry deleted successfully.[/green]")
                console.print("[yellow]📝 You can view your updated health history.[/yellow]")
            else:
                console.print("[yellow]❌ Operation cancelled.[/yellow]")
        else:
            console.print("[yellow]📭 No entries to delete.[/yellow]")
            console.print("[yellow]📝 Start by reporting your symptoms.[/yellow]")

def export_history(student_id: str):
    """Export health history to a text file."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    export_file = f"health_history_{student_id}_{timestamp}.txt"
    
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT timestamp, symptoms, keywords, score, verdict, gemini_response 
            FROM sessions 
            WHERE student_id = ? 
            ORDER BY timestamp
        """, (student_id,))
        logs = cursor.fetchall()
    
    if not logs:
        console.print("[yellow]📭 No health logs to export.[/yellow]")
        console.print("[yellow]📝 Start by reporting your symptoms.[/yellow]")
        return
    
    with open(export_file, 'w') as f:
        f.write("📋 Health History Export\n")
        f.write("=" * 50 + "\n\n")
        for log in logs:
            f.write(f"📅 Date: {log[0]}\n")
            f.write(f"🤒 Symptoms: {log[1]}\n")
            f.write(f"🔑 Keywords: {log[2]}\n")
            f.write(f"📊 Score: {log[3]}\n")
            f.write(f"⚖️ Verdict: {log[4]}\n")
            f.write(f"💡 Response: {log[5]}\n")
            f.write("=" * 50 + "\n\n")
    
    console.print(f"[green]✅ History exported to {export_file}[/green]")
    console.print("[yellow]📝 You can find the file in the current directory.[/yellow]")

def create_new_profile():
    """Create a new user profile."""
    try:
        console.print(Panel("💡 Let's create your profile!", style="bold blue"))
        
        while True:
            try:
                full_name = Prompt.ask("📝 Full Name")
                if not full_name.strip():
                    console.print("[red]❌ Full name cannot be empty.[/red]")
                    continue
                
                student_id = Prompt.ask("🎓 Student ID")
                if not student_id.strip():
                    console.print("[red]❌ Student ID cannot be empty.[/red]")
                    continue
                
                # Check if student ID already exists
                with sqlite3.connect(DB_FILE) as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT student_id FROM users WHERE student_id = ?", (student_id,))
                    if cursor.fetchone():
                        console.print("[red]❌ This Student ID is already registered.[/red]")
                        continue
                
                age = Prompt.ask("🎂 Age")
                try:
                    age = int(age)
                    if age < 0 or age > 120:
                        console.print("[red]❌ Please enter a valid age between 0 and 120.[/red]")
                        continue
                except ValueError:
                    console.print("[red]❌ Please enter a valid number for age.[/red]")
                    continue
                
                gender = Prompt.ask("🚻 Gender", choices=["Male", "Female", "Other"])
                hostel_room = Prompt.ask("🏠 Hostel/Room Number")
                if not hostel_room.strip():
                    console.print("[red]❌ Hostel/Room number cannot be empty.[/red]")
                    continue
                
                break
            except Exception as e:
                console.print(f"[red]❌ Error in input: {str(e)}[/red]")
                continue
        
        # Save to database
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO users 
                    (student_id, full_name, age, gender, hostel_room, created_at, last_login)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (student_id, full_name, age, gender, hostel_room, timestamp, timestamp))
                conn.commit()
                console.print(Panel("✅ Profile created successfully! 🎉", style="bold green"))
                return student_id
            except sqlite3.Error as e:
                console.print(f"[red]❌ Database error: {str(e)}[/red]")
                console.print("[yellow]⚠️ Please try again later.[/yellow]")
                return None
    
    except Exception as e:
        console.print(f"[red]❌ An error occurred: {str(e)}[/red]")
        console.print("[yellow]⚠️ Please try again later.[/yellow]")
        return None

def login():
    """Login with student ID."""
    while True:
        console.print(Panel("🔐 Login to your account", style="bold blue"))
        student_id = Prompt.ask("🎓 Enter your Student ID")
        
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE student_id = ?", (student_id,))
            user = cursor.fetchone()
            
            if user:
                # Update last login time
                cursor.execute("""
                    UPDATE users 
                    SET last_login = ? 
                    WHERE student_id = ?
                """, (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), student_id))
                conn.commit()
                
                console.print(Panel(f"👋 Welcome back, {user[1]}!", style="bold green"))
                return student_id
            else:
                console.print("[red]❌ Student ID not found.[/red]")
                if Confirm.ask("Would you like to create a new profile?"):
                    return create_new_profile()
                else:
                    continue

def manage_medical_history(student_id: str):
    """Manage medical history entries."""
    while True:
        console.print(Panel("🩺 Medical History Management", style="bold blue"))
        console.print("1. ➕ Add new condition")
        console.print("2. 📋 View history")
        console.print("3. ↩️ Back to main menu")
        
        choice = Prompt.ask("Choose an option", choices=["1", "2", "3"])
        
        if choice == "1":
            condition = Prompt.ask("🤒 Condition name")
            description = Prompt.ask("📝 Description (optional)")
            start_date = Prompt.ask("📅 Start date (YYYY-MM-DD)")
            is_ongoing = Confirm.ask("⏳ Is this an ongoing condition?")
            end_date = None if is_ongoing else Prompt.ask("📅 End date (YYYY-MM-DD)")
            
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            with sqlite3.connect(DB_FILE) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO medical_history 
                    (student_id, condition, description, start_date, end_date, is_ongoing, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (student_id, condition, description, start_date, end_date, 1 if is_ongoing else 0, timestamp))
                conn.commit()
            
            console.print(Panel("✅ Medical condition added successfully! 🎉", style="bold green"))
            console.print("[yellow]📝 You can view your medical history anytime.[/yellow]")
            
        elif choice == "2":
            with sqlite3.connect(DB_FILE) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM medical_history WHERE student_id = ? ORDER BY created_at DESC", (student_id,))
                history = cursor.fetchall()
            
            if not history:
                console.print("[yellow]📭 No medical history found.[/yellow]")
                console.print("[yellow]📝 Start by adding a medical condition.[/yellow]")
                continue
            
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("🤒 Condition", style="cyan")
            table.add_column("📝 Description", style="green")
            table.add_column("📅 Start Date", style="yellow")
            table.add_column("⏳ Status", style="blue")
            
            for entry in history:
                status = "🟢 Ongoing" if entry[5] else f"🔴 Ended: {entry[4]}" if entry[4] else "⚪ Unknown"
                table.add_row(entry[2], entry[3] or "", entry[3], status)
            
            console.print(Panel(table, title="📋 Medical History", border_style="green"))
            console.print("[yellow]📝 You can add more conditions anytime.[/yellow]")
            
        elif choice == "3":
            break

def manage_allergies(student_id: str):
    """Manage allergies and conditions."""
    while True:
        console.print(Panel("⚠️ Allergies & Conditions Management", style="bold blue"))
        console.print("1. ➕ Add new allergy/condition")
        console.print("2. 📋 View allergies/conditions")
        console.print("3. ↩️ Back to main menu")
        
        choice = Prompt.ask("Choose an option", choices=["1", "2", "3"])
        
        if choice == "1":
            allergy_type = Prompt.ask("🏷️ Type (e.g., food, drug, environmental)")
            name = Prompt.ask("📝 Name")
            severity = Prompt.ask("⚠️ Severity", choices=["Mild", "Moderate", "Severe"])
            notes = Prompt.ask("📝 Additional notes (optional)")
            
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            with sqlite3.connect(DB_FILE) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO allergies 
                    (student_id, type, name, severity, notes, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (student_id, allergy_type, name, severity, notes, timestamp))
                conn.commit()
            
            console.print(Panel("✅ Allergy/condition added successfully! 🎉", style="bold green"))
            console.print("[yellow]📝 You can view your allergies anytime.[/yellow]")
            
        elif choice == "2":
            with sqlite3.connect(DB_FILE) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM allergies WHERE student_id = ? ORDER BY created_at DESC", (student_id,))
                allergies = cursor.fetchall()
            
            if not allergies:
                console.print("[yellow]📭 No allergies or conditions found.[/yellow]")
                console.print("[yellow]📝 Start by adding an allergy or condition.[/yellow]")
                continue
            
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("🏷️ Type", style="cyan")
            table.add_column("📝 Name", style="red")
            table.add_column("⚠️ Severity", style="yellow")
            table.add_column("📝 Notes", style="green")
            
            for allergy in allergies:
                severity_emoji = "🟢" if allergy[3] == "Mild" else "🟡" if allergy[3] == "Moderate" else "🔴"
                table.add_row(allergy[2], allergy[3], f"{severity_emoji} {allergy[3]}", allergy[5] or "")
            
            console.print(Panel(table, title="📋 Allergies & Conditions", border_style="red"))
            console.print("[yellow]📝 You can add more allergies anytime.[/yellow]")
            
        elif choice == "3":
            break

def manage_emergency_contacts(student_id: str):
    """Manage emergency contacts."""
    while True:
        console.print(Panel("📞 Emergency Contacts Management", style="bold blue"))
        console.print("1. ➕ Add new contact")
        console.print("2. 📋 View contacts")
        console.print("3. ↩️ Back to main menu")
        
        choice = Prompt.ask("Choose an option", choices=["1", "2", "3"])
        
        if choice == "1":
            name = Prompt.ask("👤 Name")
            relationship = Prompt.ask("🤝 Relationship")
            phone = Prompt.ask("📱 Phone Number")
            email = Prompt.ask("✉️ Email (optional)")
            is_primary = Confirm.ask("⭐ Set as primary contact?")
            
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            with sqlite3.connect(DB_FILE) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO emergency_contacts 
                    (student_id, name, relationship, phone, email, is_primary, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (student_id, name, relationship, phone, email, 1 if is_primary else 0, timestamp))
                conn.commit()
            
            console.print(Panel("✅ Emergency contact added successfully! 🎉", style="bold green"))
            
        elif choice == "2":
            with sqlite3.connect(DB_FILE) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM emergency_contacts WHERE student_id = ? ORDER BY is_primary DESC, created_at DESC", (student_id,))
                contacts = cursor.fetchall()
            
            if not contacts:
                console.print("[yellow]📭 No emergency contacts found.[/yellow]")
                continue
            
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("👤 Name", style="cyan")
            table.add_column("🤝 Relationship", style="green")
            table.add_column("📱 Phone", style="yellow")
            table.add_column("✉️ Email", style="blue")
            table.add_column("⭐ Primary", style="red")
            
            for contact in contacts:
                table.add_row(
                    contact[2],
                    contact[3],
                    contact[4],
                    contact[5] or "",
                    "⭐ Yes" if contact[6] else "No"
                )
            
            console.print(Panel(table, title="📋 Emergency Contacts", border_style="blue"))
            
        elif choice == "3":
            break

def show_symptom_timeline(student_id: str):
    """Display symptom frequency for the last 7 days using Rich's Table."""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)
    
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DATE(timestamp), COUNT(*) 
            FROM sessions 
            WHERE student_id = ? AND timestamp >= ? 
            GROUP BY DATE(timestamp)
            ORDER BY DATE(timestamp)
        """, (student_id, start_date.strftime("%Y-%m-%d")))
        data = cursor.fetchall()
    
    # Prepare data
    dates = [(end_date - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7, -1, -1)]
    counts = {date: 0 for date in dates}
    for date, count in data:
        if date in counts:
            counts[date] = count
    
    # Create table
    table = Table(show_header=True, header_style="bold magenta", box=DOUBLE)
    table.add_column("📅 Date", style="cyan")
    table.add_column("📊 Frequency", style="green")
    table.add_column("📈 Graph", style="yellow")
    
    max_count = max(counts.values()) if counts.values() else 1
    for date in dates:
        count = counts[date]
        graph = "█" * int((count * 20) / max_count)  # Scale to max 20 characters
        table.add_row(
            datetime.strptime(date, "%Y-%m-%d").strftime("%d/%m"),
            str(count),
            graph
        )
    
    console.print(Panel(table, title="📊 Health Timeline", border_style="blue"))

def show_body_map():
    """Display interactive body map for pain location."""
    console.print(Panel(BODY_MAP, title="🗺️ Body Map", border_style="blue"))
    location = Prompt.ask(
        "Select pain location",
        choices=["1", "2", "3", "4", "5", "6"],
        show_choices=False
    )
    
    locations = {
        "1": "Head",
        "2": "Neck",
        "3": "Chest",
        "4": "Stomach",
        "5": "Arms",
        "6": "Legs"
    }
    
    return locations[location]

def analyze_trends(student_id: str):
    """Analyze symptom trends and patterns."""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        
        # Get symptom frequency by time of day
        cursor.execute("""
            SELECT 
                symptoms,
                strftime('%H', timestamp) as hour,
                COUNT(*) as frequency
            FROM sessions 
            WHERE student_id = ?
            GROUP BY symptoms, hour
            HAVING frequency > 2
        """, (student_id,))
        trends = cursor.fetchall()
        
        if trends:
            console.print("\n[bold blue]📈 Trend Analysis[/bold blue]")
            for symptom, hour, freq in trends:
                hour_int = int(hour)
                time_of_day = "morning" if 5 <= hour_int < 12 else "afternoon" if 12 <= hour_int < 17 else "evening" if 17 <= hour_int < 22 else "night"
                console.print(f"• Your '{symptom}' occurs {freq}x during {time_of_day}")

def get_personalized_advice(student_id: str):
    """Generate personalized health advice based on symptom history."""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        
        # Check for frequent symptoms
        cursor.execute("""
            SELECT symptoms, COUNT(*) as frequency
            FROM sessions 
            WHERE student_id = ?
            GROUP BY symptoms
            HAVING frequency >= 3
        """, (student_id,))
        frequent_symptoms = cursor.fetchall()
        
        if frequent_symptoms:
            console.print("\n[bold green]💡 Personalized Advice[/bold green]")
            for symptom, freq in frequent_symptoms:
                if "fatigue" in symptom.lower():
                    console.print("• Consider iron-rich foods (spinach, lentils) - common in hostel diets")
                    console.print("• Maintain a regular sleep schedule (aim for 7-8 hours)")
                elif "headache" in symptom.lower():
                    console.print("• Take regular screen breaks (20-20-20 rule)")
                    console.print("• Stay hydrated and maintain good posture")
        
        # Add seasonal alerts
        month = datetime.now().month
        season = "summer" if 3 <= month <= 6 else "monsoon" if 7 <= month <= 10 else "winter"
        
        console.print(f"\n[bold yellow]🌤️ Seasonal Health Alert[/bold yellow]")
        for alert in SEASONAL_ALERTS[season]:
            console.print(f"• {alert}")

def show_research_info(topic: str):
    """Display research information in a two-column layout."""
    if topic not in HEALTH_TOPICS:
        console.print("[red]❌ Topic not found in research database.[/red]")
        return
    
    info = HEALTH_TOPICS[topic]
    
    # Create columns
    prevention = Panel(
        "\n".join(info["prevention"]),
        title="🛡️ Prevention",
        border_style="blue"
    )
    
    first_aid = Panel(
        "\n".join(info["first_aid"]),
        title="🚑 First Aid",
        border_style="red"
    )
    
    # Display with animation
    with Live(refresh_per_second=4) as live:
        # First show loading animation
        for _ in range(3):
            for frame in LOADING_FRAMES:
                live.update(Text(frame, style="bold blue"))
                time.sleep(0.2)
        
        # Then show the content
        layout = Layout()
        layout.split_column(
            Layout(name="title"),
            Layout(name="content")
        )
        layout["title"].update(Panel(f"Research: {topic.title()}", style="bold magenta"))
        layout["content"].split_row(
            Layout(prevention),
            Layout(first_aid)
        )
        live.update(layout)

def show_session_stats():
    """Display session statistics."""
    session_duration = int(time.time() - SESSION_START_TIME)
    minutes = session_duration // 60
    seconds = session_duration % 60
    
    console.print(f"\n[bold blue]⏱️ Session Stats[/bold blue]")
    console.print(f"You've used HealthBot for {minutes}m {seconds}s today")

def play_alert_sound():
    """Play system bell for critical alerts."""
    sys.stdout.write('\a')
    sys.stdout.flush()

def show_loading_animation():
    """Display loading animation."""
    with Live(refresh_per_second=4) as live:
        for frame in LOADING_FRAMES:
            live.update(Text(frame, style="bold blue"))
            time.sleep(0.2)

def premium_health_menu(student_id: str):
    """Display premium health features menu."""
    while True:
        console.print(Panel.fit(
            "[1] 📊 Health Timeline\n"
            "[2] 🗺️ Body Map\n"
            "[3] 📈 Trend Analysis\n"
            "[4] 💡 Personalized Advice\n"
            "[5] 📚 Health Research\n"
            "[6] ↩️ Back to Main Menu",
            title="✨ Premium Features",
            border_style="blue"
        ))
        
        choice = Prompt.ask("Choose an option", choices=["1", "2", "3", "4", "5", "6"])
        
        if choice == "1":
            show_symptom_timeline(student_id)
        elif choice == "2":
            location = show_body_map()
            console.print(f"[green]Selected location: {location}[/green]")
        elif choice == "3":
            analyze_trends(student_id)
        elif choice == "4":
            get_personalized_advice(student_id)
        elif choice == "5":
            topic = Prompt.ask("Enter health topic to research", choices=list(HEALTH_TOPICS.keys()))
            show_research_info(topic)
        elif choice == "6":
            break
        
        show_session_stats()

def main():
    """Main application loop."""
    # Handle command line arguments
    parser = argparse.ArgumentParser(description="HealthBot - Your Personal Health Assistant")
    parser.add_argument("--research", type=str, help="Research a health topic")
    args = parser.parse_args()

    # If research argument is provided, show research info and exit
    if args.research:
        if args.research in HEALTH_TOPICS:
            show_research_info(args.research)
        else:
            console.print(f"[red]❌ Topic '{args.research}' not found.[/red]")
            console.print(f"[yellow]Available topics: {', '.join(HEALTH_TOPICS.keys())}[/yellow]")
        return

    console.print(Panel("🏥 Welcome to Health Alert Bot! 🏥", style="bold blue"))
    init_db()
    
    # Login or create new profile
    current_user_id = None
    while not current_user_id:
        console.print(Panel.fit(
            "[1] 🔐 Login\n[2] ✨ Create New Profile",
            title="Account Management",
            border_style="blue"
        ))
        
        choice = Prompt.ask("Choose an option", choices=["1", "2"])
        
        if choice == "1":
            current_user_id = login()
        else:
            current_user_id = create_new_profile()
    
    # Get user details for display
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT full_name, student_id FROM users WHERE student_id = ?", (current_user_id,))
        user = cursor.fetchone()
    
    while True:
        show_loading_animation()
        console.print(Panel.fit(
            f"👤 {user[0]} | 🎓 {user[1]}\n\n"
            "[1] 🤒 Report Symptoms\n"
            "[2] 🗑️ Delete Last Entry\n"
            "[3] 📤 Export History\n"
            "[4] 👤 User Profile\n"
            "[5] ✨ Premium Features\n"
            "[6] 🚪 Exit",
            title="🏥 Health Alert Bot",
            border_style="blue"
        ))
        
        choice = Prompt.ask("Choose an option", choices=["1", "2", "3", "4", "5", "6"])
        
        if choice == "1":
            report_symptoms(current_user_id)
        elif choice == "2":
            delete_last_entry(current_user_id)
        elif choice == "3":
            export_history(current_user_id)
        elif choice == "4":
            while True:
                console.print(Panel.fit(
                    "[1] 🩺 Medical History\n"
                    "[2] ⚠️ Allergies & Conditions\n"
                    "[3] 📞 Emergency Contacts\n"
                    "[4] ↩️ Back to Main Menu",
                    title="👤 User Profile Management",
                    border_style="blue"
                ))
                profile_choice = Prompt.ask("Choose an option", choices=["1", "2", "3", "4"])
                if profile_choice == "1":
                    manage_medical_history(current_user_id)
                elif profile_choice == "2":
                    manage_allergies(current_user_id)
                elif profile_choice == "3":
                    manage_emergency_contacts(current_user_id)
                elif profile_choice == "4":
                    break
        elif choice == "5":
            premium_health_menu(current_user_id)
        elif choice == "6":
            if Confirm.ask("Are you sure you want to exit?"):
                show_session_stats()
                console.print("[green]👋 Goodbye! Stay healthy![/green]")
                break

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️ Program interrupted by user.[/yellow]")
        console.print("[green]👋 Goodbye! Stay healthy![/green]")
    except Exception as e:
        console.print(f"[red]❌ An error occurred: {str(e)}[/red]")
        console.print("[yellow]⚠️ Please try again later.[/yellow]") 