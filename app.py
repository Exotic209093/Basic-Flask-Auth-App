from flask import Flask, request, render_template, redirect, url_for, jsonify
import sqlite3
import os
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import time
# Initialize the Flask app
app = Flask(__name__)

# File upload configuration
UPLOAD_FOLDER = 'uploads/'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Function to create the initial database
# First, let's modify the create_table function to add the new columns safely
def create_table():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    
    # First, check if we need to add new columns to the existing table
    c.execute("PRAGMA table_info(users)")
    columns = [column[1] for column in c.fetchall()]
    
    # If the table doesn't exist, create it with all columns
    if not columns:
        c.execute('''CREATE TABLE users
                     (username TEXT PRIMARY KEY,
                      password TEXT,
                      image_path TEXT,
                      display_name TEXT,
                      email TEXT,
                      bio TEXT,
                      email_notifications BOOLEAN DEFAULT FALSE,
                      profile_visible BOOLEAN DEFAULT FALSE)''')
    else:
        # Add any missing columns
        if 'display_name' not in columns:
            c.execute('ALTER TABLE users ADD COLUMN display_name TEXT')
        if 'email' not in columns:
            c.execute('ALTER TABLE users ADD COLUMN email TEXT')
        if 'bio' not in columns:
            c.execute('ALTER TABLE users ADD COLUMN bio TEXT')
        if 'email_notifications' not in columns:
            c.execute('ALTER TABLE users ADD COLUMN email_notifications BOOLEAN DEFAULT FALSE')
        if 'profile_visible' not in columns:
            c.execute('ALTER TABLE users ADD COLUMN profile_visible BOOLEAN DEFAULT FALSE')
    
    conn.commit()
    conn.close()

# Now let's modify the profile route to handle null values safely
@app.route('/profile/<username>', methods=['GET'])
def profile(username):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    
    # First, make sure we have all the necessary columns
    create_table()
    
    # Get user data
    c.execute('''SELECT username, image_path, display_name, email, bio, 
                 email_notifications, profile_visible 
                 FROM users WHERE username=?''', (username,))
    user = c.fetchone()
    conn.close()
    
    if user:
        return render_template('profile.html',
                             username=user[0],
                             image_path=user[1] if user[1] else 'default_avatar.jpg',
                             display_name=user[2] if user[2] else user[0],  # Use username if no display name
                             email=user[3] if user[3] else '',
                             bio=user[4] if user[4] else '',
                             email_notifications=bool(user[5]),
                             profile_visible=bool(user[6]))
    return redirect(url_for('login'))

# Add the update profile route
@app.route('/update_profile', methods=['POST'])
def update_profile():
    if request.method == 'POST':
        username = request.form.get('username')
        display_name = request.form.get('display_name')
        email = request.form.get('email')
        bio = request.form.get('bio')
        email_notifications = True if request.form.get('email_notifications') else False
        profile_visible = True if request.form.get('profile_visible') else False

        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute('''UPDATE users 
                    SET display_name=?, email=?, bio=?, 
                        email_notifications=?, profile_visible=?
                    WHERE username=?''',
                 (display_name, email, bio, 
                  email_notifications, profile_visible, username))
        conn.commit()
        conn.close()
        
        return redirect(url_for('profile', username=username))


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






@app.route('/upload_profile_image', methods=['POST'])
def upload_profile_image():
    if 'profile_image' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['profile_image']
    username = request.form.get('username')
    
    if file and username:
        filename = secure_filename(f"{username}_profile_{int(time.time())}.jpg")
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute('UPDATE users SET image_path=? WHERE username=?', (filename, username))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'image_path': filename})
    return jsonify({'error': 'Invalid request'}), 400

@app.route('/delete_account/<username>')
def delete_account(username):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('DELETE FROM users WHERE username=?', (username,))
    conn.commit()
    conn.close()
    return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(debug=True)
