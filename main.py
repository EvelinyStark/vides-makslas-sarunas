# main.py - RENDER VERSION WITH INTEGRATED CONTROL PANEL
# Replace your existing main.py with this enhanced version

from flask import Flask, request, jsonify, render_template_string, Response
import json
import os
from datetime import datetime
import sqlite3
import threading
import time

app = Flask(__name__)

# Render environment variables (you set this in Render dashboard)
API_KEY = os.environ.get('API_KEY', 'your-default-api-key')
# Render uses PORT environment variable automatically
PORT = int(os.environ.get('PORT', 10000))

DATABASE_PATH = 'exhibition.db'

def init_database():
    """Initialize SQLite database"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # Create conversations table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            speaker TEXT NOT NULL,
            text TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            turn_number INTEGER NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create exhibition status table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS exhibition_status (
            id INTEGER PRIMARY KEY DEFAULT 1,
            active INTEGER DEFAULT 0,
            current_turn INTEGER DEFAULT 0,
            current_speaker TEXT DEFAULT 'janis',
            total_messages INTEGER DEFAULT 0,
            last_update DATETIME DEFAULT CURRENT_TIMESTAMP,
            tts_mode TEXT DEFAULT 'Hugo.lv TTS',
            ai_mode TEXT DEFAULT 'Simple Fallback'
        )
    ''')
    
    # Create control commands table (NEW!)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS control_commands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            command TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            processed INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Initialize status if empty
    cursor.execute('SELECT COUNT(*) FROM exhibition_status')
    if cursor.fetchone()[0] == 0:
        cursor.execute('INSERT INTO exhibition_status (id) VALUES (1)')
    
    conn.commit()
    conn.close()
    print("✅ Database initialized with control panel support")

def get_db():
    """Get database connection"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# EXISTING API ROUTES (UNCHANGED)
@app.route('/api/add-message', methods=['POST'])
def add_message():
    """Add new conversation message"""
    try:
        data = request.get_json()
        
        if not data or data.get('api_key') != API_KEY:
            return jsonify({'error': 'Invalid API key'}), 401
        
        message = data.get('message', {})
        
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO conversations (speaker, text, timestamp, turn_number)
            VALUES (?, ?, ?, ?)
        ''', (
            message.get('speaker', ''),
            message.get('text', ''),
            message.get('timestamp', ''),
            message.get('turn', 0)
        ))
        
        cursor.execute('SELECT COUNT(*) FROM conversations')
        total = cursor.fetchone()[0]
        
        cursor.execute('''
            UPDATE exhibition_status 
            SET total_messages = ?, last_update = CURRENT_TIMESTAMP 
            WHERE id = 1
        ''', (total,))
        
        conn.commit()
        message_id = cursor.lastrowid
        conn.close()
        
        print(f"✅ Message added: {message.get('speaker')} - {message.get('text', '')[:30]}...")
        
        return jsonify({'success': True, 'message_id': message_id})
        
    except Exception as e:
        print(f"❌ Add message error: {e}")
        return jsonify({'error': 'Server error'}), 500

@app.route('/api/update-status', methods=['POST'])
def update_status():
    """Update exhibition status"""
    try:
        data = request.get_json()
        
        if not data or data.get('api_key') != API_KEY:
            return jsonify({'error': 'Invalid API key'}), 401
        
        status = data.get('status', {})
        
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE exhibition_status 
            SET active = ?, current_turn = ?, current_speaker = ?, 
                tts_mode = ?, ai_mode = ?, last_update = CURRENT_TIMESTAMP
            WHERE id = 1
        ''', (
            1 if status.get('active') else 0,
            status.get('turn', 0),
            status.get('speaker', 'janis'),
            status.get('tts_mode', 'Hugo.lv TTS'),
            status.get('ai_mode', 'Simple Fallback')
        ))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
        
    except Exception as e:
        print(f"❌ Update status error: {e}")
        return jsonify({'error': 'Server error'}), 500

@app.route('/api/conversation')
def get_conversation():
    """Get conversation data for website"""
    try:
        limit = request.args.get('limit', 50, type=int)
        
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT speaker, text, timestamp, turn_number 
            FROM conversations 
            ORDER BY id DESC 
            LIMIT ?
        ''', (limit,))
        
        messages = []
        for row in cursor.fetchall():
            messages.append({
                'speaker': row['speaker'],
                'text': row['text'],
                'timestamp': row['timestamp'],
                'turn': row['turn_number']
            })
        
        messages.reverse()
        
        cursor.execute('SELECT * FROM exhibition_status WHERE id = 1')
        status_row = cursor.fetchone()
        
        if status_row:
            status = {
                'active': bool(status_row['active']),
                'turn': status_row['current_turn'],
                'speaker': status_row['current_speaker'],
                'total_messages': status_row['total_messages'],
                'last_update': status_row['last_update'],
                'tts_mode': status_row['tts_mode'],
                'ai_mode': status_row['ai_mode']
            }
        else:
            status = {
                'active': False,
                'turn': 0,
                'speaker': 'janis',
                'total_messages': 0,
                'last_update': '',
                'tts_mode': 'Hugo.lv TTS',
                'ai_mode': 'Simple Fallback'
            }
        
        conn.close()
        
        return jsonify({
            'messages': messages,
            'status': status
        })
        
    except Exception as e:
        print(f"❌ Get conversation error: {e}")
        return jsonify({'messages': [], 'status': {'active': False, 'turn': 0, 'speaker': 'janis', 'total_messages': 0}})

@app.route('/api/clear-history', methods=['POST'])
def clear_history():
    """Clear conversation history"""
    try:
        data = request.get_json()
        
        if not data or data.get('api_key') != API_KEY:
            return jsonify({'error': 'Invalid API key'}), 401
        
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM conversations')
        cursor.execute('''
            UPDATE exhibition_status 
            SET current_turn = 0, total_messages = 0, current_speaker = 'janis',
                last_update = CURRENT_TIMESTAMP
            WHERE id = 1
        ''')
        
        conn.commit()
        conn.close()
        
        print("✅ History cleared")
        
        return jsonify({'success': True})
        
    except Exception as e:
        print(f"❌ Clear history error: {e}")
        return jsonify({'error': 'Server error'}), 500

@app.route('/api/stats')
def get_stats():
    """Get exhibition statistics"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM conversations')
        total_messages = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM conversations WHERE speaker = 'janis'")
        janis_messages = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM conversations WHERE speaker = 'anna'")
        anna_messages = cursor.fetchone()[0]
        
        conn.close()
        
        return jsonify({
            'total_messages': total_messages,
            'janis_messages': janis_messages,
            'anna_messages': anna_messages
        })
        
    except Exception as e:
        print(f"❌ Stats error: {e}")
        return jsonify({'total_messages': 0, 'janis_messages': 0, 'anna_messages': 0})

# NEW CONTROL PANEL ROUTES
# ========================

@app.route('/control')
def control_panel():
    """Private management control panel"""
    return render_template_string('''
<!DOCTYPE html>
<html>
<head>
    <title>🎛️ Exhibition Control Panel</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inconsolata:wght@200..900&display=swap" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: "Inconsolata", monospace;
            background: linear-gradient(135deg, #1a1a2e, #16213e, #0f0f23);
            color: white;
            min-height: 100vh;
            padding: 20px;
        }
        .container { max-width: 900px; margin: 0 auto; }
        .header { 
            text-align: center; 
            margin-bottom: 30px;
            padding: 30px;
            background: linear-gradient(135deg, rgba(255,255,255,0.1), rgba(255,255,255,0.05));
            border-radius: 15px;
            backdrop-filter: blur(10px);
        }
        .header h1 { 
            font-size: 2.5rem; 
            margin-bottom: 10px;
            background: linear-gradient(45deg, #4CAF50, #2196F3);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        .status-panel { 
            background: linear-gradient(135deg, rgba(255,255,255,0.1), rgba(255,255,255,0.05));
            padding: 25px;
            border-radius: 15px;
            margin: 20px 0;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.1);
        }
        .status-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-top: 15px;
        }
        .status-item {
            background: rgba(255,255,255,0.1);
            padding: 15px;
            border-radius: 10px;
            text-align: center;
        }
        .status-label { font-size: 0.9rem; opacity: 0.7; margin-bottom: 5px; }
        .status-value { font-size: 1.3rem; font-weight: bold; color: #4CAF50; }
        .controls { 
            display: flex;
            flex-wrap: wrap;
            justify-content: center;
            gap: 15px;
            margin: 30px 0;
        }
        .btn { 
            padding: 15px 25px;
            font-size: 16px;
            font-weight: bold;
            border: none;
            border-radius: 10px;
            cursor: pointer;
            color: white;
            transition: all 0.3s ease;
            min-width: 150px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.2);
        }
        .btn:hover { transform: translateY(-2px); box-shadow: 0 6px 20px rgba(0,0,0,0.3); }
        .btn:active { transform: translateY(0); }
        .btn:disabled { opacity: 0.6; cursor: not-allowed; transform: none; }
        .btn-start { background: linear-gradient(45deg, #4CAF50, #45a049); }
        .btn-stop { background: linear-gradient(45deg, #f44336, #da190b); }
        .btn-clear { background: linear-gradient(45deg, #607D8B, #455A64); }
        .btn-download { background: linear-gradient(45deg, #FF9800, #F57C00); }
        .btn-refresh { background: linear-gradient(45deg, #2196F3, #1976D2); }
        .log-panel {
            background: linear-gradient(135deg, rgba(0,0,0,0.4), rgba(0,0,0,0.2));
            padding: 20px;
            border-radius: 15px;
            margin: 20px 0;
        }
        .log-content {
            background: #111;
            padding: 15px;
            border-radius: 8px;
            height: 250px;
            overflow-y: auto;
            font-family: 'Consolas', 'Monaco', monospace;
            font-size: 13px;
            line-height: 1.4;
        }
        .log-content::-webkit-scrollbar { width: 8px; }
        .log-content::-webkit-scrollbar-track { background: #333; border-radius: 4px; }
        .log-content::-webkit-scrollbar-thumb { background: #666; border-radius: 4px; }
        .back-link {
            display: inline-block;
            margin-top: 20px;
            padding: 10px 20px;
            background: rgba(255,255,255,0.1);
            color: #4CAF50;
            text-decoration: none;
            border-radius: 8px;
            transition: all 0.3s ease;
        }
        .back-link:hover { background: rgba(255,255,255,0.2); }
        .footer {
            text-align: center;
            margin-top: 40px;
            padding: 20px;
            opacity: 0.6;
            border-top: 1px solid rgba(255,255,255,0.1);
        }
        @media (max-width: 768px) {
            .controls { flex-direction: column; align-items: center; }
            .btn { width: 100%; max-width: 300px; }
            .status-grid { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎛️ Exhibition Control Panel</h1>
            <p>Private Management Interface</p>
            <p style="font-size: 0.9rem; opacity: 0.7;">Control your AI conversation exhibition remotely</p>
        </div>
        
        <div class="status-panel">
            <h3>📊 Current Exhibition Status</h3>
            <div class="status-grid">
                <div class="status-item">
                    <div class="status-label">Exhibition Status</div>
                    <div class="status-value" id="current-status">Loading...</div>
                </div>
                <div class="status-item">
                    <div class="status-label">Current Turn</div>
                    <div class="status-value" id="current-turn">-</div>
                </div>
                <div class="status-item">
                    <div class="status-label">Active Speaker</div>
                    <div class="status-value" id="current-speaker">-</div>
                </div>
                <div class="status-item">
                    <div class="status-label">Total Messages</div>
                    <div class="status-value" id="total-messages">-</div>
                </div>
            </div>
        </div>
        
        <div class="controls">
            <button class="btn btn-start" onclick="sendCommand('start')">
                🚀 START EXHIBITION
            </button>
            <button class="btn btn-stop" onclick="sendCommand('stop')">
                ⏹️ STOP EXHIBITION
            </button>
            <button class="btn btn-clear" onclick="sendCommand('clear')">
                🗑️ CLEAR HISTORY
            </button>
            <button class="btn btn-download" onclick="downloadHistory()">
                📄 DOWNLOAD HISTORY
            </button>
            <button class="btn btn-refresh" onclick="refreshStatus()">
                🔄 REFRESH STATUS
            </button>
        </div>
        
        <div class="log-panel">
            <h3>📝 Activity Log</h3>
            <div class="log-content" id="log">
                <div style="color: #4CAF50;">[''' + datetime.now().strftime('%H:%M:%S') + '''] Control panel loaded successfully</div>
                <div style="color: #2196F3;">[''' + datetime.now().strftime('%H:%M:%S') + '''] Ready to manage exhibition</div>
            </div>
        </div>
        
        <div style="text-align: center;">
            <a href="/" class="back-link">← Back to Public Exhibition View</a>
        </div>
        
        <div class="footer">
            <p>🌍 Remote Exhibition Control - Integrated with Your Render Service</p>
            <p>Access from anywhere to manage your AI conversation exhibition</p>
        </div>
    </div>
    
    <script>
        function log(message, type = 'info') {
            const timestamp = new Date().toLocaleTimeString();
            const colors = {
                'info': '#ffffff',
                'success': '#4CAF50', 
                'error': '#f44336',
                'warning': '#FF9800',
                'command': '#2196F3'
            };
            
            const logDiv = document.getElementById('log');
            const newLog = document.createElement('div');
            newLog.style.color = colors[type] || colors.info;
            newLog.innerHTML = `[${timestamp}] ${message}`;
            
            logDiv.insertBefore(newLog, logDiv.firstChild);
            
            while (logDiv.children.length > 50) {
                logDiv.removeChild(logDiv.lastChild);
            }
        }
        
        function sendCommand(command) {
            log(`Sending command: ${command.toUpperCase()}`, 'command');
            
            const button = event.target;
            const originalText = button.innerHTML;
            button.innerHTML = '⏳ Sending...';
            button.disabled = true;
            
            fetch('/control/api/command', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({command: command})
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    log(`✅ ${data.message}`, 'success');
                    setTimeout(refreshStatus, 2000);
                } else {
                    log(`❌ Command failed: ${data.message}`, 'error');
                }
            })
            .catch(error => {
                log(`❌ Network error: ${error.message}`, 'error');
            })
            .finally(() => {
                button.innerHTML = originalText;
                button.disabled = false;
            });
        }
        
        function downloadHistory() {
            log('📄 Starting download...', 'info');
            
            const link = document.createElement('a');
            link.href = '/control/api/download';
            link.download = `exhibition_conversation_${new Date().toISOString().split('T')[0]}.txt`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            
            log('✅ Download initiated', 'success');
        }
        
        function refreshStatus() {
            log('🔄 Refreshing status...', 'info');
            
            fetch('/api/conversation')
            .then(response => response.json())
            .then(data => {
                if (data.status) {
                    document.getElementById('current-status').textContent = 
                        data.status.active ? 'Running' : 'Stopped';
                    document.getElementById('current-turn').textContent = data.status.turn || 0;
                    document.getElementById('current-speaker').textContent = 
                        data.status.speaker === 'janis' ? '👾 Jānis' : 
                        data.status.speaker === 'anna' ? '🎭 Anna' : data.status.speaker;
                    document.getElementById('total-messages').textContent = data.status.total_messages || 0;
                    
                    const statusElement = document.getElementById('current-status');
                    if (data.status.active) {
                        statusElement.style.color = '#4CAF50';
                    } else {
                        statusElement.style.color = '#f44336';
                    }
                }
                
                log('✅ Status updated', 'success');
            })
            .catch(error => {
                log(`❌ Status update failed: ${error.message}`, 'error');
                document.getElementById('current-status').textContent = 'Connection Error';
                document.getElementById('current-status').style.color = '#f44336';
            });
        }
        
        setInterval(refreshStatus, 10000);
        refreshStatus();
        
        log('🎛️ Control panel initialized', 'success');
        log('🌍 Ready for remote exhibition management', 'info');
    </script>
</body>
</html>
    ''')

@app.route('/control/api/command', methods=['POST'])
def handle_control_command():
    """Handle control commands from management panel"""
    try:
        data = request.get_json()
        command = data.get('command')
        
        if not command:
            return jsonify({
                'status': 'error',
                'message': 'No command provided'
            }), 400
        
        valid_commands = ['start', 'stop', 'clear', 'refresh']
        if command not in valid_commands:
            return jsonify({
                'status': 'error',
                'message': f'Invalid command: {command}'
            }), 400
        
        conn = get_db()
        cursor = conn.cursor()
        
        # Store command for your main script to process
        cursor.execute('''
            INSERT INTO control_commands (command, timestamp)
            VALUES (?, ?)
        ''', (command, datetime.now().isoformat()))
        
        # Update status immediately for UI feedback
        if command == 'start':
            cursor.execute('''
                UPDATE exhibition_status 
                SET active = 1, last_update = CURRENT_TIMESTAMP
                WHERE id = 1
            ''')
        elif command == 'stop':
            cursor.execute('''
                UPDATE exhibition_status 
                SET active = 0, last_update = CURRENT_TIMESTAMP
                WHERE id = 1
            ''')
        elif command == 'clear':
            cursor.execute('DELETE FROM conversations')
            cursor.execute('''
                UPDATE exhibition_status 
                SET current_turn = 0, total_messages = 0, current_speaker = 'janis',
                    last_update = CURRENT_TIMESTAMP
                WHERE id = 1
            ''')
        
        conn.commit()
        conn.close()
        
        print(f"🎛️ Control command received: {command}")
        
        return jsonify({
            'status': 'success',
            'message': f'Command {command} processed successfully'
        })
        
    except Exception as e:
        print(f"❌ Control command error: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Server error: {str(e)}'
        }), 500

@app.route('/control/api/download')
def download_control_history():
    """Download conversation history from control panel"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT speaker, text, timestamp, turn_number 
            FROM conversations 
            ORDER BY id ASC
        ''')
        
        messages = cursor.fetchall()
        
        if not messages:
            content = """🎨 JĀŅA & ANNAS VIDES MĀKSLAS SARUNAS
Environmental Art Exhibition - Conversation History
========================================================

No conversation history available yet.

To populate this download:
1. Start the exhibition using your main script
2. Let the AI conversation run
3. Download again to get full conversation

========================================================
Downloaded from: Exhibition Control Panel
Export Time: """ + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + """
========================================================"""
        else:
            content_lines = []
            content_lines.append("🎨 JĀŅA & ANNAS VIDES MĀKSLAS SARUNAS")
            content_lines.append("Environmental Art Exhibition - Conversation History")
            content_lines.append("=" * 60)
            content_lines.append(f"Export Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            content_lines.append(f"Total Messages: {len(messages)}")
            content_lines.append("=" * 60)
            content_lines.append("")
            
            for i, msg in enumerate(messages, 1):
                speaker_name = "🎨 JĀNIS" if msg['speaker'] == 'janis' else "🎭 ANNA"
                
                content_lines.append(f"[{msg['timestamp']}] {speaker_name} (Turn {msg['turn_number']}):")
                content_lines.append("-" * 50)
                
                # Word wrap for readability
                words = msg['text'].split()
                lines = []
                current_line = []
                for word in words:
                    if len(' '.join(current_line + [word])) <= 70:
                        current_line.append(word)
                    else:
                        if current_line:
                            lines.append(' '.join(current_line))
                        current_line = [word]
                if current_line:
                    lines.append(' '.join(current_line))
                
                for line in lines:
                    content_lines.append(line)
                content_lines.append("")
            
            content_lines.append("=" * 60)
            content_lines.append("🌍 Downloaded from Exhibition Control Panel")
            content_lines.append("🇱🇻 Paldies for exploring environmental art!")
            content_lines.append("=" * 60)
            
            content = "\n".join(content_lines)
        
        conn.close()
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"exhibition_conversation_{timestamp}.txt"
        
        print(f"📄 Download requested from control panel: {filename}")
        
        return Response(
            content,
            mimetype='text/plain; charset=utf-8',
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"',
                'Content-Type': 'text/plain; charset=utf-8'
            }
        )
        
    except Exception as e:
        print(f"❌ Control download error: {e}")
        return Response(
            f"Download error: {str(e)}",
            mimetype='text/plain',
            status=500
        )

# EXISTING HOME ROUTE (UNCHANGED)
@app.route('/')
def home():
    """Beautiful exhibition homepage"""
    return render_template_string("""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Jāņa & Annas Vides Mākslas Sarunas | Environmental Art Exhibition</title>
    <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>✨</text></svg>">
    <link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inconsolata:wght@200..900&family=Pixelify+Sans&display=swap" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: "Inconsolata", monospace;
            background: rgba(0, 0, 0, 0.9);
            color: #fff;
            min-height: 100vh;
            overflow-x: hidden;
            line-height: 1.6;
        }
        
        .header {
            text-align: center;
            padding: 60px 20px;
            background: rgba(255,255,255,0.03);
            backdrop-filter: blur(20px);
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        
        .title {
            font-size: clamp(2.5em, 8vw, 4em);
            font-weight: 200;
            margin-bottom: 15px;
            background: linear-gradient(135deg, #4CAF50, #2196F3, #FF5722, #9C27B0);
            background-size: 400% 400%;
            animation: gradientFlow 8s ease infinite;
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        
        .subtitle {
            font-size: clamp(1.1em, 3vw, 1.4em);
            opacity: 0.9;
            margin-bottom: 15px;
        }
        
        .description {
            font-size: clamp(0.9em, 2.5vw, 1.1em);
            opacity: 0.7;
            max-width: 600px;
            margin: 0 auto 30px;
        }
        
        .status-bar {
            display: flex;
            justify-content: center;
            gap: 20px;
            flex-wrap: wrap;
            margin-top: 30px;
        }
        
        .status-item {
            padding: 12px 24px;
            background: rgba(255,255,255,0.08);
            border-radius: 25px;
            backdrop-filter: blur(10px);
            font-size: 0.9em;
            border: 1px solid rgba(255,255,255,0.1);
        }
        
        .status-live {
            background: rgba(76, 175, 80, 0.2);
            border-color: #4CAF50;
            animation: pulse 3s infinite;
        }
        
        .conversation-container {
            max-width: 1400px;
            margin: 30px auto;
            padding: 0 20px;
        }
        
        .current-message {
            background: rgba(255,255,255,0.06);
            backdrop-filter: blur(15px);
            border-radius: 10px;
            padding: 20px;
            margin: 30px 0;
            min-height: 250px;
            display: flex;
            align-items: center;
            justify-content: center;
            text-align: center;
            font-size: clamp(1.4em, 4vw, 2.2em);
            line-height: 1.4;
            border: 1px solid rgba(255,255,255,0.1);
        }
        
        .janis-message {
            border-left: 6px solid #2196F3;
            background: rgba(33, 150, 243, 0.1);
        }
        
        .anna-message {
            border-left: 6px solid #FF5722;
            background: rgba(255, 87, 34, 0.1);
        }
        
        .connection-status {
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 10px 16px;
            border-radius: 20px;
            font-size: 0.8em;
            z-index: 1000;
        }
        
        .connected { background: rgba(76, 175, 80, 0.9); }
        .disconnected { background: rgba(244, 67, 54, 0.9); }
        
        @keyframes gradientFlow {
            0% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
            100% { background-position: 0% 50%; }
        }
        
        @keyframes pulse {
            0% { box-shadow: 0 0 0 0 rgba(76, 175, 80, 0.4); }
            70% { box-shadow: 0 0 0 15px rgba(76, 175, 80, 0); }
            100% { box-shadow: 0 0 0 0 rgba(76, 175, 80, 0); }
        }
    </style>
</head>
<body>
    <div class="connection-status" id="connectionStatus">🔗 savienojas...</div>
    
    <div class="header">
        <h1 class="title">Vides Mākslas Sarunas</h1>
        <p class="subtitle">Jānis & Anna - Vides mākslas sarunas un pārdomas</p>
        <p class="description">
            Dzīvā saruna ar diviem AI par vides mākslu un telpu filazofiju
        </p>
        
        <div class="status-bar">
            <div class="status-item" id="statusIndicator">⏸️ Gaida</div>
            <div class="status-item">Kārta: <span id="turnCount">0</span></div>
            <div class="status-item">Sarunas: <span id="messageCount">0</span></div>
        </div>
    </div>
    
    <div class="conversation-container">
        <div id="currentMessage" class="current-message">
            <div>
                <div>Waiting for the conversation to begin...</div>
                <div style="font-size: 0.6em; opacity: 0.7; margin-top: 20px;">
                    The AI artists are preparing their environmental art dialogue
                </div>
            </div>
        </div>
    </div>
    
    <script>
        let isConnected = false;
        
        async function updateExhibition() {
            try {
                const response = await fetch('/api/conversation');
                const data = await response.json();
                
                // Update connection status
                document.getElementById('connectionStatus').textContent = '🟢 Tiešraidē';
                document.getElementById('connectionStatus').className = 'connection-status connected';
                isConnected = true;
                
                // Update status bar
                if (data.status) {
                    const isActive = data.status.active;
                    document.getElementById('statusIndicator').textContent = 
                        isActive ? '🟢 Tiešraides saruna' : '⏸️ Pauze';
                    document.getElementById('statusIndicator').className = 
                        isActive ? 'status-item status-live' : 'status-item';
                    document.getElementById('turnCount').textContent = data.status.turn || 0;
                    document.getElementById('messageCount').textContent = data.status.total_messages || 0;
                }
                
                // Update current message
                if (data.messages && data.messages.length > 0) {
                    const latestMessage = data.messages[data.messages.length - 1];
                    const currentMessageDiv = document.getElementById('currentMessage');
                    
                    const speakerName = latestMessage.speaker === 'janis' ? '👾 JĀNIS AI' : '🤖 ANNA AI';
                    const speakerRole = latestMessage.speaker === 'janis' ? 'Telpu filazofija' : 'Virtuālas vides pārdomas';
                    const messageClass = latestMessage.speaker === 'janis' ? 'janis-atbild' : 'anna-atbild';
                    
                    currentMessageDiv.className = `current-message ${messageClass}`;
                    currentMessageDiv.innerHTML = `
                        <div>
                            <div style="font-size: 0.6em; opacity: 0.7; margin-bottom: 8px;">${speakerRole}</div>
                            <div style="font-size: 0.8em; opacity: 0.9; margin-bottom: 20px; font-weight: 600;">${speakerName}</div>
                            <div>${latestMessage.text}</div>
                            <div style="font-size: 0.5em; opacity: 0.5; margin-top: 20px;">${latestMessage.timestamp}</div>
                        </div>
                    `;
                } else if (isConnected) {
                    document.getElementById('currentMessage').innerHTML = `
                        <div>
                            <div>Savienots ar mākslas instalāciju</div>
                            <div style="font-size: 0.6em; opacity: 0.7; margin-top: 20px;">
                                Gaida Jāņa un Annas sarunas dialogu...
                            </div>
                        </div>
                    `;
                }
                
            } catch (error) {
                console.error('Connection error:', error);
                
                // Update connection status
                document.getElementById('connectionStatus').textContent = '🔴 Bezsaistē';
                document.getElementById('connectionStatus').className = 'connection-status disconnected';
                isConnected = false;
                
                document.getElementById('currentMessage').innerHTML = `
                    <div>
                        <div style="color: #ff6b6b;">🔌 Savienojums zaudēts ar serveri</div>
                        <div style="font-size: 0.6em; opacity: 0.6; margin-top: 15px;">
                            Attempting to reconnect...
                        </div>
                    </div>
                `;
            }
        }
        
        // Update every 2 seconds
        setInterval(updateExhibition, 2000);
        updateExhibition(); // Initial load
    </script>
</body>
</html>
    """)

# HELPER FUNCTIONS FOR YOUR MAIN SCRIPT INTEGRATION
# =================================================

def check_control_commands():
    """
    Call this function in your main script to check for control commands
    """
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Get unprocessed commands
        cursor.execute('''
            SELECT id, command, timestamp 
            FROM control_commands 
            WHERE processed = 0 
            ORDER BY id ASC
        ''')
        
        commands = cursor.fetchall()
        
        for cmd in commands:
            command = cmd['command']
            print(f"🎛️ Processing control command: {command}")
            
            if command == 'start':
                # Your code to start exhibition
                print("🚀 Exhibition started by control panel")
                # Add your start logic here
                
            elif command == 'stop':
                # Your code to stop exhibition
                print("⏹️ Exhibition stopped by control panel")
                # Add your stop logic here
                
            elif command == 'clear':
                # Your code to clear conversation history
                print("🗑️ History cleared by control panel")
                # Add your clear logic here
            
            # Mark command as processed
            cursor.execute('''
                UPDATE control_commands 
                SET processed = 1 
                WHERE id = ?
            ''', (cmd['id'],))
        
        conn.commit()
        conn.close()
        
        return [cmd['command'] for cmd in commands]
        
    except Exception as e:
        print(f"❌ Command processing error: {e}")
        return []

if __name__ == '__main__':
    print("🌟 RENDER ENVIRONMENTAL ART EXHIBITION WITH CONTROL PANEL")
    print("✅ Enhanced version with remote control capability!")
    
    # Initialize database
    init_database()
    
    print(f"✅ Starting on port {PORT}...")
    print(f"🌐 Public Exhibition: https://your-service.onrender.com")
    print(f"🎛️ Control Panel: https://your-service.onrender.com/control")
    
    # This is the key difference for Render!
    app.run(host='0.0.0.0', port=PORT, debug=False)