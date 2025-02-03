from flask import Flask, render_template, redirect, url_for, request, flash, session, jsonify, current_app
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_socketio import SocketIO, join_room, leave_room, emit
from datetime import datetime
import eventlet
import os
eventlet.monkey_patch()

# Initialize the app and configuration
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = 'static/uploads'

# Create the uploads folder if it doesn't exist
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])
    
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Initialize SocketIO
socketio = SocketIO(app, manage_session=False)

#File Verification service
def allowed_file(filename):
    allowed_extensions = current_app.config.get('ALLOWED_EXTENSIONS', set())
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions


# Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    bio = db.Column(db.Text, default="")  # New field for a user's bio
    avatar = db.Column(db.String(300), default="")  # New field for an avatar URL

    def __repr__(self):
        return f'<User {self.username}>'


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Message from {self.sender_id} to {self.receiver_id}>'

# User loader for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Utility function to generate a unique room name for two users
def get_room_name(user1_id, user2_id):
    # Ensure that the room name is the same regardless of order
    sorted_ids = sorted([user1_id, user2_id])
    return f"conversation_{sorted_ids[0]}_{sorted_ids[1]}"

# Routes

@app.route('/')
def index():
    if current_user.is_authenticated:
        # List all users except the current user
        users = User.query.filter(User.id != current_user.id).all()
        return render_template('index.html', users=users)
    return render_template('index.html')

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        # Update the bio field
        bio = request.form.get('bio', '').strip()
        current_user.bio = bio

        # Check if a file was uploaded for the avatar
        file = request.files.get('avatar_file')
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            # Save the relative path to the avatar field (so it can be served from static/)
            current_user.avatar = filename  # Just save the filename
            db.session.commit()
        elif file and file.filename != '':
            # File was submitted but the extension is not allowed.
            flash("File type not allowed. Please upload an image file.", "danger")
            return redirect(url_for('profile'))

        db.session.commit()
        flash("Profile updated successfully!", "success")
        return redirect(url_for('profile'))
    
    return render_template('profile.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username').strip()
        password = request.form.get('password').strip()

        if not username or not password:
            flash("Please enter both username and password.", "danger")
            return redirect(url_for('register'))

        if User.query.filter_by(username=username).first():
            flash("Username already exists. Please choose a different one.", "danger")
            return redirect(url_for('register'))

        hashed_pw = generate_password_hash(password)  # default is pbkdf2:sha256
        new_user = User(username=username, password=hashed_pw)
        db.session.add(new_user)
        db.session.commit()
        flash("Account created successfully. Please login.", "success")
        return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username').strip()
        password = request.form.get('password').strip()

        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            flash("Logged in successfully!", "success")
            return redirect(url_for('index'))
        else:
            flash("Invalid username or password.", "danger")
            return redirect(url_for('login'))
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for('login'))


@app.route('/conversation/<int:other_user_id>')
@login_required
def conversation(other_user_id):
    other_user = User.query.get_or_404(other_user_id)
    room = get_room_name(current_user.id, other_user.id)

    # Query messages between current_user and the other user
    messages = Message.query.filter(
        ((Message.sender_id == current_user.id) & (Message.receiver_id == other_user.id)) |
        ((Message.sender_id == other_user.id) & (Message.receiver_id == current_user.id))
    ).order_by(Message.timestamp).all()
    
    return render_template('conversation.html', messages=messages, other_user=other_user, room=room)


# SocketIO events

@socketio.on('join')
def on_join(data):
    room = data['room']
    join_room(room)
    # Optionally, notify others that a user has joined
    # emit('status', {'msg': f'{current_user.username} has entered the room.'}, room=room)

@socketio.on('send_message')
def handle_send_message_event(data):
    room = data['room']
    content = data['message']
    other_user_id = data['other_user_id']
    
    # Save message to database
    new_message = Message(sender_id=current_user.id,
                          receiver_id=other_user_id,
                          content=content)
    db.session.add(new_message)
    db.session.commit()

    timestamp = new_message.timestamp.strftime('%Y-%m-%d %H:%M:%S')
    message_data = {
        'sender_id': current_user.id,
        'sender': current_user.username,
        'message': content,
        'timestamp': timestamp,
    }
    emit('receive_message', message_data, room=room)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    # Use socketio.run instead of app.run
    socketio.run(app, debug=True)
