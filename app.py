import os
from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory, jsonify, abort
import random
from werkzeug.utils import secure_filename

app = Flask(__name__)

# --- Configuration ---
app.secret_key = os.environ.get('SECRET_KEY', 'your-very-secret-key')
app.config['UPLOAD_FOLDER'] = os.environ.get('UPLOAD_FOLDER', '/tmp/uploads')
app.config['ADMIN_USERNAME'] = os.environ.get('ADMIN_USERNAME', 'adbriasfilesstar12')
app.config['ADMIN_PASSWORD'] = os.environ.get('ADMIN_PASSWORD', 'admi8?%03E,w4FA3^Wy4')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Limit uploads to 16 MB


# --- Helper Functions & Initial Setup ---
def is_user_logged_in():
    return bool(session.get('logged_in'))

# --- Route to handle favicon requests and prevent 404 errors ---
@app.route('/favicon.ico')
@app.route('/favicon.png')
def favicon():
    """Sends a 204 No Content response to favicon requests."""
    return '', 204

# --- Public Routes ---
@app.route('/')
def index():
    """Serves the public file list page."""
    # The file list will now be loaded dynamically via JavaScript.
    return render_template('index.html')

@app.route('/resource/<filename>')
def resource_page(filename):
    """Serves a dedicated page for a single resource."""
    safe_filename = secure_filename(filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], safe_filename)
    if not os.path.exists(filepath):
        abort(404)

    return render_template('resource.html', filename=safe_filename)
    
@app.route('/prepare-download/<filename>')
def prepare_download(filename):
    """Serves the intermediate 'ad gate' page."""
    safe_filename = secure_filename(filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], safe_filename)
    if not os.path.exists(filepath):
        abort(404)

    # --- Select a random video ---
    video_path = None
    try:
        videos_dir = os.path.join(app.static_folder, 'videos')
        available_videos = [f for f in os.listdir(videos_dir) if os.path.isfile(os.path.join(videos_dir, f)) and not f.startswith('.')]
        if available_videos:
            random_video_filename = random.choice(available_videos)
            # Construct the path relative to the 'static' folder
            video_path = os.path.join('videos', random_video_filename).replace("\\", "/")
    except FileNotFoundError:
        print("Warning: 'static/videos' directory not found. No video will be displayed.")
    return render_template(
        'download_gate.html', 
        filename=safe_filename, 
        video_path=video_path)

@app.route('/download/<filename>')
def download_file(filename):
    """Serves a file for download."""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

# --- Admin & Auth Routes ---
@app.route('/admin', methods=['GET', 'POST'])
def admin():
    """Handles admin login and serves the admin panel."""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username == app.config['ADMIN_USERNAME'] and password == app.config['ADMIN_PASSWORD']:
            session['logged_in'] = True
            return redirect(url_for('admin'))
        else:
            return render_template('admin.html', error="Invalid credentials")

    if not is_user_logged_in():
        return render_template('admin.html') # Show login form

    return render_template('admin.html') # Show admin panel

@app.route('/logout')
def logout():
    """Logs the user out."""
    session.pop('logged_in', None)
    return redirect(url_for('admin'))

# --- API Routes (for JavaScript interaction) ---
@app.route('/api/files', methods=['GET'])
def list_files():
    """Returns a JSON list of files in the upload folder."""
    files = []
    upload_folder = app.config['UPLOAD_FOLDER']
    try:
        os.makedirs(upload_folder, exist_ok=True) # Ensure directory exists
        for filename in os.listdir(upload_folder):
            if os.path.isfile(os.path.join(upload_folder, filename)) and not filename.startswith('.'):
                path = os.path.join(upload_folder, filename)
                size_bytes = os.path.getsize(path)
                # Format size to be human-readable
                if size_bytes < 1024 * 1024:
                    size = f"{size_bytes / 1024:.2f} KB"
                else:
                    size = f"{size_bytes / (1024 * 1024):.2f} MB"
                files.append({'name': filename, 'size': size})
    except Exception as e:
        # If any error occurs with the filesystem, log it and return an empty list.
        # This prevents the entire app from crashing.
        print(f"Error reading upload folder: {e}")
    return jsonify(files)

@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Handles file uploads."""
    if not is_user_logged_in():
        abort(403) # Forbidden

    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    if file:
        filename = secure_filename(file.filename)
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True) # Ensure directory exists
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        return jsonify({'success': f'File {filename} uploaded successfully'}), 201

@app.route('/api/delete/<filename>', methods=['DELETE'])
def delete_file(filename):
    """Handles file deletions."""
    if not is_user_logged_in():
        abort(403) # Forbidden

    try:
        # No need to create directory for deletion, just check path
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(filename))
        os.remove(filepath)
        return jsonify({'success': f'File {filename} deleted'}), 200
    except FileNotFoundError:
        return jsonify({'error': 'File not found'}), 404

if __name__ == '__main__':
    app.run(debug=True, port=5001)
