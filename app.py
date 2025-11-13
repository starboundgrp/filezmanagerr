import os
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, abort
from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file

import random
from werkzeug.utils import secure_filename
import cloudinary
import cloudinary.uploader
import cloudinary.api

# Explicitly set the static folder to be 'static' in the same directory as this script.
# This makes the app more robust, especially in different deployment environments.
app = Flask(__name__, static_folder='static')


# --- Configuration ---
app.secret_key = os.environ.get('SECRET_KEY', 'your-very-secret-key')
app.config['ADMIN_USERNAME'] = os.environ.get('ADMIN_USERNAME', 'adbriasfilesstar12')
app.config['ADMIN_PASSWORD'] = os.environ.get('ADMIN_PASSWORD', 'admi8?%03E,w4FA3^Wy4')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Limit uploads to 16 MB

# --- Cloudinary Configuration ---
cloudinary.config(
    cloud_name = os.environ.get('CLOUDINARY_CLOUD_NAME'),
    api_key = os.environ.get('CLOUDINARY_API_KEY'),
    api_secret = os.environ.get('CLOUDINARY_API_SECRET')
)

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
    safe_filename = secure_filename(filename)
    
    try:
        # Check if the file exists in Cloudinary before showing the gate
        cloudinary.api.resource(os.path.splitext(safe_filename)[0], resource_type="raw")
    except cloudinary.exceptions.NotFound:
        # If Cloudinary says the file doesn't exist, show a 404 error
        abort(404)
    except Exception as e:
        print(f"ERROR checking file in Cloudinary: {e}")
        abort(404)

    # --- Select a random video from Cloudinary (or set to None) ---
    video_url = None
    
    try:
        # Try to fetch video files from Cloudinary
        video_resources = cloudinary.api.resources(
            resource_type="video",
            type="upload",
            max_results=100
        ).get('resources', [])
        
        print(f"DEBUG: Found {len(video_resources)} videos in Cloudinary")
        
        if video_resources:
            # Select a random video
            random_video = random.choice(video_resources)
            # Generate the video URL
            video_url = cloudinary.utils.cloudinary_url(
                random_video['public_id'],
                resource_type="video",
                format=random_video.get('format', 'mp4')
            )[0]
            print(f"DEBUG: Selected video: {random_video['public_id']}")
            print(f"DEBUG: Video URL: {video_url}")
        else:
            print("INFO: No videos found in Cloudinary - page will show without video")
    except Exception as e:
        print(f"WARNING: Error fetching videos from Cloudinary: {e}")
        # Continue without video
    
    return render_template(
        'download_gate.html', 
        filename=safe_filename, 
        video_url=video_url)

@app.route('/download/<filename>')
def download_file(filename):
    """Redirects to the Cloudinary URL for the file to start the download."""
    try:
        # Get the file's URL from Cloudinary
        # The 'fl_attachment' flag tells the browser to download the file instead of displaying it
        public_id = os.path.splitext(secure_filename(filename))[0]
        download_url = cloudinary.utils.cloudinary_url(public_id, resource_type="raw", flags="attachment")[0]
        return redirect(download_url)
    except Exception:
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
        return render_template('admin.html')  # Show login form

    return render_template('admin.html')  # Show admin panel

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
        # Fetch all "raw" files from Cloudinary
        resources = cloudinary.api.resources(resource_type="raw", max_results=500).get('resources', [])
        for resource in resources:
            size_bytes = resource.get('bytes', 0)
            if size_bytes < 1024 * 1024:
                size = f"{size_bytes / 1024:.2f} KB"
            else:
                size = f"{size_bytes / (1024 * 1024):.2f} MB"
            # The public_id is the unique identifier, which we use as the filename
            files.append({'name': resource['public_id'] + '.' + resource.get('format', ''), 'size': size})
    except Exception as e:
        print(f"Error listing files from Cloudinary: {e}")
    return jsonify(files)

@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Handles file uploads."""
    if not is_user_logged_in():
        abort(403)  # Forbidden

    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    if file:
        filename = secure_filename(file.filename)
        # Upload to Cloudinary. 'public_id' is the filename without extension.
        # 'resource_type="raw"' is for non-image/video files.
        try:
            cloudinary.uploader.upload(
                file,
                public_id=os.path.splitext(filename)[0],
                resource_type="raw"
            )
            return jsonify({'success': f'File {filename} uploaded successfully'}), 201
        except Exception as e:
            print(f"Error uploading to Cloudinary: {e}")
            return jsonify({'error': 'Cloudinary upload failed. Check server logs and credentials.'}), 500

@app.route('/api/delete/<filename>', methods=['DELETE'])
def delete_file(filename):
    """Handles file deletions."""
    if not is_user_logged_in():
        abort(403)  # Forbidden
    try:
        # Delete from Cloudinary using the public_id (filename without extension)
        public_id = os.path.splitext(secure_filename(filename))[0]
        cloudinary.uploader.destroy(public_id, resource_type="raw")
        return jsonify({'success': f'File {filename} deleted'}), 200
    except Exception as e:
        print(f"Error deleting file from Cloudinary: {e}")
        return jsonify({'error': 'Could not delete file'}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5001)
