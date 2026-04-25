from flask import Flask, render_template, request, redirect, url_for, session, flash
from models import db, User, Ticket
from werkzeug.security import generate_password_hash, check_password_hash
import random, string
import urllib.parse
from utils import generate_otp, send_sms_otp
from datetime import datetime


app = Flask(__name__)
 
# urllib handles the @ symbol automatically.
raw_password = "pujitha@2007" 
encoded_password = urllib.parse.quote_plus(raw_password) 

app.config['SQLALCHEMY_DATABASE_URI'] = f'mysql+mysqlconnector://root:{encoded_password}@localhost/smart_gov_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = "secure_key_456"
db.init_app(app)

# Create tables in MySQL Workbench automatically
with app.app_context():
    db.create_all()

# --- HELPERS ---
def generate_captcha():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))

# --- ROUTES ---

@app.route('/')
def home():
    captcha = generate_captcha()
    return render_template('login.html', captcha=captcha)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        fname = request.form.get('fname')
        lname = request.form.get('lname')
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        role = request.form.get('role')

        if password != confirm_password:
            flash("Passwords do not match!")
            return redirect(url_for('signup'))

        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash("Username already exists!")
            return redirect(url_for('signup'))

        hashed_pw = generate_password_hash(password)
        new_user = User(
            first_name=fname,
            last_name=lname,
            username=username,
            password=hashed_pw,
            role=role
        )
        db.session.add(new_user)
        db.session.commit()
        flash("Registration successful! Please login.")
        return redirect(url_for('home'))
    return render_template('signup.html')


@app.route('/send_otp', methods=['POST'])
def send_otp_route():
    username = request.form.get('username')
    if not username:
        flash("Please enter mobile/email first.")
        return redirect(url_for('home'))

    # 1. Generate OTP
    otp = generate_otp()
    session['generated_otp'] = otp
    session['user_attempting_login'] = username
    session['otp_sent'] = True

    # 2. SEND OTP TO BROWSER POPUP
    # This stores the OTP in a flash message that JavaScript can read
    flash(f"{otp}", "browser_otp")
    
    # Optional: Keep the terminal print if you want to see it there too
    print(f"Terminal backup: OTP is {otp}") 
    
    return redirect(url_for('home'))

@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')
    user_otp = request.form.get('otp_input')
    actual_otp = session.get('generated_otp')
    
    # 1. Check OTP First
    if user_otp != actual_otp:
        flash("Invalid OTP! Try again.")
        return redirect(url_for('home'))

    # 2. Check Captcha
    user_captcha = request.form.get('captcha_input')
    actual_captcha = request.form.get('actual_captcha')
    if user_captcha.upper() != actual_captcha.upper():
        flash("Invalid CAPTCHA!")
        return redirect(url_for('home'))

    # 3. Check User Credentials
    user = User.query.filter_by(username=username).first()
    if user and check_password_hash(user.password, password):
        # Clear OTP data from session after success
        session.pop('otp_sent', None)
        session.pop('generated_otp', None)
        
        session['user_id'] = user.id
        session['role'] = user.role
        session['name'] = user.first_name
        
        if user.role == 'staff':
            return redirect(url_for('staff_dashboard'))
        return redirect(url_for('dashboard'))
    
    flash("Invalid username or password")
    return redirect(url_for('home'))

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        username = request.form.get('username')
        new_pw = request.form.get('new_password')
        user = User.query.filter_by(username=username).first()
        if user:
            user.password = generate_password_hash(new_pw)
            db.session.commit()
            flash("Password reset successful!")
            return redirect(url_for('home'))
        flash("User not found.")
    return render_template('forgot_password.html')

# --- CITIZEN DASHBOARD ---

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session: return redirect(url_for('home'))
    
    # 1. Get the current active ticket for this user
    ticket = Ticket.query.filter(Ticket.user_id == session['user_id'], Ticket.status != 'Completed').first()
    
    pos = None
    wait_time = 0
    
    if ticket:
        if ticket.status == 'Waiting':
            # 2. Position logic: Count how many tickets of the same office are WAITING and were created BEFORE this one
            # We also prioritize the 'is_priority' users
            all_waiting = Ticket.query.filter_by(
                status='Waiting', 
                state=ticket.state, 
                district=ticket.district
            ).order_by(Ticket.is_priority.desc(), Ticket.created_at.asc()).all()
            
            try:
                # Find index in the sorted list
                pos = all_waiting.index(ticket) + 1
                # 3. Calculation: (People ahead) * 15 minutes
                wait_time = (pos - 1) * 15 
            except ValueError:
                pos = 1
                wait_time = 0
        else:
            # If status is 'Serving', position is effectively 0
            pos = 0
            wait_time = 0

    return render_template('dashboard.html', ticket=ticket, position=pos, wait_time=wait_time)

@app.route('/book_ticket', methods=['POST'])
def book_ticket():
    if 'user_id' not in session: return redirect(url_for('home'))
    
    state = request.form.get('state')
    district = request.form.get('district')
    purpose = request.form.get('purpose')
    is_priority = 'priority' in request.form
    
    # Logic to generate a unique token
    # Example: AP-VIS-101 (Andhra Pradesh - Visakhapatnam)
    state_code = state[:2].upper()
    dist_code = district[:3].upper()
    
    count = Ticket.query.filter_by(state=state, district=district).count()
    token_no = f"{state_code}-{dist_code}-{101+count}"
    
    new_ticket = Ticket(
        user_id=session['user_id'],
        token_number=token_no,
        purpose=purpose,
        state=state,
        district=district,
        is_priority=is_priority
    )
    db.session.add(new_ticket)
    db.session.commit()
    return redirect(url_for('dashboard'))

# --- STAFF DASHBOARD ---

@app.route('/staff/dashboard')
def staff_dashboard():
    if session.get('role') != 'staff': return "Access Denied"
    
    current = Ticket.query.filter_by(status='Serving').first()
    waiting = Ticket.query.filter_by(status='Waiting').order_by(Ticket.is_priority.desc(), Ticket.created_at.asc()).all()
    
    return render_template('staff_dashboard.html', current=current, waiting=waiting)

@app.route('/staff/call_next/<int:ticket_id>')
def call_next(ticket_id):
    if session.get('role') != 'staff': return "Access Denied"

    # Complete current person if any
    Ticket.query.filter_by(status='Serving').update({'status': 'Completed'})
    
    # Accept new person
    ticket = Ticket.query.get(ticket_id)
    if ticket:
        ticket.status = 'Serving'
        db.session.commit()
        
        # Reminder Logic: Notify the next 2 people in line
        next_in_line = Ticket.query.filter_by(status='Waiting').order_by(Ticket.is_priority.desc(), Ticket.created_at.asc()).limit(2).all()
        for person in next_in_line:
            print(f"SMS ALERT to {person.user.username}: Your turn is near! Only {next_in_line.index(person)+1} people ahead.")

    return redirect(url_for('staff_dashboard'))

@app.route('/staff/complete/<int:ticket_id>')
def complete(ticket_id):
    ticket = Ticket.query.get(ticket_id)
    if ticket:
        ticket.status = 'Completed'
        db.session.commit()
    return redirect(url_for('staff_dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True)