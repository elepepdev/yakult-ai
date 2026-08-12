import os
import sys
import atexit
import asyncio
import argparse
import signal
import time
import subprocess
from pathlib import Path
import tomli
import uvicorn
from loguru import logger
from src.yakult_mybini.server import WebSocketServer
from src.yakult_mybini.config_manager import Config, read_yaml, validate_config
from src.yakult_mybini.utils.token_tracker import get_tracker

os.environ["HF_HOME"] = str(Path(__file__).parent / "models")
os.environ["MODELSCOPE_CACHE"] = str(Path(__file__).parent / "models")


def find_pids_on_port(port: int) -> list[int]:
    """Return PIDs of processes currently listening on ``port``.

    Uses psutil when available (it can match the listening socket directly),
    otherwise falls back to ``lsof``.  The current process and its ancestors
    are never returned so we cannot kill ourselves.
    """
    pids: set[int] = set()

    # Exclude this process and its parents (never kill ourselves)
    excluded = {os.getpid()}
    ppid = os.getppid()
    while ppid and ppid > 1:
        excluded.add(ppid)
        try:
            with open(f"/proc/{ppid}/stat", "r") as f:
                parts = f.read().split()
            ppid = int(parts[3])
        except (OSError, IndexError, ValueError):
            break

    try:
        import psutil

        for conn in psutil.net_connections(kind="inet"):
            try:
                if conn.status == psutil.CONN_LISTEN and conn.laddr.port == port and conn.pid:
                    pids.add(conn.pid)
            except (AttributeError, OSError):
                continue
    except (ImportError, Exception) as e:
        logger.debug(f"psutil unavailable for port scan: {e}")

    if not pids:
        try:
            out = subprocess.run(
                ["lsof", "-t", f"-iTCP:{port}", "-sTCP:LISTEN"],
                capture_output=True,
                text=True,
                timeout=5,
            ).stdout
            for line in out.splitlines():
                line = line.strip()
                if line.isdigit():
                    pids.add(int(line))
        except (FileNotFoundError, subprocess.SubprocessError) as e:
            logger.debug(f"lsof unavailable for port scan: {e}")

    return sorted(p for p in pids if p not in excluded)


def kill_process_on_port(port: int) -> None:
    """Kill any process bound to ``port`` so we can bind it ourselves.

    Sends SIGTERM first, waits briefly for graceful shutdown, then escalates
    to SIGKILL.  Logs every step so it is always clear what was stopped.
    """
    pids = find_pids_on_port(port)
    if not pids:
        logger.info(f"Port {port} is free.")
        return

    logger.warning(
        f"Port {port} is already in use by PID(s): {', '.join(map(str, pids))}. "
        f"Stopping them so the server can start."
    )

    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
            logger.warning(f"Sent SIGTERM to PID {pid}.")
        except ProcessLookupError:
            logger.debug(f"PID {pid} already gone.")
        except PermissionError:
            logger.error(f"No permission to stop PID {pid}. Port {port} will stay busy.")

    # Wait for graceful exit, escalate to SIGKILL if needed
    for _ in range(10):
        time.sleep(0.5)
        remaining = find_pids_on_port(port)
        if not remaining:
            logger.info(f"Port {port} released.")
            return

    for pid in remaining:
        try:
            os.kill(pid, signal.SIGKILL)
            logger.warning(f"PID {pid} did not exit gracefully - sent SIGKILL.")
        except (ProcessLookupError, PermissionError):
            pass

    time.sleep(0.5)
    if find_pids_on_port(port):
        logger.error(
            f"Could not free port {port}. Check what is holding it and stop it manually."
        )
    else:
        logger.info(f"Port {port} released.")


def get_version() -> str:
    with open("pyproject.toml", "rb") as f:
        pyproject = tomli.load(f)
    return pyproject["project"]["version"]


def init_logger(console_log_level: str = "INFO") -> None:
    logger.remove()
    # Console output
    logger.add(
        sys.stderr,
        level=console_log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | {message}",
        colorize=True,
    )

    # File output
    logger.add(
        "logs/debug_{time:YYYY-MM-DD}.log",
        rotation="10 MB",
        retention="30 days",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message} | {extra}",
        backtrace=True,
        diagnose=True,
    )


def check_frontend_submodule(lang='en'):
    """
    Check if the frontend build is present. If not, warn the user to build it.
    The frontend lives in `deskcom/` (not a submodule) and is served from `deskcom/dist/web`.
    """
    frontend_path = Path(__file__).parent / "deskcom" / "dist" / "web" / "index.html"
    if not frontend_path.exists():
        if lang == "zh":
            logger.warning(
                "未找到前端构建产物，请先构建前端: cd deskcom && npm install && npm run build:web"
            )
        else:
            logger.warning(
                "Frontend build not found. Build it first: cd deskcom && npm install && npm run build:web"
            )


def parse_args():
    parser = argparse.ArgumentParser(description="Yakult My Bini Server")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument(
        "--hf_mirror", action="store_true", help="Use Hugging Face mirror"
    )
    parser.add_argument(
        "--no-kill-port",
        action="store_true",
        help="Do not kill processes already using the configured port. "
        "By default, the server stops whatever is bound to the port and restarts.",
    )
    return parser.parse_args()


@logger.catch
def run(console_log_level: str, kill_port: bool = True):
    init_logger(console_log_level)
    logger.info(f"Yakult My Bini, version v{get_version()}")

    # Check if the frontend submodule is initialized
    check_frontend_submodule()

    atexit.register(WebSocketServer.clean_cache)

    # Load configurations from yaml file
    config: Config = validate_config(read_yaml("conf.yaml"))
    server_config = config.system_config

    # Free the configured port before starting (kill whatever holds it)
    if kill_port:
        kill_process_on_port(server_config.port)
    else:
        logger.info(f"Skipping port check (--no-kill-port). Port {server_config.port}.")

    if server_config.enable_proxy:
        logger.info("Proxy mode enabled - /proxy-ws endpoint will be available")

    # Initialize the WebSocket server (synchronous part)
    server = WebSocketServer(config=config)

    # Perform asynchronous initialization (loading context, etc.)
    logger.info("Initializing server context...")
    try:
        asyncio.run(server.initialize())
        logger.info("Server context initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize server context: {e}")
        sys.exit(1)  # Exit if initialization fails

    # Run the Uvicorn server
    logger.info(f"Starting server on {server_config.host}:{server_config.port}")
    try:
        uvicorn.run(
            app=server.app,
            host=server_config.host,
            port=server_config.port,
            log_level=console_log_level.lower(),
        )
    except KeyboardInterrupt:
        pass
    finally:
        summary = get_tracker().summary()
        logger.info(f"\n{summary}")


if __name__ == "__main__":
    args = parse_args()
    console_log_level = "DEBUG" if args.verbose else "INFO"
    if args.verbose:
        logger.info("Running in verbose mode")
    else:
        logger.info(
            "Running in standard mode. For detailed debug logs, use: uv run run_server.py --verbose"
        )
    if args.hf_mirror:
        os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
    run(console_log_level=console_log_level, kill_port=not args.no_kill_port)
