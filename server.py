
# Requirements: pip install flask flask-socketio eventlet pynput

from flask import Flask, send_from_directory, request
from flask_socketio import SocketIO, emit
import eventlet
import os
import socket
from contextlib import closing
from typing import Callable, Any

_PYNPUT_ERROR = None
try:
    from pynput.mouse import Controller as MouseController, Button
    from pynput.keyboard import Controller as KeyboardController, Key
    _PYNPUT_AVAILABLE = True
except Exception as exc:  # pragma: no cover - depends on environment
    MouseController = None  # type: ignore
    KeyboardController = None  # type: ignore
    Button = type("Button", (), {"left": "left", "right": "right", "middle": "middle"})  # type: ignore
    Key = type(
        "Key",
        (),
        {
            "enter": "enter",
            "tab": "tab",
            "esc": "esc",
            "escape": "escape",
            "backspace": "backspace",
            "delete": "delete",
            "space": "space",
            "up": "up",
            "down": "down",
            "left": "left",
            "right": "right",
            "home": "home",
            "end": "end",
            "page_up": "page_up",
            "page_down": "page_down",
            "ctrl": "ctrl",
            "alt": "alt",
            "shift": "shift",
            "cmd": "cmd",
        },
    )  # type: ignore
    _PYNPUT_AVAILABLE = False
    _PYNPUT_ERROR = exc

# --- Config ---
PIN_CODE = os.environ.get("MOUSE_PIN", "8900")  # set a PIN for pairing
HOST = os.environ.get("MOUSE_HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT") or os.environ.get("MOUSE_PORT", "5000"))
ENABLE_DEVICE_CONTROL = os.environ.get("ENABLE_DEVICE_CONTROL", "1").lower() in {"1", "true", "yes", "on"}


class NoOpMouse:
    def move(self, dx, dy):
        pass

    def press(self, button):
        pass

    def release(self, button):
        pass

    def click(self, button, count=1):
        pass

    def scroll(self, dx, dy):
        pass


class NoOpKeyboard:
    def type(self, text):
        pass

    def press(self, key):
        pass

    def release(self, key):
        pass


def init_devices():
    if ENABLE_DEVICE_CONTROL and _PYNPUT_AVAILABLE:
        return MouseController(), KeyboardController(), "pynput"
    reason = "disabled via ENABLE_DEVICE_CONTROL=0" if not ENABLE_DEVICE_CONTROL else f"pynput unavailable ({_PYNPUT_ERROR})"
    print(f"[WARN] Falling back to no-op input devices: {reason}")
    print("       Events will be logged but no mouse/keyboard actions will run on this host.")
    return NoOpMouse(), NoOpKeyboard(), "noop"

app = Flask(__name__, static_folder=".")
socketio = SocketIO(app, cors_allowed_origins="*")  # LAN only; PIN gate below

mouse, keyboard, INPUT_BACKEND = init_devices()

# Session auth (very light)
authorized_clients = set()

@app.route("/")
def root():
    return send_from_directory(".", "index.html")

@socketio.on("pair")
def on_pair(data):
    pin = str(data.get("pin", ""))
    if pin == PIN_CODE:
        authorized_clients.add(request.sid)
        emit("pair_ok", {"ok": True})
    else:
        emit("pair_ok", {"ok": False})

def require_auth(func: Callable[[dict], Any]) -> Callable[[dict], None]:
    def wrapper(data) -> None:
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

def pick_port(preferred_port: int) -> tuple[int, bool]:
    """Return a port that is free to bind; prefer preferred_port."""
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((HOST, preferred_port))
            return preferred_port, False
        except OSError:
            sock.bind((HOST, 0))
            return sock.getsockname()[1], True


if __name__ == "__main__":
    chosen_port, fell_back = pick_port(PORT)
    if fell_back:
        print(f"Port {PORT} in use; falling back to {chosen_port}.")
    print(f"Phone-as-Mouse running on http://<your-laptop-ip>:{chosen_port}  (PIN={PIN_CODE})")
    print(f"Input backend: {INPUT_BACKEND}")
    # Use eventlet web server for WebSocket
    socketio.run(app, host=HOST, port=chosen_port)
