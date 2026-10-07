from flask import Flask, render_template, request, jsonify 
from dotenv import load_dotenv 
import os 
import requests 
 
 
load_dotenv() 
 
app = Flask(__name__) 
 
 
BOT_TOKEN = os.getenv("BOT_TOKEN") 
CHAT_ID = os.getenv("CHAT_ID") 
TTS_API_KEY = os.getenv("TTS_API_KEY") 
 
TTS_URL = "https://www.kurdishtts.com/api/tts-proxy"



def create_and_send_voice(medicine_name):

    text = f"کاتی خواردنی {medicine_name} ە، تکایە دەرمانەکەت بخۆ."

    headers = {
        "x-api-key": TTS_API_KEY,
        "Content-Type": "application/json"
    }

    data = {
        "text": text,
        "speaker_id": "sorani_85"
    }

    print("Creating Kurdish voice...")

    response = requests.post(
        TTS_URL,
        headers=headers,
        json=data
    )

    print("TTS status:", response.status_code)

    if response.status_code != 200:
        print("TTS error:", response.text)
        return False

    with open("medicine_voice.wav", "wb") as audio_file:
        audio_file.write(response.content)

    print("Voice file created.")

    telegram_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendAudio"

    with open("medicine_voice.wav", "rb") as audio_file:

        files = {
            "audio": audio_file
        }

        data = {
            "chat_id": CHAT_ID
        }

        telegram_response = requests.post(
            telegram_url,
            data=data,
            files=files
        )

    print("Telegram status:", telegram_response.status_code)
    print("Telegram response:", telegram_response.text)

    return telegram_response.status_code == 200


# ---------------------------------
# Test Kurdish Voice
# ---------------------------------

@app.route("/test-voice")
def test_voice():

    success = create_and_send_voice("Vitamin D")

    if success:
        return "Voice sent successfully!"

    return "Voice sending failed!", 500


@app.route("/reminder", methods=["POST"])
def reminder():

    data = request.get_json()

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

# ---------------------------------
# Temporary medicine data
# ---------------------------------

medicines = {

    "box1": {
        "medicine": "Vitamin D",
        "times": ["08:00", "20:00"],
        "active": True
    },

    "box2": {
        "medicine": "Medicine 2",
        "times": ["14:00"],
        "active": True
    },

    "box3": {
        "medicine": "",
        "times": [],
        "active": False
    },

    "box4": {
        "medicine": "",
        "times": [],
        "active": False
    }
}


# ---------------------------------
# Main Web App
# ---------------------------------

@app.route("/")
def home():

    return render_template("index.html")


# ---------------------------------
# Get medicine status
# ---------------------------------

@app.route("/api/status")
def status():

    return jsonify(medicines)


@app.route("/api/esp32/config")
def esp32_config():

    return jsonify({
        "box1": medicines["box1"],
        "box2": medicines["box2"],
        "box3": medicines["box3"],
        "box4": medicines["box4"]
    })



# ---------------------------------
# Save medicine
# ---------------------------------

@app.route("/api/set-medicine", methods=["POST"])
def set_medicine():

    data = request.get_json()

    box = str(data.get("box"))

    medicine = data.get("medicine", "")

    times = data.get("times", [])


    if box not in ["1", "2", "3", "4"]:

        return jsonify({
            "success": False,
            "message": "Invalid box"
        })


    if len(times) > 4:

        return jsonify({
            "success": False,
            "message": "Maximum 4 reminder times"
        })


    medicines["box" + box] = {

        "medicine": medicine,

        "times": times,

        "active": bool(medicine)

    }


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


@app.route("/api/esp32/update-box", methods=["POST"])
def esp32_update_box():
    data = request.get_json()

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

    medicines["box" + box] = {
        "medicine": medicine,
        "times": times,
        "active": bool(medicine)
    }

    print("ESP32 → Flask")
    print("Box:", box)
    print("Medicine:", medicine)
    print("Times:", times)

    return jsonify({
        "success": True,
        "message": "ESP32 data saved to Flask"
    })


# ---------------------------------
# Run Flask
# ---------------------------------

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )
