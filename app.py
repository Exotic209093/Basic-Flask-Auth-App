from flask import Flask, request, render_template, redirect, url_for
import sqlite3
import os
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

# Initialize the Flask app
app = Flask(__name__)

# File upload configuration
UPLOAD_FOLDER = 'uploads/'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Function to create the initial database
def create_table():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (username TEXT PRIMARY KEY, 
                  password TEXT, 
                  image_path TEXT, 
                  file_path TEXT)''')
    # Insert some initial data
    c.execute("INSERT OR IGNORE INTO users (username, password) VALUES (?, ?)", 
              ('user1', generate_password_hash('password1')))
    c.execute("INSERT OR IGNORE INTO users (username, password) VALUES (?, ?)", 
              ('user2', generate_password_hash('password2')))
    conn.commit()
    conn.close()


create_table()  # Initialize the database


# Route for the home page
@app.route('/')
def home():
    return redirect(url_for('login'))


# Function to verify login credentials
def verify_login(username, password):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('SELECT password FROM users WHERE username=?', (username,))
    result = c.fetchone()
    conn.close()
    if result and check_password_hash(result[0], password):
        return True
    return False


# Route for the login page
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if verify_login(username, password):
            return redirect(url_for('welcome', username=username))
        else:
            error = 'Invalid username or password. Please try again.'

    return render_template('login.html', error=error)


# Route for the registration page
@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        hashed_password = generate_password_hash(password)
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        try:
            c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed_password))
            conn.commit()
            conn.close()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            error = 'Username already exists. Please try a different one.'

    return render_template('register.html', error=error)


# Route for the welcome page
@app.route('/welcome/<username>')
def welcome(username):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('SELECT image_path FROM users WHERE username=?', (username,))
    result = c.fetchone()
    conn.close()
    image_path = result[0] if result and result[0] else 'default_image.jpg'  # Replace with your default image path
    return render_template('welcome.html', username=username, image_path=image_path)


# Route for file upload
@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    error = None
    if request.method == 'POST':
        file = request.files['file']
        username = request.form['username']
        if file and username:
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)

            conn = sqlite3.connect('users.db')
            c = conn.cursor()
            c.execute('UPDATE users SET file_path=? WHERE username=?', (file_path, username))
            conn.commit()
            conn.close()
            return redirect(url_for('welcome', username=username))
        else:
            error = 'Please provide both username and a file.'

    return render_template('upload.html', error=error)


if __name__ == '__main__':
    app.run(debug=True)
