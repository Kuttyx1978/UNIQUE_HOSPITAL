from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

app = Flask(__name__)
app.secret_key = "unique_hospital_premium_2026"

# --- DEPLOYMENT PATHS ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "hospital.db")

# --- EMAIL CONFIG ---
HOSPITAL_EMAIL = "uniquehospitals@gmail.com"     # Update this
HOSPITAL_APP_PASSWORD = "Gaamch2006&" # Update this

# --- STAFF CREDENTIALS (UPDATED) ---
DOCTORS = {
    'ram': {'name': 'Dr. Ram (Cardiology)', 'pass': 'doc123'},
    'priya': {'name': 'Dr. Priya (Neurology)', 'pass': 'doc123'},
    'shiva': {'name': 'Dr. Shiva (General)', 'pass': 'doc123'}
}

def send_confirmation_email(patient_email, patient_name, doctor, date, time, fee):
    try:
        msg = MIMEMultipart()
        msg['From'] = f"Unique Hospital <{HOSPITAL_EMAIL}>"
        msg['To'] = patient_email
        msg['Subject'] = "Appointment Confirmed - Unique Hospital"
        body = f"Hello {patient_name},\n\nYour 15-minute consultation is confirmed.\n\nDoctor: {doctor}\nDate: {date}\nTime: {time}\nFee: ₹{fee}\n\nPlease arrive 10 minutes early.\n\nStay Healthy,\nUnique Hospital"
        msg.attach(MIMEText(body, 'plain'))
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(HOSPITAL_EMAIL, HOSPITAL_APP_PASSWORD)
        server.sendmail(HOSPITAL_EMAIL, patient_email, msg.as_string())
        server.quit()
    except Exception as e: print(f"Email Error: {e}")

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, email TEXT UNIQUE, password TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS appointments (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, patient_name TEXT, age INTEGER, phone TEXT, doctor TEXT, date TEXT, time TEXT, reason TEXT, fee TEXT)")
    conn.commit(); conn.close()

init_db()

# --- PATIENT ROUTES ---
@app.route('/')
def index(): return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        hashed_pw = generate_password_hash(request.form['password'])
        try:
            conn = sqlite3.connect(DB_NAME); cur = conn.cursor()
            cur.execute("INSERT INTO users (name, email, password) VALUES (?, ?, ?)", (request.form['name'], request.form['email'], hashed_pw))
            conn.commit(); conn.close()
            return redirect(url_for('patient_login'))
        except: flash("Email already registered.", "danger")
    return render_template('register.html')

@app.route('/patient_login', methods=['GET', 'POST'])
def patient_login():
    if request.method == 'POST':
        conn = sqlite3.connect(DB_NAME); cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE email=?", (request.form['email'],))
        user = cur.fetchone(); conn.close()
        if user and check_password_hash(user[3], request.form['password']):
            session['user_id'], session['user_name'] = user[0], user[1]
            return redirect(url_for('index'))
        flash("Invalid credentials.", "danger")
    return render_template('patient_login.html')

@app.route('/book', methods=['GET', 'POST'])
def book_appointment():
    if 'user_id' not in session: return redirect(url_for('patient_login'))
    conn = sqlite3.connect(DB_NAME); cur = conn.cursor()
    
    if request.method == 'POST':
        u_id = session['user_id']
        name, age, phone = request.form['name'], request.form['age'], request.form['phone']
        doctor, date, time = request.form['doctor'], request.form['date'], request.form['time']
        reason, fee = request.form['reason'], request.form.get('fee', '500')
        cur.execute("INSERT INTO appointments (user_id, patient_name, age, phone, doctor, date, time, reason, fee) VALUES (?,?,?,?,?,?,?,?,?)", (u_id, name, age, phone, doctor, date, time, reason, fee))
        appt_id = cur.lastrowid
        cur.execute("SELECT email FROM users WHERE id=?", (u_id,))
        email = cur.fetchone()[0]; conn.commit(); conn.close()
        send_confirmation_email(email, name, doctor, date, time, fee)
        return redirect(url_for('booking_success', id=appt_id))
    
    cur.execute("SELECT doctor, date, time FROM appointments")
    booked = cur.fetchall(); conn.close()
    
    # Pre-fill data if passed from homepage quick-book widget
    pre_name = request.args.get('patient_name', session.get('user_name', ''))
    pre_loc = request.args.get('location', '')
    pre_phone = request.args.get('phone', '')
    pre_date = request.args.get('date', '')
    
    return render_template('book.html', 
                           default_name=pre_name, 
                           booked_slots=booked,
                           pre_phone=pre_phone,
                           pre_date=pre_date)

@app.route('/my_appointments')
def my_appointments():
    if 'user_id' not in session: return redirect(url_for('patient_login'))
    conn = sqlite3.connect(DB_NAME); cur = conn.cursor()
    cur.execute("SELECT * FROM appointments WHERE user_id=? ORDER BY date DESC, time DESC", (session['user_id'],))
    appts = cur.fetchall(); conn.close()
    return render_template('my_appointments.html', appointments=appts)

@app.route('/booking_success')
def booking_success(): 
    appt_id = request.args.get('id')
    return render_template('booking_success.html', appt_id=appt_id)

@app.route('/receipt/<int:id>')
def view_receipt(id):
    if 'user_id' not in session: return redirect(url_for('patient_login'))
    conn = sqlite3.connect(DB_NAME); cur = conn.cursor()
    cur.execute("SELECT * FROM appointments WHERE id=? AND user_id=?", (id, session['user_id']))
    appt = cur.fetchone(); conn.close()
    if not appt: return redirect(url_for('index'))
    
    appointment_data = {
        'id': appt[0],
        'patient_name': appt[2],
        'age': appt[3],
        'phone': appt[4],
        'doctor': appt[5],
        'date': appt[6],
        'time': appt[7],
        'fee': appt[9]
    }
    return render_template('receipt.html', appointment=appointment_data)

# --- DOCTOR ROUTES ---
@app.route('/doctor_login', methods=['GET', 'POST'])
def doctor_login():
    if request.method == 'POST':
        username = request.form['username'].lower().strip()
        password = request.form['password']
        if username in DOCTORS and DOCTORS[username]['pass'] == password:
            session['doctor_logged_in'] = True
            session['doctor_name'] = DOCTORS[username]['name']
            return redirect(url_for('doctor_dashboard'))
        flash("Invalid Doctor Credentials", "danger")
    return render_template('doctor_login.html')

@app.route('/doctor_dashboard')
def doctor_dashboard():
    if not session.get('doctor_logged_in'): return redirect(url_for('doctor_login'))
    conn = sqlite3.connect(DB_NAME); cur = conn.cursor()
    cur.execute("SELECT * FROM appointments WHERE doctor=? ORDER BY date ASC, time ASC", (session['doctor_name'],))
    appts = cur.fetchall(); conn.close()
    return render_template('doctor_dashboard.html', appointments=appts, doc_name=session['doctor_name'])

# --- ADMIN ROUTES ---
@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        if request.form['username'] == 'admin' and request.form['password'] == 'admin123':
            session['admin_logged_in'] = True
            return redirect(url_for('records'))
        flash("Invalid Admin Credentials", "danger")
    return render_template('admin_login.html')

@app.route('/records')
def records():
    if not session.get('admin_logged_in'): return redirect(url_for('admin_login'))
    conn = sqlite3.connect(DB_NAME); cur = conn.cursor()
    cur.execute("SELECT * FROM appointments ORDER BY date DESC")
    all_appts = cur.fetchall(); conn.close()
    return render_template('records.html', records=all_appts)

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit_record(id):
    if not session.get('admin_logged_in'): return redirect(url_for('admin_login'))
    conn = sqlite3.connect(DB_NAME); cur = conn.cursor()
    if request.method == 'POST':
        name = request.form['name']
        date = request.form['date']
        time = request.form['time']
        reason = request.form['reason']
        fee = request.form['fee']
        cur.execute("UPDATE appointments SET patient_name=?, date=?, time=?, reason=?, fee=? WHERE id=?", (name, date, time, reason, fee, id))
        conn.commit(); conn.close()
        return redirect(url_for('records'))
    cur.execute("SELECT * FROM appointments WHERE id=?", (id,))
    record = cur.fetchone(); conn.close()
    return render_template('edit.html', record=record)

@app.route('/cancel_appointment/<int:id>')
def cancel_appointment(id):
    conn = sqlite3.connect(DB_NAME); cur = conn.cursor()
    cur.execute("DELETE FROM appointments WHERE id=?", (id,))
    conn.commit(); conn.close()
    if session.get('admin_logged_in'): return redirect(url_for('records'))
    if session.get('doctor_logged_in'): return redirect(url_for('doctor_dashboard'))
    return redirect(url_for('my_appointments'))

@app.route('/logout')
def logout(): 
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__': app.run(debug=True)