# main.py - RENDER VERSION (Fixed for your platform)
# Delete your old main.py and replace with this code

from flask import Flask, request, jsonify, render_template_string
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
    
    # Initialize status if empty
    cursor.execute('SELECT COUNT(*) FROM exhibition_status')
    if cursor.fetchone()[0] == 0:
        cursor.execute('INSERT INTO exhibition_status (id) VALUES (1)')
    
    conn.commit()
    conn.close()
    print("✅ Database initialized")

def get_db():
    """Get database connection"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# API Routes
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

if __name__ == '__main__':
    print("🌟 RENDER ENVIRONMENTAL ART EXHIBITION")
    print("✅ Fixed for Render platform!")
    
    # Initialize database
    init_database()
    
    print(f"✅ Starting on port {PORT}...")
    # This is the key difference for Render!
    app.run(host='0.0.0.0', port=PORT, debug=False)
