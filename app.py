from flask import Flask, request, render_template, redirect, url_for
import sqlite3
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)


# Function to create the initial database
def create_table():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (username TEXT PRIMARY KEY, password TEXT, image_path TEXT, file_path TEXT)''')
    # Insert some initial data
    c.execute("INSERT OR IGNORE INTO users (username, password) VALUES ('user1', 'password1')")
    c.execute("INSERT OR IGNORE INTO users (username, password) VALUES ('user2', 'password2')")
    conn.commit()
    conn.close()


create_table()

# Configure upload folder and allowed file extensions
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


# Check if a file has an allowed extension
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# Route for the home page
@app.route('/')
def home():
    return redirect(url_for('login'))


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


# Function to verify login credentials
def verify_login(username, password):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE username=? AND password=?', (username, password))
    result = c.fetchone()
    conn.close()
    return result is not None


# Route for the welcome page
@app.route('/welcome/<username>')
def welcome(username):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('SELECT image_path FROM users WHERE username=?', (username,))
    results = c.fetchall()
    conn.close()
    image_paths = [result[0] for result in results] if results else []
    return render_template('welcome.html', username=username, image_paths=image_paths)


# Route for uploading files
@app.route('/upload', methods=['POST'])
def upload_file():
    if request.method == 'POST':
        # Check if the post request has the file part
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['file']
        # If user does not select file, browser also
        # submit an empty part without filename
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            # Secure the filename before saving it
            filename = secure_filename(file.filename)
            # Save the file to the upload folder
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            # Update the database with the file path
            conn = sqlite3.connect('users.db')
            c = conn.cursor()
            c.execute('UPDATE users SET file_path=? WHERE username=?',
                      (os.path.join(app.config['UPLOAD_FOLDER'], filename), request.form['username']))
            conn.commit()
            conn.close()
            return redirect(url_for('welcome', username=request.form['username']))
    return redirect(url_for('welcome', username=request.form['username']))


if __name__ == '__main__':
    app.run(debug=True)
