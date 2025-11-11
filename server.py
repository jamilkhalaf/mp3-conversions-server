from flask import Flask, request, jsonify, send_from_directory
import os
import subprocess
import uuid
import re
import shutil
from datetime import datetime
import json

app = Flask(__name__)
DOWNLOAD_FOLDER = os.path.expanduser("~/Desktop/songs")
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# Define the restricted screenshots folder path
SCREENSHOTS_FOLDER = os.path.expanduser("~/Pictures")

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

def get_file_info(file_path):
    """Get file information for the Finder app"""
    try:
        stat = os.stat(file_path)
        return {
            "name": os.path.basename(file_path),
            "size": stat.st_size,
            "modifiedDate": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "isDirectory": os.path.isdir(file_path)
        }
    except Exception as e:
        print(f"Error getting file info for {file_path}: {e}")
        return None

def is_safe_path(path):
    """Check if the path is safe to access (only within screenshots folder)"""
    try:
        # Resolve the requested path
        requested_path = os.path.realpath(path)
        screenshots_path = os.path.realpath(SCREENSHOTS_FOLDER)
        
        # Check if the requested path is within the screenshots folder
        return requested_path.startswith(screenshots_path)
    except Exception:
        return False

@app.route("/download", methods=["POST"])
def handle_download():
    # Accept JSON ({ "url": "..." }) or form (url=...)
    url = None
    if request.is_json:
        data = request.get_json(silent=True) or {}
        url = data.get("url")
    else:
        url = request.form.get("url")

    if not url:
        return jsonify({"error": "URL is required"}), 400

    try:
        filename = download_audio(url)
        file_path = os.path.join(DOWNLOAD_FOLDER, filename)
        music_auto_import = "/Users/jamilkhalaf/Music/Music/Media.localized/Automatically Add to Music.localized"

        # Copy into Apple Music's auto-import folder
        shutil.copy(file_path, music_auto_import)

        return jsonify({"file": filename, "status": "imported to Apple Music"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/file/<filename>")
def serve_file(filename):
    try:
        return send_from_directory(DOWNLOAD_FOLDER, filename, as_attachment=True)
    except FileNotFoundError:
        return jsonify({"error": "File not found"}), 404

@app.route("/files/<path:directory>")
def list_files(directory):
    """List files in a directory for the Finder app - restricted to screenshots folder only"""
    try:
        # Decode the directory path
        import urllib.parse
        directory = urllib.parse.unquote(directory)
        print(f"Requested directory: {directory}")
        
        # Handle root path - always show screenshots folder
        if directory == "" or directory == "/":
            full_path = SCREENSHOTS_FOLDER
        else:
            # Build the full path within screenshots folder
            if directory.startswith("/"):
                directory = directory[1:]  # Remove leading slash
            full_path = os.path.join(SCREENSHOTS_FOLDER, directory)
        
        # Resolve any symbolic links and normalize the path
        full_path = os.path.realpath(full_path)
        screenshots_path = os.path.realpath(SCREENSHOTS_FOLDER)
        
        print(f"Screenshots folder: {screenshots_path}")
        print(f"Full resolved path: {full_path}")
        
        # Security check - ensure we're only accessing files within the screenshots folder
        if not full_path.startswith(screenshots_path):
            print(f"Access denied: {full_path} is outside {screenshots_path}")
            return jsonify({"error": "Access denied - path outside screenshots folder"}), 403
        
        if not os.path.exists(full_path):
            print(f"Directory not found: {full_path}")
            return jsonify({"error": f"Directory not found: {directory}"}), 404
        
        if not os.path.isdir(full_path):
            print(f"Not a directory: {full_path}")
            return jsonify({"error": "Not a directory"}), 400
        
        files = []
        try:
            for item in os.listdir(full_path):
                # Skip hidden files (starting with .)
                if item.startswith('.'):
                    continue
                    
                item_path = os.path.join(full_path, item)
                file_info = get_file_info(item_path)
                if file_info:
                    files.append(file_info)
                    print(f"Found: {item} ({'dir' if file_info['isDirectory'] else 'file'})")
        except PermissionError:
            print(f"Permission denied accessing: {full_path}")
            return jsonify({"error": "Permission denied"}), 403
        
        print(f"Returning {len(files)} files/directories")
        
        # Return HTML interface instead of JSON
        current_path = directory if directory else ""
        parent_path = "/".join(current_path.split("/")[:-1]) if "/" in current_path else ""
        
        html_content = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Screenshots Folder - {current_path or 'Root'}</title>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    margin: 0;
                    padding: 20px;
                    background-color: #f5f5f7;
                }}
                .container {{
                    max-width: 1200px;
                    margin: 0 auto;
                    background: white;
                    border-radius: 12px;
                    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                    overflow: hidden;
                }}
                .header {{
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 20px;
                    text-align: center;
                }}
                .breadcrumb {{
                    background: #f8f9fa;
                    padding: 15px 20px;
                    border-bottom: 1px solid #e9ecef;
                }}
                .breadcrumb a {{
                    color: #007aff;
                    text-decoration: none;
                    margin-right: 10px;
                }}
                .breadcrumb a:hover {{
                    text-decoration: underline;
                }}
                .file-list {{
                    padding: 0;
                    margin: 0;
                }}
                .file-item {{
                    display: flex;
                    align-items: center;
                    padding: 15px 20px;
                    border-bottom: 1px solid #e9ecef;
                    transition: background-color 0.2s;
                }}
                .file-item:hover {{
                    background-color: #f8f9fa;
                }}
                .file-item:last-child {{
                    border-bottom: none;
                }}
                .file-icon {{
                    width: 40px;
                    height: 40px;
                    margin-right: 15px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    background: #e9ecef;
                    border-radius: 8px;
                    font-size: 20px;
                }}
                .file-info {{
                    flex: 1;
                }}
                .file-name {{
                    font-weight: 600;
                    color: #1d1d1f;
                    margin-bottom: 4px;
                }}
                .file-details {{
                    font-size: 14px;
                    color: #86868b;
                }}
                .file-actions {{
                    display: flex;
                    gap: 10px;
                }}
                .btn {{
                    padding: 8px 16px;
                    border: none;
                    border-radius: 6px;
                    cursor: pointer;
                    font-size: 14px;
                    text-decoration: none;
                    display: inline-block;
                    text-align: center;
                }}
                .btn-primary {{
                    background: #007aff;
                    color: white;
                }}
                .btn-primary:hover {{
                    background: #0056b3;
                }}
                .btn-secondary {{
                    background: #6c757d;
                    color: white;
                }}
                .btn-secondary:hover {{
                    background: #545b62;
                }}
                .empty-state {{
                    text-align: center;
                    padding: 60px 20px;
                    color: #86868b;
                }}
                .stats {{
                    background: #f8f9fa;
                    padding: 15px 20px;
                    border-bottom: 1px solid #e9ecef;
                    font-size: 14px;
                    color: #86868b;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>📸 Screenshots Folder</h1>
                    <p>Browse and download your screenshots</p>
                </div>
                
                <div class="breadcrumb">
                    <a href="/files/">🏠 Home</a>
                    {f'<a href="/files/{parent_path}">⬆️ Parent</a>' if parent_path else ''}
                    <span>📍 {current_path or 'Root'}</span>
                </div>
                
                <div class="stats">
                    📊 {len(files)} items found
                </div>
                
                <div class="file-list">
        """
        
        if not files:
            html_content += """
                    <div class="empty-state">
                        <h3>📁 This folder is empty</h3>
                        <p>No files or folders found in this directory.</p>
                    </div>
            """
        else:
            for file_info in files:
                if file_info['isDirectory']:
                    # Directory
                    html_content += f"""
                        <div class="file-item">
                            <div class="file-icon">📁</div>
                            <div class="file-info">
                                <div class="file-name">{file_info['name']}</div>
                                <div class="file-details">Directory</div>
                            </div>
                            <div class="file-actions">
                                <a href="/files/{current_path + '/' if current_path else ''}{file_info['name']}" class="btn btn-primary">Open</a>
                            </div>
                        </div>
                    """
                else:
                    # File
                    file_size = file_info['size']
                    size_str = f"{file_size / (1024*1024):.1f} MB" if file_size > 1024*1024 else f"{file_size / 1024:.1f} KB"
                    
                    html_content += f"""
                        <div class="file-item">
                            <div class="file-icon">📄</div>
                            <div class="file-info">
                                <div class="file-name">{file_info['name']}</div>
                                <div class="file-details">{size_str} • Modified: {file_info['modifiedDate'][:10]}</div>
                            </div>
                            <div class="file-actions">
                                <a href="/download-file/{current_path + '/' if current_path else ''}{file_info['name']}" class="btn btn-primary">Download</a>
                            </div>
                        </div>
                    """
        
        html_content += """
                </div>
            </div>
        </body>
        </html>
        """
        
        return html_content
    
    except Exception as e:
        print(f"Error listing files in {directory}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/files/")
def list_root_files():
    """List files in the screenshots folder"""
    return list_files("")

@app.route("/download-file/<path:file_path>")
def download_file(file_path):
    """Download a specific file from the screenshots folder only"""
    try:
        # Decode the file path
        import urllib.parse
        file_path = urllib.parse.unquote(file_path)
        print(f"Requested file path: {file_path}")
        
        # Build the full path within screenshots folder
        if file_path.startswith("/"):
            file_path = file_path[1:]  # Remove leading slash
        
        full_path = os.path.join(SCREENSHOTS_FOLDER, file_path)
        
        # Resolve any symbolic links and normalize the path
        full_path = os.path.realpath(full_path)
        screenshots_path = os.path.realpath(SCREENSHOTS_FOLDER)
        
        print(f"Screenshots folder: {screenshots_path}")
        print(f"Full resolved path: {full_path}")
        
        # Security check - ensure we're only accessing files within the screenshots folder
        if not full_path.startswith(screenshots_path):
            print(f"Access denied: {full_path} is outside {screenshots_path}")
            return jsonify({"error": "Access denied - path outside screenshots folder"}), 403
        
        if not os.path.exists(full_path):
            print(f"File not found: {full_path}")
            return jsonify({"error": f"File not found: {file_path}"}), 404
        
        if os.path.isdir(full_path):
            print(f"Cannot download directory: {full_path}")
            return jsonify({"error": "Cannot download directory"}), 400
        
        # Check file size to prevent downloading huge files
        try:
            file_size = os.path.getsize(full_path)
            print(f"File size: {file_size} bytes")
            if file_size > 100 * 1024 * 1024:  # 100MB limit
                return jsonify({"error": "File too large (max 100MB)"}), 413
        except OSError as e:
            print(f"Error getting file size: {e}")
            return jsonify({"error": "Cannot access file"}), 500
        
        directory = os.path.dirname(full_path)
        filename = os.path.basename(full_path)
        
        print(f"Serving file: {filename} from directory: {directory}")
        
        # Set proper headers for file download
        response = send_from_directory(directory, filename, as_attachment=True)
        response.headers['Content-Length'] = str(file_size)
        response.headers['Cache-Control'] = 'no-cache'
        
        return response
    
    except Exception as e:
        print(f"Error downloading file {file_path}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/")
def home():
    return """
    <html>
    <head><title>Audio Downloader</title></head>
    <body>
      <h1>Audio Downloader</h1>
      <p>Jamil Server.</p>
      <p>Welcome to mp3 conversions web page</p>

      <h2>Clicks: <span id="counter">0</span></h2>
      <button onclick="increment()">Click Me</button>

      <script>
        let count = 0;
        function increment() {
          count++;
          document.getElementById("counter").innerText = count;
        }
      </script>
    </body>
    </html>
    """

@app.route("/mp3", methods=["GET"])
def mp3_page():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="utf-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1" />
      <title>MP3 Downloader</title>
      <style>
        :root { font-family: -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Ubuntu,"Helvetica Neue",Arial; }
        body { margin: 0; background:#f5f5f7; }
        .wrap { max-width: 720px; margin: 40px auto; background:#fff; border-radius: 14px; box-shadow: 0 8px 24px rgba(0,0,0,.08); overflow: hidden; }
        header { padding: 20px 24px; color: #fff;
                 background: linear-gradient(135deg,#667eea 0%, #764ba2 100%); }
        header h1 { margin: 0; font-size: 22px; }
        main { padding: 20px 24px 28px; }
        label { font-weight: 600; display:block; margin: 8px 0 6px; }
        input[type=text]{
          width:100%; padding:14px 12px; font-size:16px; border:1px solid #e5e7eb; border-radius:10px; outline:none;
        }
        input[type=text]:focus { border-color:#667eea; box-shadow: 0 0 0 3px rgba(102,126,234,.15); }
        button {
          margin-top: 14px; padding: 11px 18px; font-size: 15px; border:0; border-radius: 10px; cursor:pointer;
          color:#fff; background:#007aff;
        }
        button[disabled] { opacity:.6; cursor:not-allowed; }
        .note { color:#6b7280; font-size: 13px; margin-top: 8px; }
        .status { margin-top: 16px; padding: 12px; border-radius: 10px; display:none; }
        .status.ok { background:#ecfdf5; color:#065f46; display:block; }
        .status.err { background:#fef2f2; color:#991b1b; display:block; }
        .result { margin-top: 14px; padding: 12px; border:1px solid #e5e7eb; border-radius: 10px; display:none; }
        .muted { color:#6b7280; font-size: 14px; }
        footer { padding: 14px 24px; font-size: 12px; color:#6b7280; border-top:1px solid #f0f0f0; background:#fafafa; }
        .spinner { display:inline-block; width: 16px; height:16px; border:2px solid #fff; border-right-color: transparent; border-radius:50%; animation:spin 0.7s linear infinite; vertical-align: -2px; margin-right:8px; }
        @keyframes spin { to { transform: rotate(360deg); } }
      </style>
    </head>
    <body>
      <div class="wrap">
        <header>
          <h1>🎵 MP3 Downloader</h1>
          <div class="muted">Paste a YouTube URL and I’ll import it into Apple Music.</div>
        </header>
        <main>
          <form id="dl-form">
            <label for="yt">YouTube URL</label>
            <input type="text" id="yt" name="url" placeholder="https://www.youtube.com/watch?v=..." required />
            <div class="note">The audio will also appear in <em>Music &rarr; Automatically Add to Music</em> on this Mac.</div>
            <button id="go"><span class="btn-text">Download MP3</span></button>
          </form>

          <div id="status" class="status"></div>

          <div id="result" class="result">
            <div><strong>File:</strong> <span id="fname"></span></div>
            <div class="muted">Local download link (server): <a id="fhref" href="#" download>open</a></div>
            <div class="muted" id="imported">Status: <em>imported to Apple Music</em></div>
          </div>
        </main>
        <footer>
          Tip: bookmark <code>/mp3</code> on your phone to use it like a mini app.
        </footer>
      </div>

      <script>
        const form = document.getElementById('dl-form');
        const input = document.getElementById('yt');
        const btn = document.getElementById('go');
        const statusEl = document.getElementById('status');
        const result = document.getElementById('result');
        const fname = document.getElementById('fname');
        const fhref = document.getElementById('fhref');

        function setBusy(b) {
          if (b) {
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner"></span>Downloading...';
          } else {
            btn.disabled = false;
            btn.innerHTML = '<span class="btn-text">Download MP3</span>';
          }
        }

        function showStatus(msg, ok) {
          statusEl.textContent = msg;
          statusEl.className = 'status ' + (ok ? 'ok' : 'err');
        }

        form.addEventListener('submit', async (e) => {
          e.preventDefault();
          const url = input.value.trim();
          if (!url) { showStatus('Please paste a YouTube URL.', false); return; }

          setBusy(true);
          showStatus('Starting download… this can take a bit depending on video length.', true);
          result.style.display = 'none';

          try {
            const resp = await fetch('/download', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ url })
            });

            const data = await resp.json();
            if (!resp.ok) {
              throw new Error(data.error || 'Unknown error');
            }

            // Success
            fname.textContent = data.file;
            fhref.href = '/file/' + encodeURIComponent(data.file);
            result.style.display = 'block';
            showStatus('Done! File saved and imported to Apple Music.', true);
          } catch (err) {
            console.error(err);
            showStatus('Error: ' + err.message, false);
          } finally {
            setBusy(false);
          }
        });
      </script>
    </body>
    </html>
    """


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050) 