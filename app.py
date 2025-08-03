from flask import Flask, render_template, request, redirect, session, url_for, jsonify, send_file
import mysql.connector
import random
import string
import csv
import io
import bcrypt

# ✅ Initialize Flask app
app = Flask(__name__)
app.secret_key = 'insuready_secret_key'
app.permanent_session_lifetime = 300  # 5 minutes

# ✅ MySQL connection
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",
    database="insuready"
)
cursor = db.cursor(dictionary=True)

# ✅ Home page
@app.route('/')
def home():
    return render_template("index.html")

# ✅ Login route with role handling
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        email = request.form['email']
        password_input = request.form['password']

        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()

        if user:
            stored_hash = user['password'].encode('utf-8')
            if bcrypt.checkpw(password_input.encode('utf-8'), stored_hash):
                session['user_id'] = user['id']
                session['email'] = user['email']
                session['role'] = user['role']

                # Redirect based on role
                if user['role'] == 'admin':
                    return redirect('/admin/dashboard')
                else:
                    return redirect('/referral/dashboard')
            else:
                error = "Invalid password"
        else:
            error = "User not found"

    return render_template('login.html', error=error)

# ✅ Logout route
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

# ✅ Admin dashboard
@app.route('/admin/dashboard')
def admin_dashboard():
    if session.get('role') != 'admin':
        return redirect('/login')

    cursor.execute("SELECT COUNT(*) AS total_leads FROM leads")
    leads_count = cursor.fetchone()['total_leads']

    cursor.execute("SELECT COUNT(*) AS total_referrals FROM referral_partners")
    referrals_count = cursor.fetchone()['total_referrals']

    return render_template("admin.html", leads_count=leads_count, referrals_count=referrals_count)

# ✅ Referral dashboard
@app.route('/referral/dashboard')
def referral_dashboard():
    if session.get('role') != 'referral':
        return redirect('/login')
    return render_template("referral.html")

# ✅ Leads list
@app.route('/leads')
def leads():
    if session.get('role') != 'admin':
        return redirect('/login')

    cursor.execute("SELECT * FROM leads")
    leads = cursor.fetchall()
    return render_template("leads.html", leads=leads)

# ✅ Referrals list
@app.route('/referrals')
def referrals():
    if session.get('role') != 'admin':
        return redirect('/login')

    cursor.execute("SELECT * FROM referral_partners")
    referrals = cursor.fetchall()
    return render_template("referrals.html", referrals=referrals)

# ✅ Export leads as CSV
@app.route('/export/leads')
def export_leads():
    cursor.execute("SELECT * FROM leads")
    leads = cursor.fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Name', 'Email', 'Phone', 'Insurance Type', 'Notes', 'Referral Code', 'Source', 'Status'])

    for lead in leads:
        writer.writerow([
            lead['id'], lead['name'], lead['email'], lead['phone'],
            lead['insurance_type'], lead['notes'], lead['referral_code'],
            lead['source'], lead['status']
        ])

    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode()),
        mimetype='text/csv',
        as_attachment=True,
        download_name='leads.csv'
    )

# ✅ Export referrals as CSV
@app.route('/export/referrals')
def export_referrals():
    cursor.execute("SELECT * FROM referral_partners")
    referrals = cursor.fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Name', 'Phone', 'Email', 'Referral Code'])

    for ref in referrals:
        writer.writerow([ref['id'], ref['name'], ref['phone'], ref['email'], ref['referral_code']])

    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode()),
        mimetype='text/csv',
        as_attachment=True,
        download_name='referrals.csv'
    )

# ✅ Update status of a lead
@app.route('/update_status/<int:lead_id>', methods=['POST'])
def update_status(lead_id):
    data = request.get_json()
    new_status = data['status']

    cursor.execute("UPDATE leads SET status = %s WHERE id = %s", (new_status, lead_id))
    db.commit()
    return jsonify({"success": True})

# ✅ Generate referral code
def generate_referral_code(name):
    initials = ''.join([word[0].upper() for word in name.split() if word])
    random_part = ''.join(random.choices(string.digits, k=4))
    return initials + random_part

# ✅ Form submission (lead or referral)
@app.route('/submit', methods=['POST'])
def submit_form():
    source = request.form.get('source')

    if source == "referral":
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        referral_code = generate_referral_code(name)

        cursor.execute("""
            INSERT INTO referral_partners (name, phone, email, referral_code)
            VALUES (%s, %s, %s, %s)
        """, (name, phone, email, referral_code))
        db.commit()

        return jsonify({"status": "success", "referral_code": referral_code})
    
    else:  # lead form
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        insurance_type = request.form.get('insurance_type')
        notes = request.form.get('notes')
        referral_code = request.form.get('referral_code')

        cursor.execute("""
            INSERT INTO leads (name, email, phone, insurance_type, notes, referral_code, source, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'Pending')
        """, (name, email, phone, insurance_type, notes, referral_code, source))
        db.commit()

        return "✅ Submitted successfully!"

# ✅ One-time conversion of old plain text passwords to bcrypt hashed passwords
@app.route('/convert-passwords')
def convert_passwords():
    try:
        cursor.execute("SELECT id, password FROM users")
        users = cursor.fetchall()
        count = 0

        for user in users:
            user_id = user['id']
            raw_pass = user['password']

            # Skip if already bcrypt hashed
            if raw_pass.startswith('$2b$') or raw_pass.startswith('$2a$'):
                continue

            hashed = bcrypt.hashpw(raw_pass.encode('utf-8'), bcrypt.gensalt())
            cursor.execute("UPDATE users SET password = %s WHERE id = %s", (hashed.decode('utf-8'), user_id))
            count += 1

        db.commit()
        return f"{count} password(s) converted to bcrypt successfully."
    except Exception as e:
        return f"Error during conversion: {str(e)}"

# ✅ Run the app
if __name__ == '__main__':
    app.run(debug=True)
