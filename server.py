from flask import Flask, request, jsonify, send_from_directory
import os
import subprocess
import uuid
import re
import sys

app = Flask(__name__)
DOWNLOAD_FOLDER = "downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

def install_ytdlp():
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"], check=True)
        print("yt-dlp installed successfully")
    except subprocess.CalledProcessError as e:
        print(f"Failed to install yt-dlp: {e}")
        raise Exception("Failed to install yt-dlp")

def sanitize_filename(name):
    return re.sub(r'[^\w\-_\. ]', '_', name)

def download_audio(url):
    # Ensure yt-dlp is installed
    install_ytdlp()
    
    # Generate a unique filename
    unique_id = str(uuid.uuid4())
    safe_title = f"audio_{unique_id}.mp3"
    output_path = os.path.join(DOWNLOAD_FOLDER, safe_title)

    command = [
        "yt-dlp",
        "--extract-audio",
        "--audio-format", "mp3",
        "--audio-quality", "0",
        "-o", output_path,
        url
    ]

    try:
        print(f"Downloading: {url}")
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        print(f"Download output: {result.stdout}")
        if result.stderr:
            print(f"Download errors: {result.stderr}")
        return safe_title
    except subprocess.CalledProcessError as e:
        print(f"Download error: {e.stderr}")
        raise Exception(f"Download failed: {e.stderr}")

@app.route("/download", methods=["POST"])
def handle_download():
    data = request.get_json()
    url = data.get("url")
    if not url:
        return jsonify({"error": "URL is required"}), 400

    try:
        filename = download_audio(url)
        return jsonify({"file": filename})
    except Exception as e:
        print(f"Error in handle_download: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route("/file/<filename>")
def serve_file(filename):
    try:
        return send_from_directory(DOWNLOAD_FOLDER, filename, as_attachment=True)
    except FileNotFoundError:
        return jsonify({"error": "File not found"}), 404

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5050))
    app.run(host="0.0.0.0", port=port)