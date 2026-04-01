import os
import yt_dlp
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import tempfile
import threading

app = Flask(__name__)
CORS(app)  # GitHub Pages thi call allow karshe

def get_ydl_opts(fmt='best', audio_only=False, audio_format='mp3', audio_bitrate='192'):
    opts = {
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
    }
    if audio_only:
        opts['format'] = 'bestaudio/best'
        opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': audio_format,
            'preferredquality': audio_bitrate,
        }]
    else:
        # Video quality map
        quality_map = {
            '2160': 'bestvideo[height<=2160]+bestaudio/best[height<=2160]',
            '1080': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]',
            '720':  'bestvideo[height<=720]+bestaudio/best[height<=720]',
            '480':  'bestvideo[height<=480]+bestaudio/best[height<=480]',
            '360':  'bestvideo[height<=360]+bestaudio/best[height<=360]',
        }
        opts['format'] = quality_map.get(fmt, 'best')
        opts['merge_output_format'] = 'mp4'
    return opts


@app.route('/', methods=['GET'])
def index():
    return jsonify({'status': 'ok', 'service': 'yt-dlp API', 'version': '1.0'})


@app.route('/info', methods=['POST'])
def video_info():
    """Video info fetch karo — title, thumbnail, duration"""
    data = request.get_json()
    url  = data.get('url', '').strip()
    if not url:
        return jsonify({'error': 'URL required'}), 400

    try:
        opts = {'quiet': True, 'no_warnings': True, 'noplaylist': True, 'skip_download': True}
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return jsonify({
                'title':     info.get('title', ''),
                'channel':   info.get('uploader', ''),
                'duration':  info.get('duration', 0),
                'thumbnail': info.get('thumbnail', ''),
                'view_count':info.get('view_count', 0),
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/download', methods=['POST'])
def download():
    """Direct file stream karo"""
    data         = request.get_json()
    url          = data.get('url', '').strip()
    quality      = data.get('quality', '720')       # video quality
    audio_only   = data.get('audio_only', False)
    audio_format = data.get('audio_format', 'mp3')
    audio_bitrate= data.get('audio_bitrate', '192')

    if not url:
        return jsonify({'error': 'URL required'}), 400

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            out_tmpl = os.path.join(tmpdir, '%(title)s.%(ext)s')
            opts = get_ydl_opts(quality, audio_only, audio_format, audio_bitrate)
            opts['outtmpl'] = out_tmpl

            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                title = info.get('title', 'video')

            # Find downloaded file
            files = os.listdir(tmpdir)
            if not files:
                return jsonify({'error': 'Download failed'}), 500

            filepath = os.path.join(tmpdir, files[0])
            ext      = os.path.splitext(files[0])[1]
            mime     = 'audio/mpeg' if ext in ['.mp3', '.m4a'] else 'video/mp4'
            filename = f"{title}{ext}"

            def generate():
                with open(filepath, 'rb') as f:
                    while chunk := f.read(8192):
                        yield chunk

            return Response(
                generate(),
                mimetype=mime,
                headers={
                    'Content-Disposition': f'attachment; filename="{filename}"',
                    'X-Title': title,
                }
            )

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/link', methods=['POST'])
def get_link():
    """Direct stream URL apo (redirect) — Railway timeout avoid karva"""
    data         = request.get_json()
    url          = data.get('url', '').strip()
    quality      = data.get('quality', '720')
    audio_only   = data.get('audio_only', False)
    audio_format = data.get('audio_format', 'mp3')

    if not url:
        return jsonify({'error': 'URL required'}), 400

    try:
        fmt_map = {
            '2160': 'bestvideo[height<=2160][ext=mp4]+bestaudio[ext=m4a]/best[height<=2160]',
            '1080': 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080]',
            '720':  'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]',
            '480':  'bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480]',
            '360':  'bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/best[height<=360]',
        }

        if audio_only:
            fmt = 'bestaudio[ext=m4a]/bestaudio'
        else:
            fmt = fmt_map.get(quality, 'best')

        opts = {
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
            'skip_download': True,
            'format': fmt,
        }

        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get('title', 'video')

            # Get direct URL
            if 'url' in info:
                direct_url = info['url']
            elif 'requested_formats' in info:
                # Merged format — video stream URL apo
                direct_url = info['requested_formats'][0]['url']
            else:
                direct_url = None

            if not direct_url:
                return jsonify({'error': 'Stream URL mali nahi'}), 500

            return jsonify({
                'url':   direct_url,
                'title': title,
                'ext':   info.get('ext', 'mp4'),
            })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
