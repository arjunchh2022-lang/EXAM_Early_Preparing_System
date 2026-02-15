import gradio as gr
import csv, os, smtplib, time, threading, json, hashlib, secrets, sqlite3
from email.message import EmailMessage
from datetime import datetime, timedelta
import wikipedia
import random
import string

# ================= CONFIG =================
SENDER_EMAIL = "exam.eps12@gmail.com"
SENDER_PASSWORD = "getfyqzitlmrzpcd"
BASE_DIR = os.path.join(os.path.expanduser("~"), "Desktop", "EXAM_EPS_DATA")
os.makedirs(BASE_DIR, exist_ok=True)

# File paths
LOG_FILE = os.path.join(BASE_DIR, "activity_log.csv")
NOTES_FILE = os.path.join(BASE_DIR, "notes.txt")
TASKS_FILE = os.path.join(BASE_DIR, "tasks.json")
GOALS_FILE = os.path.join(BASE_DIR, "goals.json")
AUTH_FILE = os.path.join(BASE_DIR, "auth.db")

# Admin config
ADMIN_EMAIL = "exam.eps12@gmail.com"
ADMIN_KEY = "EXAM_ADMIN_2024"

# Predefined activities
ACTIVITY_OPTIONS = [
    "STUDY", "HOMEWORK", "REVISION", "SCREENTIME", "EXERCISE", "SLEEP",
    "BREAK", "READING", "PRACTICE"
]

# Global variables
current_activity = None
start_time = None
timer_running = False
live_time = "00:00:00"
current_user_email = None
current_user_name = None


# ================= FILE SETUP =================
def setup_files():
    """Setup all required files"""
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w", newline="") as f:
            csv.writer(f).writerow(["date", "activity", "seconds", "user"])

    if not os.path.exists(NOTES_FILE):
        open(NOTES_FILE, "w").close()

    if not os.path.exists(TASKS_FILE):
        with open(TASKS_FILE, "w") as f:
            json.dump([], f)

    if not os.path.exists(GOALS_FILE):
        with open(GOALS_FILE, "w") as f:
            json.dump([], f)

    setup_auth_db()


def setup_auth_db():
    """Setup authentication database"""
    conn = sqlite3.connect(AUTH_FILE)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            is_active BOOLEAN DEFAULT 1,
            is_blocked BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP,
            blocked_at TIMESTAMP,
            blocked_reason TEXT
        )
    ''')

    conn.commit()
    conn.close()


setup_files()


# ================= AUTHENTICATION FUNCTIONS =================
def generate_password(length=10):
    """Generate random password"""
    characters = string.ascii_letters + string.digits
    return ''.join(secrets.choice(characters) for _ in range(length))


def hash_password(password):
    """Hash password"""
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(stored_hash, password):
    """Verify password"""
    return hash_password(password) == stored_hash


def create_account(name, email):
    """Create new user account"""
    email = email.strip().lower()
    name = name.strip()

    if not email or "@" not in email:
        return "❌ Please enter a valid email address"

    if not name:
        return "❌ Please enter your name"

    password = generate_password()

    conn = sqlite3.connect(AUTH_FILE)
    cursor = conn.cursor()

    cursor.execute("SELECT id, is_blocked FROM users WHERE email = ?",
                   (email, ))
    user = cursor.fetchone()

    if user:
        if user[1]:
            conn.close()
            return "❌ This email has been blocked. Please contact admin."
        conn.close()
        return "❌ Email already registered! Please login."

    try:
        cursor.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, hash_password(password)))

        conn.commit()
        conn.close()

        try:
            send_welcome_email(name, email, password)
            return f"""✅ Account created successfully!

👤 Name: {name}
📧 Email: {email}
🔑 Password: {password}

📩 Credentials have been sent to your email.
You can now login!"""
        except Exception as e:
            return f"""✅ Account created successfully!

👤 Name: {name}
📧 Email: {email}
🔑 Password: {password}

⚠️ Email sending failed: {str(e)}
Please save these credentials!"""

    except Exception as e:
        conn.close()
        return f"❌ Error creating account: {str(e)}"


def send_welcome_email(name, email, password):
    """Send welcome email with credentials"""
    msg = EmailMessage()
    msg["From"] = SENDER_EMAIL
    msg["To"] = email
    msg["Subject"] = f"Welcome to EXAM_EPS - Your Account Details"

    content = f"""Dear {name},

Welcome to EXAM_EPS Study Platform! 🎉

Your account has been successfully created.

🔑 YOUR LOGIN CREDENTIALS:
--------------------------
Name: {name}
Email: {email}
Password: {password}

🚀 GET STARTED:
--------------------------
1. Go to EXAM_EPS login page
2. Enter your email and password
3. Start tracking your studies!

✨ FEATURES:
--------------------------
• Live Study Timer
• Activity Tracking
• Goals & Tasks Management
• Smart Notes
• Wikipedia Search
• Progress Reports
• Daily Email Reports to Parents

Need help? Reply to this email.

Best regards,
EXAM_EPS Team
"""

    msg.set_content(content)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.send_message(msg)


def authenticate_user(email, password):
    """Authenticate user login"""
    global current_user_email, current_user_name
    email = email.strip().lower()

    conn = sqlite3.connect(AUTH_FILE)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT name, password_hash, is_active, is_blocked FROM users WHERE email = ?",
        (email, ))
    user = cursor.fetchone()

    if not user:
        conn.close()
        return False, "❌ User not found. Please create an account first."

    name, stored_hash, is_active, is_blocked = user

    if is_blocked:
        conn.close()
        return False, "❌ Your account has been blocked. Please contact admin."

    if not verify_password(stored_hash, password):
        conn.close()
        return False, "❌ Invalid password"

    cursor.execute(
        "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE email = ?",
        (email, ))

    conn.commit()
    conn.close()

    current_user_email = email
    current_user_name = name
    return True, f"✅ Welcome back, {name}!"


# ================= ADMIN FUNCTIONS =================
def get_all_users():
    """Get all registered users"""
    conn = sqlite3.connect(AUTH_FILE)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT name, email, is_active, is_blocked, created_at, last_login
        FROM users
        ORDER BY created_at DESC
    ''')

    users = cursor.fetchall()
    conn.close()

    if not users:
        return "# 📋 No Users Registered\n\nNo users in the system yet."

    output = "# 👥 All Registered Users\n\n"
    output += f"**Total Users:** {len(users)}\n\n"
    output += "---\n\n"

    for user in users:
        name, email, is_active, is_blocked, created_at, last_login = user

        status_emoji = "🔴" if is_blocked else "🟢"
        status_text = "BLOCKED" if is_blocked else "ACTIVE"

        output += f"### {status_emoji} {name}\n"
        output += f"- **Email:** {email}\n"
        output += f"- **Status:** {status_text}\n"
        output += f"- **Created:** {created_at[:19] if created_at else 'N/A'}\n"
        output += f"- **Last Login:** {last_login[:19] if last_login else 'Never'}\n"
        output += "\n---\n\n"

    return output


def get_active_users():
    """Get currently active users"""
    conn = sqlite3.connect(AUTH_FILE)
    cursor = conn.cursor()

    today = datetime.now().date().isoformat()

    cursor.execute(
        '''
        SELECT name, email, last_login
        FROM users
        WHERE is_blocked = 0
        AND last_login IS NOT NULL
        AND DATE(last_login) = ?
        ORDER BY last_login DESC
    ''', (today, ))

    users = cursor.fetchall()
    conn.close()

    if not users:
        return "# 🟢 Currently Active Users\n\n**No users active today.**"

    output = "# 🟢 Currently Active Users (Today)\n\n"
    output += f"**Active Users:** {len(users)}\n"
    output += f"**Date:** {datetime.now().strftime('%B %d, %Y')}\n\n"
    output += "---\n\n"

    for user in users:
        name, email, last_login = user
        login_time = datetime.fromisoformat(last_login).strftime("%I:%M %p")

        output += f"### 🟢 {name}\n"
        output += f"- **Email:** {email}\n"
        output += f"- **Last Login:** {login_time}\n"
        output += "\n---\n\n"

    return output


def block_user(email, reason="No reason provided"):
    """Block a user account"""
    email = email.strip().lower()

    if not email:
        return "❌ Please enter an email address"

    conn = sqlite3.connect(AUTH_FILE)
    cursor = conn.cursor()

    cursor.execute("SELECT name, is_blocked FROM users WHERE email = ?",
                   (email, ))
    user = cursor.fetchone()

    if not user:
        conn.close()
        return f"❌ User not found: {email}"

    name, is_blocked = user

    if is_blocked:
        conn.close()
        return f"⚠️ User {email} is already blocked"

    cursor.execute(
        '''
        UPDATE users
        SET is_blocked = 1,
            blocked_at = CURRENT_TIMESTAMP,
            blocked_reason = ?
        WHERE email = ?
    ''', (reason, email))

    conn.commit()
    conn.close()

    return f"✅ User blocked successfully!\n\n**Name:** {name}\n**Email:** {email}\n**Reason:** {reason}"


def unblock_user(email):
    """Unblock a user account"""
    email = email.strip().lower()

    if not email:
        return "❌ Please enter an email address"

    conn = sqlite3.connect(AUTH_FILE)
    cursor = conn.cursor()

    cursor.execute("SELECT name, is_blocked FROM users WHERE email = ?",
                   (email, ))
    user = cursor.fetchone()

    if not user:
        conn.close()
        return f"❌ User not found: {email}"

    name, is_blocked = user

    if not is_blocked:
        conn.close()
        return f"⚠️ User {email} is not blocked"

    cursor.execute(
        '''
        UPDATE users
        SET is_blocked = 0,
            blocked_at = NULL,
            blocked_reason = NULL
        WHERE email = ?
    ''', (email, ))

    conn.commit()
    conn.close()

    return f"✅ User unblocked successfully!\n\n**Name:** {name}\n**Email:** {email}"


# ================= GOAL & TASK MANAGER FUNCTIONS =================
def load_goals():
    """Load goals from file"""
    try:
        with open(GOALS_FILE, 'r') as f:
            return json.load(f)
    except:
        return []


def save_goals(goals):
    """Save goals to file"""
    with open(GOALS_FILE, 'w') as f:
        json.dump(goals, f, indent=2)


def add_goal(goal_text, deadline):
    """Add a new goal"""
    if not goal_text or not goal_text.strip():
        return "⚠️ Please enter a goal"

    goals = load_goals()

    new_goal = {
        "id": len(goals) + 1,
        "goal_name": goal_text.strip(),
        "deadline": deadline if deadline else "No deadline",
        "completed": False,
        "created_at": datetime.now().isoformat()
    }

    goals.append(new_goal)
    save_goals(goals)

    return f"✅ Goal added: {goal_text}"


def view_goals():
    """View all goals"""
    goals = load_goals()

    if not goals:
        return "# 📋 No goals yet\n\nAdd your first goal to get started!"

    output = "# 🎯 My Goals\n\n"

    active_goals = [g for g in goals if not g['completed']]
    completed_goals = [g for g in goals if g['completed']]

    if active_goals:
        output += "## 🔥 Active Goals\n\n"
        for goal in active_goals:
            output += f"**#{goal['id']}** - {goal['goal_name']}\n"
            output += f"📅 Deadline: {goal['deadline']}\n"
            output += f"🕐 Created: {goal['created_at'][:10]}\n\n"

    if completed_goals:
        output += "## ✅ Completed Goals\n\n"
        for goal in completed_goals:
            output += f"~~**#{goal['id']}** - {goal['goal_name']}~~\n"
            output += f"✔️ Completed\n\n"

    return output


def complete_goal(goal_id):
    """Mark a goal as completed"""
    try:
        goal_id = int(goal_id)
        goals = load_goals()

        found = False
        for goal in goals:
            if goal['id'] == goal_id:
                goal['completed'] = True
                goal['completed_at'] = datetime.now().isoformat()
                found = True
                goal_text = goal.get('goal_name', 'Goal')
                break

        if found:
            save_goals(goals)
            return f"🎉 Goal #{goal_id} marked as completed!\n\n**{goal_text}**"
        else:
            return f"❌ Goal #{goal_id} not found"

    except ValueError:
        return "❌ Please enter a valid number for Goal ID."
    except Exception as e:
        return f"❌ Error: {str(e)}"


def delete_goal(goal_id):
    """Delete a goal"""
    try:
        goal_id = int(goal_id)
        goals = load_goals()

        original_length = len(goals)
        goals = [g for g in goals if g['id'] != goal_id]

        if len(goals) < original_length:
            save_goals(goals)
            return f"🗑️ Goal #{goal_id} deleted"

        return f"❌ Goal #{goal_id} not found"
    except:
        return "⚠️ Please enter a valid goal ID number"


def load_tasks():
    """Load tasks from file"""
    try:
        with open(TASKS_FILE, 'r') as f:
            return json.load(f)
    except:
        return []


def save_tasks(tasks):
    """Save tasks to file"""
    with open(TASKS_FILE, 'w') as f:
        json.dump(tasks, f, indent=2)


def add_task(task_text, priority):
    """Add a new task"""
    if not task_text or not task_text.strip():
        return "⚠️ Please enter a task"

    tasks = load_tasks()

    new_task = {
        "id": len(tasks) + 1,
        "text": task_text.strip(),
        "priority": priority if priority else "Medium",
        "completed": False,
        "created_at": datetime.now().isoformat()
    }

    tasks.append(new_task)
    save_tasks(tasks)

    return f"✅ Task added: {task_text}"


def view_tasks():
    """View all tasks"""
    tasks = load_tasks()

    if not tasks:
        return "# 📝 No tasks yet\n\nAdd your first task to get started!"

    output = "# 📝 My Tasks\n\n"

    priority_order = {"High": 1, "Medium": 2, "Low": 3}
    active_tasks = [t for t in tasks if not t['completed']]
    active_tasks.sort(key=lambda x: priority_order.get(x['priority'], 2))

    completed_tasks = [t for t in tasks if t['completed']]

    if active_tasks:
        output += "## 📋 Pending Tasks\n\n"
        for task in active_tasks:
            priority_emoji = {"High": "🔴", "Medium": "🟡", "Low": "🟢"}
            emoji = priority_emoji.get(task['priority'], "⚪")
            output += f"{emoji} **#{task['id']}** - {task['text']}\n"
            output += f"Priority: {task['priority']}\n\n"

    if completed_tasks:
        output += "## ✅ Completed Tasks\n\n"
        for task in completed_tasks:
            output += f"✔️ ~~**#{task['id']}** - {task['text']}~~\n\n"

    return output


def complete_task(task_id):
    """Mark task as completed"""
    try:
        task_id = int(task_id)
        tasks = load_tasks()

        for task in tasks:
            if task['id'] == task_id:
                task['completed'] = True
                task['completed_at'] = datetime.now().isoformat()
                save_tasks(tasks)
                return f"✅ Task #{task_id} completed!\n\n**{task['text']}**"

        return f"❌ Task #{task_id} not found"
    except:
        return "⚠️ Please enter a valid task ID number"


def delete_task(task_id):
    """Delete a task"""
    try:
        task_id = int(task_id)
        tasks = load_tasks()

        original_length = len(tasks)
        tasks = [t for t in tasks if t['id'] != task_id]

        if len(tasks) < original_length:
            save_tasks(tasks)
            return f"🗑️ Task #{task_id} deleted"

        return f"❌ Task #{task_id} not found"
    except:
        return "⚠️ Please enter a valid task ID number"


# ================= ACTIVITY TRACKING FUNCTIONS =================
def fmt(sec):
    """Format seconds to human readable"""
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    if h > 0:
        return f"{h}h {m:02}m"
    elif m > 0:
        return f"{m}m {s:02}s"
    else:
        return f"{s}s"


def fmt_clock(sec):
    """Format seconds to clock format"""
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    return f"{h:02}:{m:02}:{s:02}"


def timer_loop():
    """Background timer loop - fixed for uniform intervals"""
    global live_time
    while True:
        try:
            if timer_running and start_time:
                sec = int((datetime.now() - start_time).total_seconds())
                live_time = fmt_clock(sec)
            else:
                live_time = "00:00:00"
        except Exception as e:
            print(f"Timer error: {e}")
        time.sleep(1.0)  # Ensure exact 1-second sleep


# Start timer thread
threading.Thread(target=timer_loop, daemon=True).start()


def start_activity(act):
    """Start tracking an activity"""
    global current_activity, start_time, timer_running
    if current_activity:
        return f"⚠️ {current_activity} is already running. Stop it first.", get_timer_html(
        )
    if not act or not act.strip():
        return "⚠️ Please select an activity", get_timer_html()

    act_clean = act.strip().upper()
    current_activity = act_clean
    start_time = datetime.now()
    timer_running = True
    return f"✅ Started tracking {act_clean}", get_timer_html()


def stop_activity():
    """Stop tracking current activity"""
    global current_activity, timer_running, current_user_email
    if not current_activity:
        return "⚠️ No activity is currently running", get_timer_html()

    duration = int((datetime.now() - start_time).total_seconds())
    timer_running = False

    with open(LOG_FILE, "a", newline="") as f:
        csv.writer(f).writerow([
            datetime.now().date().isoformat(), current_activity, duration,
            current_user_email or "guest"
        ])

    msg = f"✅ Stopped {current_activity} — Duration: {fmt(duration)}"
    current_activity = None
    return msg, get_timer_html()


def pause_activity():
    """Pause current activity"""
    global timer_running
    if not current_activity:
        return "⚠️ No activity is running", get_timer_html()

    if timer_running:
        timer_running = False
        return f"⏸️ Paused {current_activity}", get_timer_html()
    else:
        timer_running = True
        return f"▶️ Resumed {current_activity}", get_timer_html()


def get_timer_html():
    """Get timer HTML - NO GLOW DIV"""
    global timer_running, current_activity, live_time

    if current_activity:
        status = "▶️ LIVE" if timer_running else "⏸️ PAUSED"
        active_class = "active" if timer_running else "paused"
        return f'''
<div class="timer-container {active_class}">
    <div class="timer-text">{live_time}</div>
    <div class="timer-label">{status}: {current_activity}</div>
</div>
'''
    return f'''
<div class="timer-container">
    <div class="timer-text">{live_time}</div>
    <div class="timer-label">⏸️ READY</div>
</div>
'''


def get_dashboard_stats():
    """Get dashboard statistics - ALL 4 STATS"""
    try:
        today = datetime.now().date().isoformat()

        # Count today's study time
        total_time = 0
        with open(LOG_FILE, 'r', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['date'] == today and row['user'] == current_user_email:
                    total_time += int(row['seconds'])

        # Count active goals
        goals = load_goals()
        active_goals = len([g for g in goals if not g['completed']])

        # Count pending tasks
        tasks = load_tasks()
        pending_tasks = len([t for t in tasks if not t['completed']])

        # Count notes (approximate)
        try:
            with open(NOTES_FILE, 'r') as f:
                notes_count = len(
                    [line for line in f if line.strip().startswith("Date:")])
        except:
            notes_count = 0

        return fmt(total_time), active_goals, pending_tasks, notes_count
    except:
        return "0h 0m", 0, 0, 0


def get_stats_html():
    """Generate HTML for all 4 stat cards"""
    study_time, goals, tasks, notes = get_dashboard_stats()

    return (f"""<div class="stat-card">
            <div style="font-size: 40px;">⏱️</div>
            <div class="stat-value">{study_time}</div>
            <div class="stat-label">Today's Study Time</div>
        </div>""", f"""<div class="stat-card">
            <div style="font-size: 40px;">🎯</div>
            <div class="stat-value">{goals}</div>
            <div class="stat-label">Active Goals</div>
        </div>""", f"""<div class="stat-card">
            <div style="font-size: 40px;">✅</div>
            <div class="stat-value">{tasks}</div>
            <div class="stat-label">Pending Tasks</div>
        </div>""", f"""<div class="stat-card">
            <div style="font-size: 40px;">📝</div>
            <div class="stat-value">{notes}</div>
            <div class="stat-label">Total Notes</div>
        </div>""")


def today_status():
    """Generate today's activity report"""
    try:
        today = datetime.now().date().isoformat()

        with open(LOG_FILE, 'r', newline='') as f:
            reader = csv.DictReader(f)
            activities = {}
            total_time = 0

            for row in reader:
                if row['date'] == today and row['user'] == current_user_email:
                    activity = row['activity']
                    seconds = int(row['seconds'])

                    if activity in activities:
                        activities[activity] += seconds
                    else:
                        activities[activity] = seconds

                    total_time += seconds

        if not activities:
            return "# 📊 Today's Report\n\n_No activities tracked yet today. Start tracking to see your report!_"

        output = f"# 📊 Today's Report - {datetime.now().strftime('%B %d, %Y')}\n\n"
        output += f"**Total Time Tracked:** {fmt(total_time)}\n\n"
        output += "## Activities Breakdown:\n\n"

        sorted_activities = sorted(activities.items(),
                                   key=lambda x: x[1],
                                   reverse=True)

        for activity, seconds in sorted_activities:
            percentage = (seconds / total_time * 100) if total_time > 0 else 0
            output += f"**{activity}:** {fmt(seconds)} ({percentage:.1f}%)\n"
            bar_length = int(percentage / 5)
            output += f"{'█' * bar_length}{'░' * (20 - bar_length)}\n\n"

        return output

    except Exception as e:
        return f"# 📊 Today's Report\n\n_No activities tracked yet. Start tracking!_"


def week_status():
    """Generate this week's activity report"""
    try:
        today = datetime.now().date()
        week_start = today - timedelta(days=today.weekday())

        with open(LOG_FILE, 'r', newline='') as f:
            reader = csv.DictReader(f)
            activities = {}
            daily_totals = {}
            total_time = 0

            for row in reader:
                if row['user'] != current_user_email:
                    continue

                date = datetime.fromisoformat(row['date']).date()

                if date >= week_start and date <= today:
                    activity = row['activity']
                    seconds = int(row['seconds'])
                    date_str = date.isoformat()

                    if activity in activities:
                        activities[activity] += seconds
                    else:
                        activities[activity] = seconds

                    if date_str in daily_totals:
                        daily_totals[date_str] += seconds
                    else:
                        daily_totals[date_str] = seconds

                    total_time += seconds

        if not activities:
            return "# 📈 This Week's Report\n\n_No activities tracked this week._"

        output = f"# 📈 This Week's Report\n\n"
        output += f"**Week:** {week_start.strftime('%B %d')} - {today.strftime('%B %d, %Y')}\n"
        output += f"**Total Time:** {fmt(total_time)}\n\n"

        output += "## Daily Summary:\n\n"
        for date_str in sorted(daily_totals.keys()):
            date_obj = datetime.fromisoformat(date_str).date()
            day_name = date_obj.strftime('%A')
            output += f"**{day_name} ({date_obj.strftime('%b %d')}):** {fmt(daily_totals[date_str])}\n"

        output += "\n## Activities:\n\n"
        sorted_activities = sorted(activities.items(),
                                   key=lambda x: x[1],
                                   reverse=True)

        for activity, seconds in sorted_activities:
            percentage = (seconds / total_time * 100) if total_time > 0 else 0
            output += f"**{activity}:** {fmt(seconds)} ({percentage:.1f}%)\n"

        return output

    except:
        return "# 📈 This Week's Report\n\n_No data available._"


def month_status():
    """Generate this month's activity report"""
    try:
        today = datetime.now().date()
        month_start = today.replace(day=1)

        with open(LOG_FILE, 'r', newline='') as f:
            reader = csv.DictReader(f)
            activities = {}
            total_time = 0

            for row in reader:
                if row['user'] != current_user_email:
                    continue

                date = datetime.fromisoformat(row['date']).date()

                if date >= month_start and date <= today:
                    activity = row['activity']
                    seconds = int(row['seconds'])

                    if activity in activities:
                        activities[activity] += seconds
                    else:
                        activities[activity] = seconds

                    total_time += seconds

        if not activities:
            return "# 📆 This Month's Report\n\n_No activities tracked this month._"

        output = f"# 📆 This Month's Report - {today.strftime('%B %Y')}\n\n"
        output += f"**Total Time:** {fmt(total_time)}\n\n"

        output += "## Activities:\n\n"
        sorted_activities = sorted(activities.items(),
                                   key=lambda x: x[1],
                                   reverse=True)

        for activity, seconds in sorted_activities:
            percentage = (seconds / total_time * 100) if total_time > 0 else 0
            output += f"**{activity}:** {fmt(seconds)} ({percentage:.1f}%)\n"

        return output

    except:
        return "# 📆 This Month's Report\n\n_No data available._"


# ================= WIKIPEDIA SEARCH - IMPROVED =================
def search_wikipedia(query):
    """Search Wikipedia and return clear, formatted summary"""
    if not query or not query.strip():
        return """# 🔍 Wikipedia Search

**How to use:** Enter any topic you want to learn about.

**Examples:**
- Photosynthesis
- World War 2
- Python Programming
- Albert Einstein
- Solar System

Type a topic above and click Search to get instant information!"""

    try:
        wikipedia.set_lang('en')

        # Get summary
        summary = wikipedia.summary(query, sentences=5, auto_suggest=True)
        page = wikipedia.page(query, auto_suggest=True)

        output = f"# 📚 {page.title}\n\n"
        output += "---\n\n"
        output += f"## Summary\n\n{summary}\n\n"
        output += "---\n\n"
        output += f"**📖 Read more:** [Full Wikipedia Article]({page.url})\n\n"
        output += f"**🔗 Source:** Wikipedia"

        return output

    except wikipedia.exceptions.DisambiguationError as e:
        output = f"# ⚠️ Multiple Topics Found\n\n"
        output += f"The term **'{query}'** could refer to multiple topics.\n\n"
        output += "Please be more specific and try one of these:\n\n"
        for i, option in enumerate(e.options[:8], 1):
            output += f"{i}. {option}\n"
        return output

    except wikipedia.exceptions.PageError:
        return f"""# ❌ No Results Found

Sorry, no Wikipedia page was found for **'{query}'**.

**Suggestions:**
- Check your spelling
- Try a different search term
- Use more general terms
- Search for the English name if applicable"""

    except Exception as e:
        return f"# ❌ Search Error\n\nAn error occurred while searching. Please try again.\n\n**Error:** {str(e)}"


# ================= NOTES FUNCTIONS - SHOW USER NAME =================
def save_note(note_text):
    """Save a note with user NAME instead of email"""
    global current_user_name, current_user_email

    if not note_text or not note_text.strip():
        return "⚠️ Please enter note content"

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Use name if available, fallback to email
    user_display = current_user_name if current_user_name else current_user_email if current_user_email else "Guest"

    with open(NOTES_FILE, 'a') as f:
        f.write(f"\n{'='*50}\n")
        f.write(f"Date: {timestamp}\n")
        f.write(f"Author: {user_display}\n"
                )  # Changed from "User:" to "Author:" and using name
        f.write(f"{'='*50}\n")
        f.write(f"{note_text.strip()}\n")

    return f"✅ Note saved at {timestamp}"


def view_notes():
    """View all saved notes"""
    try:
        with open(NOTES_FILE, 'r') as f:
            content = f.read()

        if not content.strip():
            return "# 📝 No notes yet\n\nSave your first note!"

        return f"# 📝 My Notes\n\n{content}"
    except:
        return "# 📝 No notes yet\n\nSave your first note!"


# ================= EMAIL REPORT =================
def send_email_report(parent_email):
    """Send daily report to parent"""
    global current_user_email, current_user_name

    if not parent_email or "@" not in parent_email:
        return "❌ Please enter a valid email address"

    try:
        report = today_status()

        msg = EmailMessage()
        msg["From"] = SENDER_EMAIL
        msg["To"] = parent_email
        msg["Subject"] = f"EXAM_EPS Daily Report - {datetime.now().strftime('%B %d, %Y')}"

        msg.set_content(f"""Daily Study Report

Student: {current_user_name or current_user_email or 'User'}
Date: {datetime.now().strftime('%B %d, %Y')}

{report}

---
Sent via EXAM_EPS
""")

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)

        return f"✅ Report sent to {parent_email}"

    except Exception as e:
        return f"❌ Failed to send email: {str(e)}"


# ================= TEAL TO GREEN GRADIENT COLOR SCHEME CSS =================
MODERN_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

:root {
    /* Core Background System - Teal to Green Gradient */
    --bg-main: #0A3D3D;
    --bg-secondary: #127A7A;
    --bg-card: #1FA8A8;
    --bg-input: #2DC5C5;

    /* Primary Brand Colors */
    --primary: #1FA8A8;
    --primary-button: #27D4D4;
    --primary-hover: #3DE8E8;
    --border-accent: #1FA8A8;

    /* Text Colors */
    --text-primary: #FFFFFF;
    --text-secondary: #E0F7F7;
    --text-muted: #A0D8D8;
    --text-placeholder: #6BB8B8;

    /* Semantic Colors */
    --success: #00FF9D;
    --warning: #FFB800;
    --error: #FF4444;
    --info: #27D4D4;
}

* {
    font-family: 'Inter', sans-serif !important;
}

body, .gradio-container {
    background: linear-gradient(135deg, #0A3D3D 0%, #127A7A 50%, #1FA8A8 100%) !important;
    color: var(--text-primary) !important;
    min-height: 100vh;
}

.timer-container {
    background: rgba(31, 168, 168, 0.2) !important;
    backdrop-filter: blur(20px) !important;
    border: 2px solid var(--border-accent) !important;
    border-radius: 20px !important;
    padding: 60px !important;
    margin: 30px auto !important;
    text-align: center !important;
    max-width: 700px !important;
    box-shadow: 0 20px 60px rgba(0, 255, 157, 0.2) !important;
}

.timer-container.active {
    border-color: var(--success) !important;
    box-shadow: 0 20px 60px rgba(0, 255, 157, 0.4) !important;
}

.timer-container.paused {
    border-color: var(--warning) !important;
}

.timer-text {
    font-family: 'Inter', monospace !important;
    font-size: 80px !important;
    font-weight: 800 !important;
    color: var(--text-primary) !important;
    letter-spacing: 8px !important;
    margin: 20px 0 !important;
    text-shadow: 0 0 30px rgba(39, 212, 212, 0.8) !important;
}

.timer-label {
    font-size: 24px !important;
    font-weight: 600 !important;
    color: var(--text-secondary) !important;
    text-transform: uppercase !important;
    letter-spacing: 3px !important;
}

.stat-card {
    background: rgba(31, 168, 168, 0.3) !important;
    backdrop-filter: blur(10px) !important;
    border: 1px solid var(--border-accent) !important;
    border-radius: 15px !important;
    padding: 25px !important;
    text-align: center !important;
    transition: all 0.3s ease !important;
}

.stat-card:hover {
    transform: translateY(-5px) !important;
    box-shadow: 0 10px 30px rgba(39, 212, 212, 0.3) !important;
}

.stat-value {
    font-size: 32px !important;
    font-weight: 700 !important;
    color: var(--text-primary) !important;
}

.stat-label {
    font-size: 14px !important;
    color: var(--text-muted) !important;
    margin-top: 5px !important;
}

button {
    background: rgba(39, 212, 212, 0.3) !important;
    color: var(--text-primary) !important;
    border: 1px solid var(--border-accent) !important;
    border-radius: 12px !important;
    padding: 14px 28px !important;
    font-weight: 600 !important;
    cursor: pointer !important;
    transition: all 0.3s !important;
}

button:hover {
    background: rgba(61, 232, 232, 0.4) !important;
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 20px rgba(39, 212, 212, 0.5) !important;
    border-color: var(--primary-hover) !important;
}

.primary-btn {
    background: linear-gradient(135deg, var(--primary-button), var(--primary-hover)) !important;
    border: none !important;
}

.primary-btn:hover {
    background: linear-gradient(135deg, var(--primary-hover), #4FFFFF) !important;
}

.danger-btn {
    background: linear-gradient(135deg, var(--error), #FF6666) !important;
    border: none !important;
}

.danger-btn:hover {
    background: linear-gradient(135deg, #FF6666, #FF8888) !important;
}

.warning-btn {
    background: linear-gradient(135deg, var(--warning), #FFCC33) !important;
    border: none !important;
}

.warning-btn:hover {
    background: linear-gradient(135deg, #FFCC33, #FFD966) !important;
}

.container, .block {
    background: rgba(31, 168, 168, 0.15) !important;
    backdrop-filter: blur(10px) !important;
    border: 1px solid rgba(31, 168, 168, 0.3) !important;
    border-radius: 15px !important;
    padding: 20px !important;
    margin: 10px 0 !important;
}

input, textarea, select {
    background: rgba(45, 197, 197, 0.2) !important;
    color: var(--text-primary) !important;
    border: 1px solid var(--border-accent) !important;
    border-radius: 10px !important;
    padding: 12px !important;
}

input::placeholder, textarea::placeholder {
    color: var(--text-placeholder) !important;
}

input:focus, textarea:focus, select:focus {
    border-color: var(--primary-hover) !important;
    box-shadow: 0 0 0 3px rgba(39, 212, 212, 0.3) !important;
    background: rgba(45, 197, 197, 0.3) !important;
    outline: none !important;
}

.markdown {
    color: var(--text-primary) !important;
}

.markdown h1 {
    color: var(--text-primary) !important;
    font-size: 36px !important;
    font-weight: 800 !important;
    margin-bottom: 20px !important;
    text-shadow: 0 0 20px rgba(39, 212, 212, 0.5) !important;
}

.markdown h2 {
    color: var(--text-secondary) !important;
    font-size: 28px !important;
    font-weight: 700 !important;
    margin: 20px 0 15px !important;
}

.markdown h3 {
    color: var(--text-secondary) !important;
    font-size: 22px !important;
    font-weight: 600 !important;
}

.tabs {
    background: rgba(31, 168, 168, 0.15) !important;
    border-radius: 15px !important;
    padding: 10px !important;
    backdrop-filter: blur(10px) !important;
}

.tab-nav button {
    background: transparent !important;
    color: var(--text-muted) !important;
    border: none !important;
}

.tab-nav button.selected {
    background: linear-gradient(135deg, var(--primary-button), var(--primary-hover)) !important;
    color: var(--text-primary) !important;
    box-shadow: 0 4px 15px rgba(39, 212, 212, 0.3) !important;
}

.activity-btn {
    min-width: 120px !important;
    margin: 5px !important;
}

/* Success, Warning, Error states for messages */
.markdown .success {
    color: var(--success) !important;
}

.markdown .warning {
    color: var(--warning) !important;
}

.markdown .error {
    color: var(--error) !important;
}

/* Scrollbar styling */
::-webkit-scrollbar {
    width: 12px;
}

::-webkit-scrollbar-track {
    background: rgba(10, 61, 61, 0.5);
}

::-webkit-scrollbar-thumb {
    background: var(--primary);
    border-radius: 6px;
}

::-webkit-scrollbar-thumb:hover {
    background: var(--primary-hover);
}
"""

# ================= GRADIO INTERFACE =================
with gr.Blocks(title="📚 EXAM_EPS - Smart Study Platform",
               css=MODERN_CSS) as app:
    user_email = gr.State("")

    # ============= LANDING PAGE =============
    with gr.Column(visible=True) as landing_page:
        gr.HTML("""
        <div style="text-align: center; padding: 60px 40px; background: rgba(31, 168, 168, 0.3); backdrop-filter: blur(20px); border-radius: 25px; margin-bottom: 30px; border: 2px solid #1FA8A8;">
            <div style="font-size: 64px; margin-bottom: 15px;">📚</div>
            <h1 style="color: #FFFFFF; margin: 0; font-size: 56px; font-weight: 800; text-shadow: 0 0 30px rgba(39, 212, 212, 0.8);">EXAM_EPS</h1>
            <p style="color: #E0F7F7; font-size: 20px; margin-top: 15px; font-weight: 500;">Smart Study & Exam Management System</p>
        </div>
        """)

        with gr.Tabs():
            with gr.TabItem("✨ Sign Up"):
                gr.Markdown("### 📝 Create Your Account")
                signup_name = gr.Textbox(label="👤 Full Name",
                                         placeholder="Enter your name")
                signup_email = gr.Textbox(label="📧 Email",
                                          placeholder="your@email.com")
                signup_btn = gr.Button("🚀 Create Account",
                                       elem_classes="primary-btn")
                signup_output = gr.Markdown(
                    "ℹ️ Enter your details to create an account")

            with gr.TabItem("🔐 Login"):
                gr.Markdown("### 🔑 Login to Dashboard")
                login_email = gr.Textbox(label="📧 Email",
                                         placeholder="your@email.com")
                login_password = gr.Textbox(label="🔒 Password",
                                            type="password",
                                            placeholder="Your password")
                login_btn = gr.Button("🚀 Login", elem_classes="primary-btn")
                login_output = gr.Markdown("ℹ️ Enter your credentials")

            with gr.TabItem("👑 Admin"):
                gr.Markdown("### 👑 Admin Access")
                admin_key = gr.Textbox(label="Admin Key",
                                       type="password",
                                       placeholder="Enter admin key")
                admin_login_btn = gr.Button("🔓 Admin Login",
                                            elem_classes="danger-btn")
                admin_output = gr.Markdown("⚠️ Authorized personnel only")

    # ============= ADMIN PAGE =============
    with gr.Column(visible=False) as admin_page:
        gr.Markdown("# 👑 Admin Panel")

        with gr.Tabs():
            with gr.TabItem("👥 All Users"):
                refresh_all_btn = gr.Button("🔄 Refresh All Users")
                all_users_display = gr.Markdown("Loading...")

            with gr.TabItem("🟢 Active Users"):
                refresh_active_btn = gr.Button("🔄 Refresh Active Users")
                active_users_display = gr.Markdown("Loading...")

            with gr.TabItem("🚫 Block User"):
                gr.Markdown("### Block User Account")
                block_email = gr.Textbox(label="User Email",
                                         placeholder="user@example.com")
                block_reason = gr.Textbox(label="Reason",
                                          placeholder="Violation of terms",
                                          value="No reason provided")
                block_btn = gr.Button("🚫 Block User",
                                      elem_classes="danger-btn")
                block_output = gr.Markdown("")

            with gr.TabItem("✅ Unblock User"):
                gr.Markdown("### Unblock User Account")
                unblock_email = gr.Textbox(label="User Email",
                                           placeholder="user@example.com")
                unblock_btn = gr.Button("✅ Unblock User",
                                        elem_classes="primary-btn")
                unblock_output = gr.Markdown("")

        back_to_landing_btn = gr.Button("⬅️ Back to Main")

    # ============= USER DASHBOARD =============
    with gr.Column(visible=False) as dashboard_page:
        with gr.Row():
            user_welcome = gr.HTML(
                "<h2 style='color: #FFFFFF; font-weight: 700;'>👋 Welcome!</h2>"
            )
            logout_btn = gr.Button("🚪 Logout",
                                   size="sm",
                                   elem_classes="danger-btn")

        # Dashboard header
        gr.HTML("""
        <div style="text-align: center; padding: 30px; background: rgba(31, 168, 168, 0.3); backdrop-filter: blur(20px); border-radius: 20px; margin-bottom: 20px; border: 2px solid #1FA8A8;">
            <div style="font-size: 48px; margin-bottom: 10px;">📚</div>
            <h1 style="color: #FFFFFF; margin: 0; font-size: 42px; font-weight: 800; text-shadow: 0 0 30px rgba(39, 212, 212, 0.8);">EXAM_EPS</h1>
            <p style="color: #E0F7F7; margin-top: 10px; font-size: 18px;">Dashboard</p>
        </div>
        """)

        # Stats cards - ALL 4 CARDS (restored and working)
        with gr.Row():
            stat_study_time = gr.HTML("""
            <div class="stat-card">
                <div style="font-size: 40px;">⏱️</div>
                <div class="stat-value">0h 0m</div>
                <div class="stat-label">Today's Study Time</div>
            </div>
            """)
            stat_goals = gr.HTML("""
            <div class="stat-card">
                <div style="font-size: 40px;">🎯</div>
                <div class="stat-value">0</div>
                <div class="stat-label">Active Goals</div>
            </div>
            """)
            stat_tasks = gr.HTML("""
            <div class="stat-card">
                <div style="font-size: 40px;">✅</div>
                <div class="stat-value">0</div>
                <div class="stat-label">Pending Tasks</div>
            </div>
            """)
            stat_notes = gr.HTML("""
            <div class="stat-card">
                <div style="font-size: 40px;">📝</div>
                <div class="stat-value">0</div>
                <div class="stat-label">Total Notes</div>
            </div>
            """)

        # Timer
        timer_display = gr.HTML(get_timer_html())

        # Activity buttons
        gr.Markdown("### 🎯 Select Activity")
        with gr.Row():
            activity_buttons = []
            for i, activity in enumerate(ACTIVITY_OPTIONS[:3]):
                btn = gr.Button(f"📚 {activity}",
                                elem_classes="activity-btn primary-btn")
                activity_buttons.append(btn)

        with gr.Row():
            for i, activity in enumerate(ACTIVITY_OPTIONS[3:6]):
                btn = gr.Button(f"📚 {activity}",
                                elem_classes="activity-btn primary-btn")
                activity_buttons.append(btn)

        with gr.Row():
            for i, activity in enumerate(ACTIVITY_OPTIONS[6:]):
                btn = gr.Button(f"📚 {activity}",
                                elem_classes="activity-btn primary-btn")
                activity_buttons.append(btn)

        # Control buttons
        with gr.Row():
            pause_btn = gr.Button("⏸️ Pause",
                                  elem_classes="warning-btn",
                                  scale=1)
            stop_btn = gr.Button("⏹️ Stop & Save",
                                 elem_classes="danger-btn",
                                 scale=1)

        output = gr.Markdown(
            "**Activity Status**\n\n_Select an activity to start tracking_")

        with gr.Tabs():
            with gr.TabItem("📊 Dashboard"):
                gr.Markdown("### 📊 Reports")
                with gr.Row():
                    today_btn = gr.Button("📅 Today's Report")
                    week_btn = gr.Button("📈 Weekly Report")
                    month_btn = gr.Button("📆 Monthly Report")

                report_display = gr.Markdown(
                    "Click a button above to view reports")

                # Email report
                with gr.Accordion("📧 Email Daily Report", open=False):
                    parent_email = gr.Textbox(label="Parent's Email",
                                              placeholder="parent@example.com")
                    email_btn = gr.Button("📤 Send Report")
                    email_output = gr.Markdown("")

            with gr.TabItem("🎯 Goals"):
                gr.Markdown("### 🎯 Goal Management")

                with gr.Row():
                    with gr.Column():
                        goal_text = gr.Textbox(
                            label="Goal",
                            placeholder="e.g., Score 95% in Math",
                            lines=2)
                        goal_deadline = gr.Textbox(label="Deadline (Optional)",
                                                   placeholder="2024-12-31")
                        add_goal_btn = gr.Button("➕ Add Goal",
                                                 elem_classes="primary-btn")
                        add_goal_output = gr.Markdown("")

                    with gr.Column():
                        goal_id_complete = gr.Textbox(
                            label="Goal ID to Complete",
                            placeholder="Enter ID")
                        complete_goal_btn = gr.Button(
                            "✅ Mark Complete", elem_classes="primary-btn")
                        goal_id_delete = gr.Textbox(label="Goal ID to Delete",
                                                    placeholder="Enter ID")
                        delete_goal_btn = gr.Button("🗑️ Delete Goal",
                                                    elem_classes="danger-btn")

                goal_action_output = gr.Markdown("")

                gr.Markdown("---")
                view_goals_btn = gr.Button("🔄 Refresh Goals")
                goals_display = gr.Markdown("Click 'Refresh Goals' to view")

            with gr.TabItem("📝 Tasks"):
                gr.Markdown("### ✅ Task Management")

                with gr.Row():
                    with gr.Column():
                        task_text = gr.Textbox(
                            label="Task",
                            placeholder="e.g., Complete homework",
                            lines=2)
                        task_priority = gr.Radio(
                            choices=["High", "Medium", "Low"],
                            label="Priority",
                            value="Medium")
                        add_task_btn = gr.Button("➕ Add Task",
                                                 elem_classes="primary-btn")
                        add_task_output = gr.Markdown("")

                    with gr.Column():
                        task_id_complete = gr.Textbox(
                            label="Task ID to Complete",
                            placeholder="Enter ID")
                        complete_task_btn = gr.Button(
                            "✅ Mark Complete", elem_classes="primary-btn")
                        task_id_delete = gr.Textbox(label="Task ID to Delete",
                                                    placeholder="Enter ID")
                        delete_task_btn = gr.Button("🗑️ Delete Task",
                                                    elem_classes="danger-btn")

                task_action_output = gr.Markdown("")

                gr.Markdown("---")
                view_tasks_btn = gr.Button("🔄 Refresh Tasks")
                tasks_display = gr.Markdown("Click 'Refresh Tasks' to view")

            with gr.TabItem("📝 Notes"):
                gr.Markdown("### 📝 Notes")
                note_input = gr.Textbox(label="Write a note",
                                        lines=5,
                                        placeholder="Enter your notes here...")
                with gr.Row():
                    save_note_btn = gr.Button("💾 Save Note",
                                              elem_classes="primary-btn")
                    view_notes_btn = gr.Button("👁️ View All Notes")

                notes_output = gr.Markdown("")

            with gr.TabItem("🔍 Search"):
                gr.Markdown("### 🔍 Wikipedia Search")
                search_input = gr.Textbox(
                    label="Search Topic",
                    placeholder=
                    "e.g., Photosynthesis, World War 2, Python Programming")
                search_btn = gr.Button("🔎 Search", elem_classes="primary-btn")
                search_output = gr.Markdown("Enter a topic to search")

    # ================= EVENT HANDLERS =================

    # Signup
    signup_btn.click(create_account,
                     inputs=[signup_name, signup_email],
                     outputs=signup_output).then(
                         lambda: ("", ""), outputs=[signup_name, signup_email])

    # Login
    def handle_login(email, password):
        success, message = authenticate_user(email, password)
        if success:
            welcome = f"<h2 style='color: #FFFFFF; font-weight: 700;'>👋 Welcome, {current_user_name}!</h2>"

            # Get updated stats
            study_html, goals_html, tasks_html, notes_html = get_stats_html()

            return (message, gr.update(visible=False), gr.update(visible=True),
                    email, welcome, study_html, goals_html, tasks_html,
                    notes_html)
        return (
            message, gr.update(visible=True), gr.update(visible=False), "",
            "<h2 style='color: #FFFFFF; font-weight: 700;'>👋 Welcome!</h2>",
            """<div class="stat-card">
                <div style="font-size: 40px;">⏱️</div>
                <div class="stat-value">0h 0m</div>
                <div class="stat-label">Today's Study Time</div>
            </div>""", """<div class="stat-card">
                <div style="font-size: 40px;">🎯</div>
                <div class="stat-value">0</div>
                <div class="stat-label">Active Goals</div>
            </div>""", """<div class="stat-card">
                <div style="font-size: 40px;">✅</div>
                <div class="stat-value">0</div>
                <div class="stat-label">Pending Tasks</div>
            </div>""", """<div class="stat-card">
                <div style="font-size: 40px;">📝</div>
                <div class="stat-value">0</div>
                <div class="stat-label">Total Notes</div>
            </div>""")

    login_btn.click(handle_login,
                    inputs=[login_email, login_password],
                    outputs=[
                        login_output, landing_page, dashboard_page, user_email,
                        user_welcome, stat_study_time, stat_goals, stat_tasks,
                        stat_notes
                    ]).then(lambda: ("", ""),
                            outputs=[login_email, login_password])

    # Admin login
    def handle_admin_login(key):
        if key == ADMIN_KEY:
            return (gr.update(visible=False), gr.update(visible=True),
                    "✅ Admin access granted")
        return (gr.update(visible=True), gr.update(visible=False),
                "❌ Invalid admin key")

    admin_login_btn.click(handle_admin_login,
                          inputs=admin_key,
                          outputs=[landing_page, admin_page, admin_output
                                   ]).then(get_all_users,
                                           outputs=all_users_display).then(
                                               get_active_users,
                                               outputs=active_users_display)

    # Admin actions
    refresh_all_btn.click(get_all_users, outputs=all_users_display)
    refresh_active_btn.click(get_active_users, outputs=active_users_display)

    block_btn.click(block_user,
                    inputs=[block_email, block_reason],
                    outputs=block_output).then(
                        lambda: ("", "No reason provided"),
                        outputs=[block_email,
                                 block_reason]).then(get_all_users,
                                                     outputs=all_users_display)

    unblock_btn.click(unblock_user,
                      inputs=unblock_email,
                      outputs=unblock_output).then(
                          lambda: "", outputs=unblock_email).then(
                              get_all_users, outputs=all_users_display)

    back_to_landing_btn.click(
        lambda: [gr.update(visible=True),
                 gr.update(visible=False)],
        outputs=[landing_page, admin_page])

    # Logout
    def handle_logout():
        global current_user_email, current_user_name
        current_user_email = None
        current_user_name = None
        return (
            gr.update(visible=True), gr.update(visible=False), "",
            "<h2 style='color: #FFFFFF; font-weight: 700;'>👋 Welcome!</h2>")

    logout_btn.click(
        handle_logout,
        outputs=[landing_page, dashboard_page, user_email, user_welcome])

    # Activity tracking - button click handlers
    for i, btn in enumerate(activity_buttons):
        activity_name = ACTIVITY_OPTIONS[i]
        btn.click(start_activity,
                  inputs=gr.State(activity_name),
                  outputs=[output, timer_display])

    def stop_and_refresh():
        """Stop activity and refresh stats"""
        msg, timer_html = stop_activity()
        study_html, goals_html, tasks_html, notes_html = get_stats_html()
        return msg, timer_html, study_html, goals_html, tasks_html, notes_html

    pause_btn.click(pause_activity, outputs=[output, timer_display])
    stop_btn.click(stop_and_refresh,
                   outputs=[
                       output, timer_display, stat_study_time, stat_goals,
                       stat_tasks, stat_notes
                   ])

    # Reports
    today_btn.click(today_status, outputs=report_display)
    week_btn.click(week_status, outputs=report_display)
    month_btn.click(month_status, outputs=report_display)

    # Notes
    def save_note_and_refresh(note_text):
        """Save note and refresh stats"""
        msg = save_note(note_text)
        _, _, _, notes_html = get_stats_html()
        return msg, notes_html

    save_note_btn.click(save_note_and_refresh,
                        inputs=note_input,
                        outputs=[notes_output,
                                 stat_notes]).then(lambda: "",
                                                   outputs=note_input)

    view_notes_btn.click(view_notes, outputs=notes_output)

    # Wikipedia
    search_btn.click(search_wikipedia,
                     inputs=search_input,
                     outputs=search_output)

    # Email
    email_btn.click(send_email_report,
                    inputs=parent_email,
                    outputs=email_output)

    # Goals
    def add_goal_and_refresh(goal_text, goal_deadline):
        """Add goal and refresh stats"""
        msg = add_goal(goal_text, goal_deadline)
        _, goals_html, _, _ = get_stats_html()
        return msg, goals_html

    def complete_goal_and_refresh(goal_id):
        """Complete goal and refresh stats"""
        msg = complete_goal(goal_id)
        _, goals_html, _, _ = get_stats_html()
        return msg, goals_html

    def delete_goal_and_refresh(goal_id):
        """Delete goal and refresh stats"""
        msg = delete_goal(goal_id)
        _, goals_html, _, _ = get_stats_html()
        return msg, goals_html

    add_goal_btn.click(add_goal_and_refresh,
                       inputs=[goal_text, goal_deadline],
                       outputs=[add_goal_output, stat_goals
                                ]).then(lambda: ("", ""),
                                        outputs=[goal_text, goal_deadline])

    complete_goal_btn.click(complete_goal_and_refresh,
                            inputs=goal_id_complete,
                            outputs=[goal_action_output, stat_goals
                                     ]).then(lambda: "",
                                             outputs=goal_id_complete)

    delete_goal_btn.click(delete_goal_and_refresh,
                          inputs=goal_id_delete,
                          outputs=[goal_action_output,
                                   stat_goals]).then(lambda: "",
                                                     outputs=goal_id_delete)

    view_goals_btn.click(view_goals, outputs=goals_display)

    # Tasks
    def add_task_and_refresh(task_text, task_priority):
        """Add task and refresh stats"""
        msg = add_task(task_text, task_priority)
        _, _, tasks_html, _ = get_stats_html()
        return msg, tasks_html

    def complete_task_and_refresh(task_id):
        """Complete task and refresh stats"""
        msg = complete_task(task_id)
        _, _, tasks_html, _ = get_stats_html()
        return msg, tasks_html

    def delete_task_and_refresh(task_id):
        """Delete task and refresh stats"""
        msg = delete_task(task_id)
        _, _, tasks_html, _ = get_stats_html()
        return msg, tasks_html

    add_task_btn.click(add_task_and_refresh,
                       inputs=[task_text, task_priority],
                       outputs=[add_task_output,
                                stat_tasks]).then(lambda: "",
                                                  outputs=task_text)

    complete_task_btn.click(complete_task_and_refresh,
                            inputs=task_id_complete,
                            outputs=[task_action_output, stat_tasks
                                     ]).then(lambda: "",
                                             outputs=task_id_complete)

    delete_task_btn.click(delete_task_and_refresh,
                          inputs=task_id_delete,
                          outputs=[task_action_output,
                                   stat_tasks]).then(lambda: "",
                                                     outputs=task_id_delete)

    view_tasks_btn.click(view_tasks, outputs=tasks_display)


    # Live timer updates
    timer_update = gr.Timer(1)
    timer_update.tick(get_timer_html, outputs=timer_display)

    # Stats refresh timer (every 5 seconds)
    stats_update = gr.Timer(5)
    stats_update.tick(
        get_stats_html,
        outputs=[stat_study_time, stat_goals, stat_tasks, stat_notes])

# Launch
# PORT FIX: Add this at the very end of your file, replacing the existing launch code

# Launch with automatic port detection
if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("🚀 EXAM_EPS - Smart Study Tracker")
    print("=" * 60)
    print("\n📧 Email: exam.eps12@gmail.com")
    print("🔑 Admin Key: EXAM_ADMIN_2024")
    print(f"💾 Data Directory: {BASE_DIR}")
    print("\n" + "=" * 60 + "\n")

    # Try ports 7860-7869 until one is available
    launch_successful = False
    for port in range(7860, 7870):
        try:
            print(f"🔍 Trying port {port}...")
            app.launch(
                server_name="0.0.0.0",
                server_port=port,
                share=True,
                inbrowser=True
            )
            launch_successful = True
            break
        except OSError as e:
            if "Cannot find empty port" in str(e) or "Address already in use" in str(e):
                print(f"⚠️  Port {port} is busy, trying next port...")
                continue
            else:
                raise  # Re-raise if it's a different error
    
    if not launch_successful:
        print("\n❌ Could not find available port in range 7860-7869")
        print("💡 Try running: pkill -f gradio")
        print("   Or restart your environment")
