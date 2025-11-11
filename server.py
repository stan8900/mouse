
# Requirements: pip install flask flask-socketio eventlet pynput

from flask import Flask, send_from_directory, request
from flask_socketio import SocketIO, emit
from pynput.mouse import Controller as MouseController, Button
from pynput.keyboard import Controller as KeyboardController, Key
import eventlet
import os

# --- Config ---
PIN_CODE = os.environ.get("MOUSE_PIN", "8900")  # set a PIN for pairing
HOST = "0.0.0.0"
PORT = 5000

app = Flask(__name__, static_folder=".")
socketio = SocketIO(app, cors_allowed_origins="*")  # LAN only; PIN gate below

mouse = MouseController()
keyboard = KeyboardController()

# Session auth (very light)
authorized_clients = set()

@app.route("/")
def root():
    return send_from_directory(".", "client.html")

@socketio.on("pair")
def on_pair(data):
    pin = str(data.get("pin", ""))
    if pin == PIN_CODE:
        authorized_clients.add(request.sid)
        emit("pair_ok", {"ok": True})
    else:
        emit("pair_ok", {"ok": False})

def require_auth(func):
    def wrapper(data):
        if request.sid not in authorized_clients:
            emit("error", {"msg": "Not paired"})
            return
        func(data)
    return wrapper

@socketio.on("move")
@require_auth
def on_move(data):
    # data: {dx: float, dy: float}
    dx = float(data.get("dx", 0))
    dy = float(data.get("dy", 0))
    mouse.move(dx, dy)

@socketio.on("click")
@require_auth
def on_click(data):
    # data: {button: "left"|"right"|"middle", "down": bool}
    btn = data.get("button", "left")
    down = bool(data.get("down", True))
    button_map = {"left": Button.left, "right": Button.right, "middle": Button.middle}
    b = button_map.get(btn, Button.left)
    if down:
        mouse.press(b)
    else:
        mouse.release(b)

@socketio.on("tap")
@require_auth
def on_tap(data):
    # convenience for quick taps
    btn = data.get("button", "left")
    button_map = {"left": Button.left, "right": Button.right, "middle": Button.middle}
    b = button_map.get(btn, Button.left)
    mouse.click(b, 1)

@socketio.on("scroll")
@require_auth
def on_scroll(data):
    # data: {dx: float, dy: float}
    dx = float(data.get("dx", 0))
    dy = float(data.get("dy", 0))
    mouse.scroll(dx, dy)

@socketio.on("type_text")
@require_auth
def on_type_text(data):
    # data: {text: "string"}
    text = data.get("text", "")
    if not text:
        return
    keyboard.type(text)

@socketio.on("key")
@require_auth
def on_key(data):
    # data: {key: "enter|tab|esc|backspace|up|down|left|right|ctrl|alt|shift|cmd|win"}
    k = (data.get("key") or "").lower()
    special = {
        "enter": Key.enter,
        "tab": Key.tab,
        "esc": Key.esc,
        "escape": Key.esc,
        "backspace": Key.backspace,
        "delete": Key.delete,
        "space": Key.space,
        "up": Key.up,
        "down": Key.down,
        "left": Key.left,
        "right": Key.right,
        "home": Key.home,
        "end": Key.end,
        "pageup": Key.page_up,
        "pagedown": Key.page_down,
        "ctrl": Key.ctrl,
        "alt": Key.alt,
        "shift": Key.shift,
        "cmd": Key.cmd,   # macOS
        "win": Key.cmd,   # treat same as cmd for mac; on Windows it’s the super key
    }
    key_obj = special.get(k)
    if key_obj:
        keyboard.press(key_obj)
        keyboard.release(key_obj)

if __name__ == "__main__":
    print(f"Phone-as-Mouse running on http://<your-laptop-ip>:{PORT}  (PIN={PIN_CODE})")
    # Use eventlet web server for WebSocket
    socketio.run(app, host=HOST, port=PORT)
