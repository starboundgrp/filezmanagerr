import os
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, abort
import random
from werkzeug.utils import secure_filename
from vercel_kv import kv

app = Flask(__name__)

# --- Configuration ---
app.secret_key = os.environ.get('SECRET_KEY', 'your-very-secret-key')
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
    # On a serverless platform, we can't guarantee the file still exists.
    # We will proceed and let the final download link handle any "Not Found" errors.
    safe_filename = secure_filename(filename)
    return render_template('resource.html', filename=safe_filename)
    
@app.route('/prepare-download/<filename>')
def prepare_download(filename):
    """Serves the intermediate 'ad gate' page."""
    # Check if the file link exists in our KV store
    if not kv.exists(secure_filename(filename)):
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
        filename=secure_filename(filename), 
        video_path=video_path)

@app.route('/download/<filename>')
def download_file(filename):
    """Redirects to the Cloudinary URL for the file to start the download."""
    # Get the external URL from the KV store and redirect the user
    download_url = kv.get(secure_filename(filename))
    if download_url:
        return redirect(download_url)
    else:
        abort(404)
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
    try:
        # Get all keys (filenames) from the KV store
        filenames = kv.keys('*')
        for filename in filenames:
            # For simplicity, we won't show file size as we don't know it.
            files.append({'name': filename, 'size': 'N/A'})
    except Exception as e:
        print(f"Error listing files from Vercel KV: {e}")
    return jsonify(files)

@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Handles adding a new file link."""
    if not is_user_logged_in():
        abort(403) # Forbidden

    data = request.get_json()
    filename = data.get('filename')
    url = data.get('url')

    if not filename or not url:
        return jsonify({'error': 'Filename and URL are required'}), 400

    # Save the filename and URL to the KV store
    kv.set(secure_filename(filename), url)
    return jsonify({'success': f'Link for {filename} added successfully'}), 201

@app.route('/api/delete/<filename>', methods=['DELETE'])
def delete_file(filename):
    """Handles file deletions."""
    if not is_user_logged_in():
        abort(403) # Forbidden
    try:
        # Delete the key (filename) from the KV store
        kv.delete(secure_filename(filename))
        return jsonify({'success': f'File {filename} deleted'}), 200
    except Exception as e:
        print(f"Error deleting file from Vercel KV: {e}")
        return jsonify({'error': 'Could not delete link'}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5001)
