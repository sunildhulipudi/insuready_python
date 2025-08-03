import mysql.connector
import bcrypt

# Connect to your MySQL database
conn = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",
    database="insuready"
)
cursor = conn.cursor()

def is_bcrypt_hash(pw):
    """
    Check if the password is already bcrypt-hashed.
    Valid bcrypt hashes start with $2b$, $2a$, or $2y$.
    """
    return pw.startswith('$2b$') or pw.startswith('$2a$') or pw.startswith('$2y$')

def convert_passwords():
    cursor.execute("SELECT id, password FROM admin_users")
    users = cursor.fetchall()
    count = 0

    for user_id, pw in users:
        if not is_bcrypt_hash(pw):
            hashed_pw = bcrypt.hashpw(pw.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            cursor.execute("UPDATE admin_users SET password=%s WHERE id=%s", (hashed_pw, user_id))
            count += 1

    conn.commit()
    print(f"{count} password(s) converted to bcrypt successfully.")

convert_passwords()
cursor.close()
conn.close()
