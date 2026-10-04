from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
import os
import sqlite3
import requests
import uuid
import threading


load_dotenv()

app = Flask(__name__)


# =========================================================
# ENVIRONMENT VARIABLES
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
TTS_API_KEY = os.getenv("TTS_API_KEY")

TTS_URL = "https://www.kurdishtts.com/api/tts-proxy"


# =========================================================
# DATABASE
# =========================================================

DB_PATH = "/data/smart_medicine.db"

# Fallback for local computer testing
if not os.path.exists("/data"):
    os.makedirs("data", exist_ok=True)
    DB_PATH = "data/smart_medicine.db"


db_lock = threading.Lock()


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_database():

    with db_lock:

        conn = get_db()
        cursor = conn.cursor()

        # Medicine boxes
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS medicines (
                box INTEGER PRIMARY KEY,
                medicine TEXT NOT NULL DEFAULT '',
                times TEXT NOT NULL DEFAULT '[]',
                active INTEGER NOT NULL DEFAULT 0
            )
        """)

        # General settings
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

        # Commands for ESP32
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS commands (
                id TEXT PRIMARY KEY,
                command TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed INTEGER NOT NULL DEFAULT 0
            )
        """)

        # Create default medicine boxes only if they don't exist
        defaults = [
            (1, "Vitamin D", '["08:00", "20:00"]', 1),
            (2, "Medicine 2", '["14:00"]', 1),
            (3, "", "[]", 0),
            (4, "", "[]", 0)
        ]

        for box, medicine, times, active in defaults:

            cursor.execute(
                """
                INSERT OR IGNORE INTO medicines
                (box, medicine, times, active)
                VALUES (?, ?, ?, ?)
                """,
                (box, medicine, times, active)
            )

        # Default Kurdish voice text
        cursor.execute(
            """
            INSERT OR IGNORE INTO settings
            (key, value)
            VALUES (?, ?)
            """,
            (
                "voice_text",
                "کاتی خواردنی دەرمانەکەتە، تکایە دەرمانەکەت بخۆ."
            )
        )

        conn.commit()
        conn.close()


init_database()


# =========================================================
# DATABASE HELPERS
# =========================================================

def get_all_medicines():

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT box, medicine, times, active
        FROM medicines
        ORDER BY box
    """)

    rows = cursor.fetchall()

    conn.close()

    result = {}

    for row in rows:

        box = str(row["box"])

        import json

        try:
            times = json.loads(row["times"])
        except:
            times = []

        result["box" + box] = {
            "medicine": row["medicine"],
            "times": times,
            "active": bool(row["active"])
        }

    return result


def get_voice_text():

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT value FROM settings WHERE key = ?",
        ("voice_text",)
    )

    row = cursor.fetchone()

    conn.close()

    if row:
        return row["value"]

    return "کاتی خواردنی دەرمانەکەتە، تکایە دەرمانەکەت بخۆ."


# =========================================================
# KURDISH VOICE
# =========================================================

def create_and_send_voice_text(text):

    if not text:
        print("Voice text is empty.")
        return False

    headers = {
        "x-api-key": TTS_API_KEY,
        "Content-Type": "application/json"
    }

    data = {
        "text": text,
        "speaker_id": "sorani_85"
    }

    print("Creating Kurdish voice...")
    print("Text:", text)

    try:

        response = requests.post(
            TTS_URL,
            headers=headers,
            json=data,
            timeout=60
        )

    except Exception as error:

        print("TTS connection error:", error)
        return False

    print("TTS status:", response.status_code)

    if response.status_code != 200:

        print("TTS error:", response.text)

        return False

    # Store audio on Railway volume
    audio_path = "/data/medicine_voice.wav"

    if not os.path.exists("/data"):
        audio_path = "medicine_voice.wav"

    try:

        with open(audio_path, "wb") as audio_file:
            audio_file.write(response.content)

    except Exception as error:

        print("Could not save voice file:", error)

        return False

    print("Voice file created.")

    telegram_url = (
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendAudio"
    )

    try:

        with open(audio_path, "rb") as audio_file:

            files = {
                "audio": audio_file
            }

            telegram_data = {
                "chat_id": CHAT_ID
            }

            telegram_response = requests.post(
                telegram_url,
                data=telegram_data,
                files=files,
                timeout=60
            )

    except Exception as error:

        print("Telegram error:", error)

        return False

    print(
        "Telegram status:",
        telegram_response.status_code
    )

    print(
        "Telegram response:",
        telegram_response.text
    )

    return telegram_response.status_code == 200


def create_and_send_voice(medicine_name):

    text = (
        f"کاتی خواردنی {medicine_name} ە، "
        "تکایە دەرمانەکەت بخۆ."
    )

    return create_and_send_voice_text(text)


# =========================================================
# TEST VOICE
# =========================================================

@app.route("/test-voice")
def test_voice():

    success = create_and_send_voice("Vitamin D")

    if success:
        return "Voice sent successfully!"

    return "Voice sending failed!", 500


# =========================================================
# ESP32 REMINDER
# =========================================================

@app.route("/reminder", methods=["POST"])
def reminder():

    data = request.get_json() or {}

    box = str(data.get("box"))
    medicine = data.get("medicine", "")

    if box not in ["1", "2", "3", "4"]:

        return jsonify({
            "success": False,
            "message": "Invalid box"
        }), 400

    if not medicine:

        return jsonify({
            "success": False,
            "message": "Medicine name is missing"
        }), 400

    print("\n============================")
    print("REMINDER RECEIVED")
    print("============================")
    print("Box:", box)
    print("Medicine:", medicine)
    print("============================\n")

    success = create_and_send_voice(medicine)

    if success:

        return jsonify({
            "success": True,
            "message": "Reminder voice sent"
        })

    return jsonify({
        "success": False,
        "message": "Failed to send reminder voice"
    }), 500


# =========================================================
# MAIN WEB APP
# =========================================================

@app.route("/")
def home():

    return render_template("index.html")


# =========================================================
# MEDICINE STATUS
# =========================================================

@app.route("/api/status")
def status():

    medicines = get_all_medicines()

    medicines["voice_text"] = get_voice_text()

    return jsonify(medicines)


# =========================================================
# ESP32 CONFIG
# =========================================================

@app.route("/api/esp32/config")
def esp32_config():

    medicines = get_all_medicines()

    return jsonify({
        "box1": medicines["box1"],
        "box2": medicines["box2"],
        "box3": medicines["box3"],
        "box4": medicines["box4"]
    })


# =========================================================
# SAVE MEDICINE FROM WEB APP
# =========================================================

@app.route("/api/set-medicine", methods=["POST"])
def set_medicine():

    import json

    data = request.get_json() or {}

    box = str(data.get("box"))
    medicine = data.get("medicine", "").strip()
    times = data.get("times", [])

    if box not in ["1", "2", "3", "4"]:

        return jsonify({
            "success": False,
            "message": "Invalid box"
        }), 400

    if len(times) > 4:

        return jsonify({
            "success": False,
            "message": "Maximum 4 reminder times"
        }), 400

    with db_lock:

        conn = get_db()

        conn.execute(
            """
            UPDATE medicines
            SET medicine = ?,
                times = ?,
                active = ?
            WHERE box = ?
            """,
            (
                medicine,
                json.dumps(times),
                1 if medicine else 0,
                int(box)
            )
        )

        conn.commit()
        conn.close()

    print("\n============================")
    print("Medicine Updated")
    print("============================")
    print("Box:", box)
    print("Medicine:", medicine)
    print("Times:", times)
    print("============================\n")

    return jsonify({
        "success": True,
        "message": "Medicine saved successfully"
    })


# =========================================================
# ESP32 → RAILWAY MEDICINE UPDATE
# =========================================================

@app.route("/api/esp32/update-box", methods=["POST"])
def esp32_update_box():

    import json

    data = request.get_json() or {}

    box = str(data.get("box"))
    medicine = data.get("medicine", "")
    times = data.get("times", [])

    if box not in ["1", "2", "3", "4"]:

        return jsonify({
            "success": False,
            "message": "Invalid box"
        }), 400

    if len(times) > 4:

        return jsonify({
            "success": False,
            "message": "Maximum 4 reminder times"
        }), 400

    with db_lock:

        conn = get_db()

        conn.execute(
            """
            UPDATE medicines
            SET medicine = ?,
                times = ?,
                active = ?
            WHERE box = ?
            """,
            (
                medicine,
                json.dumps(times),
                1 if medicine else 0,
                int(box)
            )
        )

        conn.commit()
        conn.close()

    print("ESP32 → Flask")
    print("Box:", box)
    print("Medicine:", medicine)
    print("Times:", times)

    return jsonify({
        "success": True,
        "message": "ESP32 data saved to Flask"
    })


# =========================================================
# KURDISH VOICE TEXT
# =========================================================

@app.route("/api/voice-text", methods=["GET"])
def get_saved_voice_text():

    return jsonify({
        "success": True,
        "text": get_voice_text()
    })


@app.route("/api/voice-text", methods=["POST"])
def save_voice_text():

    data = request.get_json() or {}

    text = data.get("text", "").strip()

    if not text:

        return jsonify({
            "success": False,
            "message": "Voice text cannot be empty"
        }), 400

    with db_lock:

        conn = get_db()

        conn.execute(
            """
            INSERT OR REPLACE INTO settings
            (key, value)
            VALUES (?, ?)
            """,
            ("voice_text", text)
        )

        conn.commit()
        conn.close()

    print("Kurdish voice text saved.")

    return jsonify({
        "success": True,
        "message": "Voice text saved successfully",
        "text": text
    })


# =========================================================
# SEND SAVED KURDISH VOICE
# =========================================================

@app.route("/api/send-voice", methods=["POST"])
def send_saved_voice():

    text = get_voice_text()

    if not text:

        return jsonify({
            "success": False,
            "message": "Voice text is empty"
        }), 400

    print("\n============================")
    print("MANUAL KURDISH VOICE")
    print("============================")
    print("Text:", text)
    print("============================\n")

    success = create_and_send_voice_text(text)

    if success:

        return jsonify({
            "success": True,
            "message": "Kurdish voice sent successfully"
        })

    return jsonify({
        "success": False,
        "message": "Could not send Kurdish voice"
    }), 500


# =========================================================
# REMOTE STOP ALARM
# =========================================================

@app.route("/api/stop-alarm", methods=["POST"])
def stop_alarm():

    command_id = str(uuid.uuid4())

    with db_lock:

        conn = get_db()

        conn.execute(
            """
            INSERT INTO commands
            (id, command, completed)
            VALUES (?, ?, 0)
            """,
            (
                command_id,
                "stop_alarm"
            )
        )

        conn.commit()
        conn.close()

    print("Remote STOP ALARM command created:")
    print(command_id)

    return jsonify({
        "success": True,
        "command_id": command_id,
        "message": "Stop alarm command sent"
    })


# =========================================================
# ESP32 GET COMMAND
# =========================================================

@app.route("/api/esp32/command")
def esp32_command():

    conn = get_db()

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, command
        FROM commands
        WHERE completed = 0
        ORDER BY created_at ASC
        LIMIT 1
        """
    )

    row = cursor.fetchone()

    conn.close()

    if not row:

        return jsonify({
            "success": True,
            "command": None
        })

    return jsonify({
        "success": True,
        "command": row["command"],
        "command_id": row["id"]
    })


# =========================================================
# ESP32 ACKNOWLEDGE COMMAND
# =========================================================

@app.route("/api/esp32/command/ack", methods=["POST"])
def esp32_command_ack():

    data = request.get_json() or {}

    command_id = data.get("command_id")

    if not command_id:

        return jsonify({
            "success": False,
            "message": "Command ID missing"
        }), 400

    with db_lock:

        conn = get_db()

        conn.execute(
            """
            UPDATE commands
            SET completed = 1
            WHERE id = ?
            """,
            (command_id,)
        )

        conn.commit()
        conn.close()

    print("ESP32 acknowledged command:")
    print(command_id)

    return jsonify({
        "success": True,
        "message": "Command acknowledged"
    })


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )
