"""Local 32x8 matrix control panel; standard library server, no cloud services."""
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
import subprocess
import sys
import threading

from matrix_assets import FONT_NAMES, load_icons
from matrix_canvas import LAYOUTS, rgb_content_canvas
from matrix_probe import captured_payload

TOOLS = Path(__file__).resolve().parent


def rgb(value):
    if not isinstance(value, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        raise ValueError("Colore non valido")
    return tuple(int(value[i:i + 2], 16) for i in (1, 3, 5))


def validate_content(data):
    if not isinstance(data, dict):
        raise ValueError("Contenuto non valido")
    text = data.get("text", "")
    font = data.get("font", "spleen5x8")
    icon = data.get("icon") or None
    fill = data.get("fill_height", True)
    if not isinstance(text, str) or len(text) > 128:
        raise ValueError("Testo non valido")
    if not isinstance(font, str) or font not in FONT_NAMES:
        raise ValueError("Font non valido")
    if not isinstance(icon, (str, type(None))) or (icon is not None and icon not in load_icons()):
        raise ValueError("Icona non valida")
    if type(fill) is not bool or not (text or icon):
        raise ValueError("Inserisci una scritta o scegli un'icona")
    color = data.get("color", "#00ff50")
    icon_color = data.get("icon_color")
    canvas = rgb_content_canvas(text or None, icon, font=font, text_color=rgb(color),
                                icon_color=rgb(icon_color) if icon_color is not None else None,
                                fill_height=fill)
    return {"text": text, "font": font, "icon": icon, "fill_height": fill,
            "color": color, "icon_color": icon_color}, canvas


def display_command(data, backup, log_dir, layout):
    content, _ = validate_content(data)
    saved = json.loads(backup.read_text())
    config = captured_payload(saved, "get_symp_config_v2")
    if len(config) != 11:
        raise ValueError("Backup LED non valido")
    count = int.from_bytes(config[2:4], "big") * int.from_bytes(config[4:6], "big")
    command = [sys.executable, str(TOOLS / "matrix_probe.py"), "--backup", str(backup),
               "--count", str(count), "--single-segment", "--pause-mic",
               "--variant", "a3-zero-tail", "--layout", layout,
               "--font", content["font"], "--seconds", "0.1", "--keep-drawing",
               "--log-dir", str(log_dir), "--apply", "--color", *map(str, rgb(content["color"]))]
    if content["text"]:
        # An equals argument also handles messages beginning with '-'.
        command += ["--text=" + content["text"]]
    if content["icon"]:
        command += ["--icon", content["icon"]]
    if content["fill_height"]:
        command += ["--fill-height"]
    if content["icon_color"] is not None:
        command += ["--icon-color", *map(str, rgb(content["icon_color"]))]
    return command


class Controller:
    def __init__(self, backup, log_dir, layout, preview_only=False):
        self.backup, self.log_dir, self.layout = backup, log_dir, layout
        self.preview_only = preview_only
        self.lock = threading.Lock()
        self.state_lock = threading.Lock()
        self.state = {"busy": False, "message": "Pronto. Il pannello cambia solo quando premi Invia.",
                      "error": None, "last_content": None}

    def status(self):
        with self.state_lock:
            return dict(self.state)

    def start(self, action, data):
        if self.preview_only:
            raise ValueError("Server in sola anteprima: Bluetooth disabilitato")
        content = None
        if action == "display":
            content, _ = validate_content(data)
            command = display_command(content, self.backup, self.log_dir, self.layout)
        else:
            command = [sys.executable, str(TOOLS / "matrix_restore.py"), "--backup",
                       str(self.backup), "--retry-seconds", "30"]
        if not self.lock.acquire(blocking=False):
            return False
        with self.state_lock:
            self.state.update(busy=True, error=None,
                              message="Invio al pannello…" if action == "display" else "Ripristino della modalità sonora…")

        def worker():
            try:
                self.log_dir.mkdir(parents=True, exist_ok=True)
                result = subprocess.run(command, capture_output=True, text=True, timeout=180)
                (self.log_dir / "last-operation.log").write_text(result.stdout + result.stderr)
                if result.returncode:
                    detail = (result.stderr or result.stdout).strip().splitlines()
                    raise RuntimeError(detail[-1] if detail else "Invio non riuscito")
                with self.state_lock:
                    self.state.update(message="Schermata inviata. Resta accesa fino alla prossima modifica."
                                      if action == "display" else "Modalità sonora originale ripristinata e verificata.")
                    self.state["last_content"] = content
            except Exception as error:
                with self.state_lock:
                    self.state.update(message="Operazione non riuscita. Controlla il pannello e riprova.", error=str(error))
            finally:
                with self.state_lock:
                    self.state["busy"] = False
                self.lock.release()

        threading.Thread(target=worker, daemon=True).start()
        return True


def make_server(controller, port=8765):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def local_request(self):
            allowed = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
            host = self.headers.get("Host", "")
            origin = self.headers.get("Origin")
            return host in allowed and (origin is None or origin in {"http://" + h for h in allowed})

        def respond(self, code, data, mime="application/json; charset=utf-8"):
            body = json.dumps(data).encode() if mime.startswith("application/json") else data
            self.send_response(code)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if not self.local_request():
                return self.respond(403, {"error": "Richiesta non locale"})
            if self.path == "/":
                return self.respond(200, (TOOLS / "matrix_control.html").read_bytes(), "text/html; charset=utf-8")
            if self.path == "/api/catalog":
                return self.respond(200, {"fonts": FONT_NAMES, "icons": list(load_icons()),
                                          "preview_only": controller.preview_only})
            if self.path == "/api/status":
                return self.respond(200, controller.status())
            self.respond(404, {"error": "Pagina non trovata"})

        def do_POST(self):
            if not self.local_request():
                return self.respond(403, {"error": "Richiesta non locale"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 4096:
                    raise ValueError("Richiesta troppo grande o vuota")
                data = json.loads(self.rfile.read(length))
                if self.path == "/api/preview":
                    _, canvas = validate_content(data)
                    return self.respond(200, {"pixels": canvas})
                if self.path in ("/api/display", "/api/restore"):
                    if not controller.start(self.path.rsplit("/", 1)[1], data):
                        return self.respond(409, {"error": "Attendi il completamento dell'operazione in corso"})
                    return self.respond(202, {"accepted": True})
                return self.respond(404, {"error": "Comando non trovato"})
            except (ValueError, TypeError) as error:
                self.respond(400, {"error": str(error)})
            except Exception:
                self.respond(500, {"error": "Errore locale. Verifica il backup e i log."})

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--layout", choices=LAYOUTS, default="columns-serpentine")
    parser.add_argument("--log-dir", type=Path)
    parser.add_argument("--preview-only", action="store_true")
    args = parser.parse_args()
    if not args.preview_only and (args.backup is None or not args.backup.is_file()):
        parser.error("Serve --backup con il file originale del pannello")
    backup = args.backup.resolve() if args.backup else None
    logs = args.log_dir or ((backup.parent if backup else Path.cwd()) / "matrix-ui-logs")
    controller = Controller(backup, logs.resolve(), args.layout, args.preview_only)
    server = make_server(controller, args.port)
    print(f"Controllo pannello: http://127.0.0.1:{server.server_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
