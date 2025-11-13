@app.route('/prepare-download/<filename>')
def prepare_download(filename):
    """Serves the intermediate 'ad gate' page."""
    try:
        # Check if the file exists in Cloudinary before showing the gate
        cloudinary.api.resource(os.path.splitext(secure_filename(filename))[0], resource_type="raw")
    except cloudinary.exceptions.NotFound:
        # If Cloudinary says the file doesn't exist, show a 404 error
        abort(404)

    # --- Select a random video from Cloudinary ---
    video_url = None
    try:
        # Fetch all video files from Cloudinary
        video_resources = cloudinary.api.resources(
            resource_type="video",
            type="upload",
            prefix="ads/",  # Optional: organize videos in an 'ads' folder
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
            print(f"DEBUG: Selected video URL: {video_url}")
        else:
            print("Warning: No videos found in Cloudinary")
    except Exception as e:
        print(f"ERROR: Failed to fetch videos from Cloudinary: {e}")
    
    return render_template(
        'download_gate.html', 
        filename=secure_filename(filename), 
        video_url=video_url)
