# Phone-as-Mouse

Turn a phone browser into a touchpad/keyboard for the machine that runs this server.

## Local setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python server.py
```

Useful env vars:

| Variable     | Description                         | Default |
|--------------|-------------------------------------|---------|
| `MOUSE_PIN`  | Pairing PIN that clients must enter | `8900`  |
| `MOUSE_HOST` | Interface to bind                   | `0.0.0.0` |
| `MOUSE_PORT` | Preferred local port when `PORT` is unset | `5000` |

Visit `http://<machine-ip>:<port>` from your phone and enter the PIN shown in the terminal.

> **Note:** `pynput` sends real mouse/keyboard events on the host OS. The server must run on the computer you intend to control (background SSH/terminal-only hosts will not work).

## Deploying on Railway

1. Create a new Railway project and connect this repository (or push via `railway up`).
2. Railway automatically provides a `PORT` env var; no extra config needed thanks to the `Procfile`.
3. (Optional) Add `MOUSE_PIN` to Railway's environment variables to pick your own PIN.
4. Deploy. Once the service is running, open the generated Railway domain in a mobile browser and pair with the PIN printed in the logs.

Because the app requires OS-level input access, deploying to Railway only makes sense if you expect to control that remote host.
