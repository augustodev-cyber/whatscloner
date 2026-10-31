import json
import logging
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import queue
import uuid
import webbrowser
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, render_template, send_file
from werkzeug.serving import make_server

from core.monitor import QRMonitor


APP_NAME = "WhatsCloner"
APP_VERSION = "1.0"
APP_AUTHOR = "augustodev-cyber"
GITHUB_URL = "https://github.com/augustodev-cyber"

DEFAULT_SOURCE_URL = "https://web.whatsapp.com/"
DEFAULT_QR_SELECTOR = "auto"
DEFAULT_POLL_INTERVAL = 1.0
DEFAULT_BROWSER_HEADLESS = False
DEFAULT_SERVER_PORT = 5000
DEFAULT_EXPOSURE = "local"  # local | lan | cloudflare

OPEN_DASHBOARD_ON_NEW_SESSION = True


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
SESSION_FILE = DATA_DIR / "sessions.json"
SESSION_PROFILES_DIR = DATA_DIR / "browser_profiles"
DATA_DIR.mkdir(parents=True, exist_ok=True)
SESSION_PROFILES_DIR.mkdir(parents=True, exist_ok=True)

logging.getLogger("werkzeug").disabled = True
logging.getLogger("werkzeug").setLevel(logging.CRITICAL)
logging.getLogger("qrcode_mirror").setLevel(logging.CRITICAL)

app = Flask(__name__, template_folder=str(ROOT / "layouts"))
app.logger.disabled = True
app.config["PROPAGATE_EXCEPTIONS"] = False

monitor: QRMonitor | None = None
monitor_thread: threading.Thread | None = None
active_session_name: str | None = None


# ============================================================
# TERMINAL E MENU POR SETAS
# ============================================================
def clear_screen() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def pause(message: str = "Pressione ENTER para continuar...") -> None:
    input(f"\n{message}")
    clear_screen()


def read_key() -> str:
    if os.name == "nt":
        import msvcrt
        key = msvcrt.getch()
        if key in (b"\x00", b"\xe0"):
            key = msvcrt.getch()
            return {b"H": "UP", b"P": "DOWN", b"K": "LEFT", b"M": "RIGHT"}.get(key, "UNKNOWN")
        if key in (b"\r", b"\n"):
            return "ENTER"
        if key == b"\x1b":
            return "ESC"
        return key.decode("utf-8", errors="ignore").upper()

    import termios
    import tty
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        key = sys.stdin.read(1)
        if key == "\x1b":
            second = sys.stdin.read(1)
            if second == "[":
                third = sys.stdin.read(1)
                return {"A": "UP", "B": "DOWN", "C": "RIGHT", "D": "LEFT"}.get(third, "UNKNOWN")
            return "ESC"
        if key in ("\r", "\n"):
            return "ENTER"
        return key.upper()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def print_banner() -> None:
    print("\033[92m")
    print(r"""

             ========             
         =================        
      =====            =====      
    =====                 ====    
   ====    ===              ===   
  ====   =====               ===  
  ===    ======               === 
 ===      ====                === 
 ===       ====               === 
 ====       =====    ==       === 
  ===         ============    === 
   ===           ========    ===  
   ====                    ====   
   ===                   =====    
  ===========        -======      
 ======== ===============         
 ==                               
 
 """)
    print("\033[0m")
    print(f"\033[92m  {APP_NAME} \033[0mProfessional ✔ |  v{APP_VERSION}")
    print("  \033[93mNão nos responsabilizamos pelo uso indevido\033[0m")
    print("  " + "─" * 59)
    print(f"  Autor : {APP_AUTHOR} \033[92m ✔\033[0m")
    print(f"  GitHub: \033[94m{GITHUB_URL}\033[0m")
    print("  " + "─" * 59)


def select_menu(title: str, items: list[dict], selected: int = 0) -> int | None:
    if not items:
        return None
    selectable = [i for i, item in enumerate(items) if not item.get("separator")]
    if not selectable:
        return None
    selected = selected if selected in selectable else selectable[0]

    while True:
        clear_screen()
        print_banner()
        print(title)
        print("─" * 59)
        for index, item in enumerate(items):
            if item.get("separator"):
                print("  " + "─" * 55)
            else:
                pointer = ">" if index == selected else " "
                print(f"  {pointer} {item['label']}")
        print("\n  ↑/↓ Navegar    ENTER Selecionar    ESC Voltar")

        key = read_key()
        if key in ("UP", "DOWN"):
            pos = selectable.index(selected)
            pos = (pos + (-1 if key == "UP" else 1)) % len(selectable)
            selected = selectable[pos]
        elif key == "ENTER":
            return selected
        elif key == "ESC":
            return None


def spinner(label: str, duration: float = 0.8) -> None:
    frames = ("|", "/", "-", "\\")
    end = time.monotonic() + duration
    while time.monotonic() < end:
        for frame in frames:
            sys.stdout.write(f"\r  {frame} {label}")
            sys.stdout.flush()
            time.sleep(0.09)
            if time.monotonic() >= end:
                break
    sys.stdout.write(f"\r  [OK] {label}\n")
    sys.stdout.flush()


# ============================================================
# CONFIGURACOES E SESSOES
# ============================================================
def current_config() -> dict:
    return {
        "source_url": DEFAULT_SOURCE_URL,
        "selector": DEFAULT_QR_SELECTOR,
        "interval": DEFAULT_POLL_INTERVAL,
        "headless": DEFAULT_BROWSER_HEADLESS,
        "port": DEFAULT_SERVER_PORT,
        "exposure": DEFAULT_EXPOSURE,
        "_profile_id": None,
        "_session_name": None,
    }


def normalize_config(config: dict | None) -> dict:
    result = current_config()
    if isinstance(config, dict):
        result.update({key: value for key, value in config.items() if key in result})
    result["source_url"] = str(result["source_url"] or "").strip()
    result["selector"] = str(result["selector"] or "auto").strip()
    result["port"] = max(1, min(65535, int(result["port"])))
    result["interval"] = max(0.5, float(result["interval"]))
    if result["exposure"] not in {"local", "lan", "cloudflare"}:
        result["exposure"] = "local"
    return result


def new_profile_id() -> str:
    return uuid.uuid4().hex


def valid_profile_id(value: str | None) -> str:
    if value and re.fullmatch(r"[a-fA-F0-9]{32}", str(value)):
        return str(value)
    return new_profile_id()


def profile_path(profile_id: str) -> Path:
    path = (SESSION_PROFILES_DIR / valid_profile_id(profile_id)).resolve()
    if SESSION_PROFILES_DIR.resolve() not in path.parents:
        raise ValueError("Diretorio de perfil invalido.")
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_sessions() -> dict:
    try:
        data = json.loads(SESSION_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def write_sessions(sessions: dict) -> None:
    temp = SESSION_FILE.with_suffix(".tmp")
    temp.write_text(json.dumps(sessions, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(SESSION_FILE)


def migrate_sessions() -> dict:
    raw = read_sessions()
    result = {}
    for name, entry in raw.items():
        if not isinstance(name, str) or not isinstance(entry, dict):
            continue
        if "config" in entry:
            cfg = entry.get("config", {})
            pid = entry.get("profile_id") or (cfg.get("_profile_id") if isinstance(cfg, dict) else None)
        else:
            cfg = entry
            pid = entry.get("_profile_id")
        cfg = normalize_config(cfg)
        pid = valid_profile_id(pid)
        cfg["_profile_id"] = pid
        cfg["_session_name"] = name
        result[name] = {
            "profile_id": pid,
            "config": cfg,
            "created_at": entry.get("created_at", datetime.now().isoformat(timespec="seconds")),
            "updated_at": entry.get("updated_at", datetime.now().isoformat(timespec="seconds")),
        }
    if result != raw:
        write_sessions(result)
    return result


def auto_save_session(config: dict) -> tuple[str, Path]:
    sessions = migrate_sessions()
    cfg = normalize_config(config)
    pid = valid_profile_id(cfg.get("_profile_id"))
    name = cfg.get("_session_name")
    if not name:
        base = "Sessao " + datetime.now().strftime("%d-%m-%Y %H-%M-%S")
        name = base
        suffix = 2
        while name in sessions:
            name = f"{base} ({suffix})"
            suffix += 1
    cfg["_profile_id"] = pid
    cfg["_session_name"] = name
    directory = profile_path(pid)
    previous = sessions.get(name, {})
    sessions[name] = {
        "profile_id": pid,
        "config": cfg,
        "created_at": previous.get("created_at", datetime.now().isoformat(timespec="seconds")),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    write_sessions(sessions)
    return name, directory


def update_session(config: dict) -> None:
    name = config.get("_session_name")
    if not name:
        return
    sessions = migrate_sessions()
    if name not in sessions:
        return
    cfg = normalize_config(config)
    cfg["_profile_id"] = sessions[name]["profile_id"]
    cfg["_session_name"] = name
    sessions[name]["config"] = cfg
    sessions[name]["updated_at"] = datetime.now().isoformat(timespec="seconds")
    write_sessions(sessions)


# ============================================================
# FLASK: USADO SOMENTE NA CRIACAO/INICIALIZACAO DE NOVA SESSAO
# ============================================================
@app.get("/")
def index():
    return render_template("index.html")


@app.get("/qr.png")
def qr_image():
    if monitor is None or not monitor.image_path.exists():
        return ("QR ainda nao foi capturado. A deteccao continua tentando.", 503)
    response = send_file(monitor.image_path, mimetype="image/png", max_age=0)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return response


@app.get("/api/status")
def status():
    return jsonify(monitor.status() if monitor else {"running": False, "image_available": False})


# ============================================================
# CONFIGURACOES DO MENU
# ============================================================
def choose_port(config: dict) -> None:
    clear_screen()
    print_banner()
    print(f"Porta atual: {config['port']}")
    value = input("Nova porta (1-65535, ENTER para manter): ").strip()
    if value:
        try:
            port = int(value)
            if not 1 <= port <= 65535:
                raise ValueError
            config["port"] = port
            print(f"\n[+] Porta definida para {port}.")
        except ValueError:
            print("\n[!] Porta invalida.")
    pause()


def choose_exposure(config: dict) -> None:
    options = [
        {"label": "Local"},
        {"label": "Rede local"},
        {"label": "Cloudflare"},
    ]
    choice = select_menu("MODO DE PUBLICACAO", options)
    if choice is not None:
        config["exposure"] = ["local", "lan", "cloudflare"][choice]


def show_config(config: dict) -> None:
    clear_screen()
    print_banner()
    print("CONFIGURACAO ATUAL")
    print("─" * 59)
    print(f"  URL de origem : {config['source_url']}")
    print(f"  Seletor       : {config['selector']}")
    print(f"  Intervalo     : {config['interval']}s")
    print(f"  Chromium      : {'headless' if config['headless'] else 'visivel'}")
    print(f"  Porta         : {config['port']}")
    print(f"  Publicacao    : {config['exposure']}")
    pause()


def manage_sessions() -> None:
    while True:
        sessions = migrate_sessions()
        names = list(sessions)
        items = [{"label": "Voltar", "action": "back"}, {"label": "Excluir sessao", "action": "delete"}]
        choice = select_menu("GERENCIAR SESSOES", items)
        if choice is None or items[choice]["action"] == "back":
            return
        if items[choice]["action"] == "delete":
            if not names:
                clear_screen()
                print("Nenhuma sessao salva.")
                pause()
                continue
            delete_items = [{"label": n} for n in names] + [{"label": "Cancelar"}]
            selected = select_menu("ESCOLHA A SESSAO PARA EXCLUIR", delete_items)
            if selected is None or selected >= len(names):
                continue
            name = names[selected]
            confirm = input(f"Excluir '{name}' e o perfil local? (s/N): ").strip().lower()
            if confirm == "s":
                entry = sessions.pop(name)
                folder = (SESSION_PROFILES_DIR / valid_profile_id(entry["profile_id"])).resolve()
                if SESSION_PROFILES_DIR.resolve() in folder.parents:
                    shutil.rmtree(folder, ignore_errors=True)
                write_sessions(sessions)
                print("[+] Sessao excluida.")
                pause()


# ============================================================
# CLOUDFLARE
# ============================================================
def cloudflare_tunnel(port: int):
    executable = shutil.which("cloudflared")
    if not executable:
        raise RuntimeError("cloudflared nao encontrado. Instale o Cloudflare Tunnel.")
    process = subprocess.Popen(
        [executable, "tunnel", "--no-autoupdate", "--url", f"http://127.0.0.1:{port}"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
    )
    lines: queue.Queue[str] = queue.Queue()

    def reader():
        if process.stdout:
            for line in process.stdout:
                lines.put(line)

    threading.Thread(target=reader, daemon=True).start()
    pattern = re.compile(r"https://[a-zA-Z0-9.-]+\.trycloudflare\.com")
    deadline = time.monotonic() + 25
    while time.monotonic() < deadline and process.poll() is None:
        try:
            match = pattern.search(lines.get(timeout=0.25))
        except queue.Empty:
            continue
        if match:
            return process, match.group(0)
    process.terminate()
    raise RuntimeError("Nao foi possivel obter a URL do Cloudflare Tunnel.")


# ============================================================
# EXECUCAO DE SESSAO
# ============================================================
def launch(config: dict, *, first_initialization: bool) -> None:
    global monitor, monitor_thread, active_session_name

    cfg = normalize_config(config)
    if not cfg["source_url"] or "seu-dominio.com" in cfg["source_url"]:
        clear_screen()
        print_banner()
        print("[!] Configure DEFAULT_SOURCE_URL no inicio de app.py.")
        pause()
        return

    # A primeira inicializacao cria e registra a sessao automaticamente.
    # Uma sessao existente preserva seu profile_id e nao cria outra.
    try:
        name, profile_dir = auto_save_session(cfg)
        cfg["_session_name"] = name
        cfg["_profile_id"] = profile_dir.name
        active_session_name = name
    except Exception as exc:
        clear_screen()
        print_banner()
        print(f"[!] Nao foi possivel preparar a sessao: {exc}")
        pause()
        return

    monitor = QRMonitor(
        url=cfg["source_url"],
        selector=cfg["selector"],
        interval=cfg["interval"],
        headless=cfg["headless"],
        profile_dir=profile_dir,
    )
    monitor_thread = threading.Thread(target=monitor.run, daemon=True, name="qr-browser-monitor")

    tunnel = None
    server = None
    server_thread = None
    dashboard_url = None

    try:
        clear_screen()
        print_banner()
        print(f"  Sessao: {name}")
        spinner("Abrindo sessão...")
        monitor_thread.start()

        # Sessao existente: abre somente o navegador, sem Flask e sem painel.
        if first_initialization:
            host = "0.0.0.0" if cfg["exposure"] == "lan" else "127.0.0.1"
            local_url = f"http://127.0.0.1:{cfg['port']}"
            dashboard_url = local_url

            if cfg["exposure"] == "cloudflare":
                tunnel, dashboard_url = cloudflare_tunnel(cfg["port"])

            # make_server evita o banner "Serving Flask app" e permite
            # controlar o ciclo de vida do servidor explicitamente.
            server = make_server(host, cfg["port"], app, threaded=True)
            server_thread = threading.Thread(target=server.serve_forever, daemon=True, name="flask-dashboard")
            server_thread.start()

            print(f"\033[94m\n  🔗 Link: {dashboard_url}\033[0m")
            print("\033[92m  ✔ Compartilhe o link com o destinatário, aguarde a leitura do QR Code e, em seguida, estabeleça a conexão da sessão.\033[0m")
            if OPEN_DASHBOARD_ON_NEW_SESSION:
                webbrowser.open(dashboard_url)
            print("\033[93m  Pressione CTRL+C para voltar ao menu.\n\033[0m")
        else:
            print("\033[92m\n  ✔ Sessao aberta\033[0m")
            print("\033[93m  Pressione CTRL+C para voltar ao menu.\n\033[0m")

        # Mantem a aplicacao viva enquanto o monitor/navegador estiver ativo.
        while monitor_thread.is_alive():
            monitor_thread.join(timeout=0.4)

    except KeyboardInterrupt:
        pass
    except OSError as exc:
        print(f"\n[!] Erro ao iniciar servico: {exc}")
        time.sleep(1)
    except Exception as exc:
        print(f"\n[!] Erro ao abrir sessao: {exc}")
        time.sleep(1)
    finally:
        if monitor:
            monitor.stop()
        if monitor_thread and monitor_thread.is_alive():
            monitor_thread.join(timeout=8)
        if server:
            try:
                server.shutdown()
                server.server_close()
            except Exception:
                pass
        if server_thread and server_thread.is_alive():
            server_thread.join(timeout=2)
        if tunnel and tunnel.poll() is None:
            tunnel.terminate()
            try:
                tunnel.wait(timeout=4)
            except subprocess.TimeoutExpired:
                tunnel.kill()
        try:
            update_session(cfg)
        except Exception:
            pass
        monitor = None
        monitor_thread = None
        active_session_name = None
        clear_screen()


# ============================================================
# MENU PRINCIPAL: SESSOES ABREM DIRETAMENTE COM ENTER
# ============================================================
def main() -> None:
    config = current_config()
    while True:
        sessions = migrate_sessions()
        names = list(sessions)

        items = [{"label": "+ Nova sessao / Inicializar ferramenta", "action": "new"}]
        for name in names:
            items.append({"label": name, "action": "session", "name": name})
        items.append({"separator": True})
        items.extend([
            {"label": "Configuracoes", "action": "settings"},
            {"label": "Gerenciar sessoes", "action": "manage"},
            {"label": "Sobre o projeto", "action": "about"},
            {"label": "Sair", "action": "exit"},
        ])

        selected = select_menu("MENU PRINCIPAL — SESSOES", items)
        if selected is None:
            continue
        item = items[selected]
        action = item.get("action")

        if action == "new":
            new_config = config.copy()
            new_config["_profile_id"] = None
            new_config["_session_name"] = None
            launch(new_config, first_initialization=True)
        elif action == "session":
            latest = migrate_sessions()
            name = item["name"]
            if name not in latest:
                continue
            saved = latest[name]
            restored = normalize_config(saved["config"])
            restored["_profile_id"] = saved["profile_id"]
            restored["_session_name"] = name
            launch(restored, first_initialization=False)
        elif action == "settings":
            settings = [
                {"label": "Alterar porta", "action": "port"},
                {"label": "Modo do servidor", "action": "exposure"},
                {"label": "Ver configuracoes", "action": "view"},
                {"label": "Voltar", "action": "back"},
            ]
            choice = select_menu("CONFIGURACOES", settings)
            if choice is not None:
                if settings[choice]["action"] == "port":
                    choose_port(config)
                elif settings[choice]["action"] == "exposure":
                    choose_exposure(config)
                elif settings[choice]["action"] == "view":
                    show_config(config)
        elif action == "manage":
            manage_sessions()
        elif action == "about":
            clear_screen()
            print_banner()
            print(f"{APP_NAME} {APP_VERSION}")
            print(f"Autor: {APP_AUTHOR}")
            print(f"GitHub: {GITHUB_URL}")
            pause()
        elif action == "exit":
            clear_screen()
            print("Encerrando WhatsCloner Professional...")
            return


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        clear_screen()
        print("ncerrando WhatsCloner Professional...")
        sys.exit(0)
