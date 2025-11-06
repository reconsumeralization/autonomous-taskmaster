"""
Voice Command Intake Utility

Listens for voice commands and prints/logs recognized commands.
Accessible, screen-reader friendly, with TTS and desktop notification on recognition.
"""
import speech_recognition as sr
import logging
import os
import threading
from src.utils import send_desktop_notification
from src.status_window import StatusWindow

LOGS_DIR = 'logs'
os.makedirs(LOGS_DIR, exist_ok=True)
logging.basicConfig(filename=os.path.join(LOGS_DIR, 'voice_command.log'),
                    level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(message)s')

status_window = None

def listen_and_recognize():
    global status_window
    recognizer = sr.Recognizer()
    mic = sr.Microphone()
    if status_window:
        status_window.update_status('Listening', 'Active')
    print("[Voice] Listening for command. Speak now...")
    with mic as source:
        recognizer.adjust_for_ambient_noise(source)
        audio = recognizer.listen(source)
    if status_window:
        status_window.update_status('Listening', 'Processing')
    try:
        command = recognizer.recognize_google(audio)
        print(f"[Voice] Recognized: {command}")
        logging.info(f"Recognized command: {command}")
        send_desktop_notification("Voice Command", command)
        if status_window:
            status_window.update_status('TTS', 'Speaking')
        try:
            from src.core_logic import speak_and_print
            speak_and_print(f"Recognized: {command}", {})
        except Exception:
            pass
        if status_window:
            status_window.update_status('TTS', 'Idle')
        return command
    except sr.UnknownValueError:
        print("[Voice] Could not understand audio.")
        logging.warning("Could not understand audio.")
        if status_window:
            status_window.update_status('Listening', 'Idle')
    except sr.RequestError as e:
        print(f"[Voice] Recognition error: {e}")
        logging.error(f"Recognition error: {e}")
        if status_window:
            status_window.update_status('Listening', 'Idle')

# region DD Detection Stub
# INPUT: None (to be integrated with actual DD detection logic)
# OUTPUT: Updates status window DD status (simulated here)
def simulate_dd_detection():
    import time
    global status_window
    while True:
        # Simulate DD detection every 10 seconds
        if status_window:
            status_window.update_status('DD', 'Detected')
        time.sleep(2)
        if status_window:
            status_window.update_status('DD', 'Not Detected')
        time.sleep(8)
# endregion DD Detection Stub

def main():
    import argparse
    global status_window
    parser = argparse.ArgumentParser(description="Voice command intake utility.")
    parser.add_argument('--once', action='store_true', help='Listen for a single command and exit.')
    args = parser.parse_args()
    # Start status window in a separate thread
    status_window = StatusWindow()
    threading.Thread(target=status_window.run, daemon=True).start()
    # Start DD detection simulation in a separate thread
    threading.Thread(target=simulate_dd_detection, daemon=True).start()
    if args.once:
        listen_and_recognize()
    else:
        print("[Voice] Continuous mode. Press Ctrl+C to exit.")
        while True:
            listen_and_recognize()

if __name__ == '__main__':
    main() 