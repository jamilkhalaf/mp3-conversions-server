from flask import Flask, request, jsonify, send_from_directory
import os
import subprocess
import uuid
import re

app = Flask(__name__)
DOWNLOAD_FOLDER = "downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

def sanitize_filename(name):
    return re.sub(r'[^\w\-_\. ]', '_', name)

def download_audio(url):
    # Use yt-dlp to extract title first
    title_cmd = [
        "yt-dlp",
        "--get-title",
        "--no-warnings",
        url
    ]
    try:
        title_result = subprocess.run(title_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        raw_title = title_result.stdout.decode().strip()
        safe_title = sanitize_filename(raw_title) + ".mp3"
    except subprocess.CalledProcessError as e:
        raise Exception("Failed to retrieve title")

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
        subprocess.run(command, check=True)
        return safe_title
    except subprocess.CalledProcessError as e:
        raise Exception("Download failed")


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
        return jsonify({"error": str(e)}), 500

@app.route("/file/<filename>")
def serve_file(filename):
    try:
        return send_from_directory(DOWNLOAD_FOLDER, filename, as_attachment=True)
    except FileNotFoundError:
        return jsonify({"error": "File not found"}), 404

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050)
