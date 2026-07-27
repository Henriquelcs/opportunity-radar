from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import signal
import subprocess
import sys
import time
import traceback
import urllib.error
import urllib.request
from pathlib import Path
from typing import Iterable


PROJECT_DIR = Path(__file__).resolve().parents[1]


def ensure_project_import_path(project_dir: Path = PROJECT_DIR) -> None:
    project_path = str(project_dir.resolve())
    if project_path not in sys.path:
        sys.path.insert(0, project_path)


def configure_realtime_output() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(line_buffering=True, write_through=True)


ensure_project_import_path()
configure_realtime_output()

DEFAULT_DATABASE = PROJECT_DIR / "data" / "opportunity_radar_operational.db"
DEFAULT_CACHE_DATABASE = PROJECT_DIR / "data" / "source_cache.db"
DEFAULT_QUERIES = (
    "repetitive data entry",
    "spreadsheet automation",
    "customer support automation",
)

CLOUDFLARED_VERSION = "2026.7.3"
CLOUDFLARED_SHA256 = (
    "9d71c677db00134c1bd4144b7783486b654ad281b1ea62b4972098d19f770f17"
)
CLOUDFLARED_URL = (
    "https://github.com/cloudflare/cloudflared/releases/download/"
    f"{CLOUDFLARED_VERSION}/cloudflared-linux-amd64"
)

PACKAGE_SPECS = {
    "requests": "requests>=2.31.0",
    "pandas": "pandas>=2.0.0",
    "pytest": "pytest>=8.0.0",
    "streamlit": "streamlit>=1.35.0",
    "plotly": "plotly>=5.20.0",
    "altair": "altair>=5.0.0",
}


def runtime_dir() -> Path:
    configured = os.getenv("OPPORTUNITY_RADAR_RUNTIME_DIR", "").strip()
    if configured:
        path = Path(configured).expanduser().resolve()
    elif Path("/content").exists():
        path = Path("/content/opportunity-radar-runtime")
    else:
        path = PROJECT_DIR.parent / "opportunity-radar-runtime"
    path.mkdir(parents=True, exist_ok=True)
    return path


def print_command(command: Iterable[str]) -> None:
    safe_parts: list[str] = []
    for part in command:
        value = str(part)
        if any(secret_name in value.upper() for secret_name in ("TOKEN=", "API_KEY=")):
            value = "<secret>"
        safe_parts.append(value)
    print("$ " + " ".join(safe_parts), flush=True)


def run_command(
    command: list[str],
    *,
    cwd: Path = PROJECT_DIR,
    env: dict[str, str] | None = None,
) -> None:
    print_command(command)
    subprocess.run(command, cwd=cwd, env=env, check=True)


def extract_public_url(text: str) -> str:
    match = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", text)
    return match.group(0) if match else ""


def build_collection_command(
    query: str,
    database: Path,
    *,
    limit: int,
    minimum_score: float,
    top: int,
    max_attempts: int,
    retry_delay_seconds: int,
    inter_query_delay_seconds: int,
) -> list[str]:
    """Compatibilidade com os testes do Runner V1; não é usado pelo V2."""
    return [
        sys.executable,
        "scripts/run_expanded_query.py",
        "--query",
        query,
        "--database",
        str(database),
        "--limit",
        str(limit),
        "--minimum-score",
        str(minimum_score),
        "--top",
        str(top),
        "--max-attempts",
        str(max_attempts),
        "--retry-delay-seconds",
        str(retry_delay_seconds),
        "--inter-query-delay-seconds",
        str(inter_query_delay_seconds),
    ]


def missing_packages() -> list[str]:
    return [
        spec
        for module_name, spec in PACKAGE_SPECS.items()
        if importlib.util.find_spec(module_name) is None
    ]


def install_missing_dependencies() -> None:
    missing = missing_packages()
    if not missing:
        print("[SETUP] Dependências Python já instaladas.", flush=True)
        return
    print(f"[SETUP] Instalando somente ausentes: {', '.join(missing)}", flush=True)
    run_command([sys.executable, "-m", "pip", "install", *missing])


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_cloudflared(destination: Path) -> None:
    temporary = destination.with_suffix(".download")
    temporary.parent.mkdir(parents=True, exist_ok=True)
    temporary.unlink(missing_ok=True)
    print(
        f"[SETUP] Baixando cloudflared fixado em {CLOUDFLARED_VERSION}.",
        flush=True,
    )
    request = urllib.request.Request(
        CLOUDFLARED_URL,
        headers={"User-Agent": "opportunity-radar"},
    )
    with urllib.request.urlopen(request, timeout=120) as response, temporary.open(
        "wb"
    ) as output:
        total = int(response.headers.get("Content-Length", "0") or 0)
        downloaded = 0
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            output.write(chunk)
            downloaded += len(chunk)
            if total:
                percent = downloaded * 100 / total
                print(
                    f"[SETUP] cloudflared {downloaded}/{total} bytes "
                    f"({percent:.0f}%)",
                    flush=True,
                )
            else:
                print(
                    f"[SETUP] cloudflared {downloaded} bytes",
                    flush=True,
                )
    actual = sha256_file(temporary)
    if actual != CLOUDFLARED_SHA256:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(
            "Checksum inválido do cloudflared: "
            f"esperado={CLOUDFLARED_SHA256} obtido={actual}"
        )
    temporary.chmod(0o755)
    temporary.replace(destination)


def ensure_cloudflared() -> Path:
    binary = runtime_dir() / "bin" / "cloudflared"
    if binary.exists() and sha256_file(binary) == CLOUDFLARED_SHA256:
        print(
            f"[SETUP] cloudflared {CLOUDFLARED_VERSION} já validado.",
            flush=True,
        )
        return binary
    download_cloudflared(binary)
    print(
        f"[SETUP] cloudflared instalado e checksum validado: {binary}",
        flush=True,
    )
    return binary


def setup() -> None:
    print("[SETUP] Iniciando preparação idempotente.", flush=True)
    install_missing_dependencies()
    ensure_cloudflared()
    print("[SETUP] Concluído.", flush=True)


def verify() -> None:
    print("[VERIFY] Compilação.", flush=True)
    run_command(
        [
            sys.executable,
            "-m",
            "compileall",
            "-q",
            "src",
            "scripts",
            "tests",
        ]
    )
    print("[VERIFY] Suíte completa.", flush=True)
    run_command([sys.executable, "-m", "pytest", "-q"])
    print("[VERIFY] Compilação e testes aprovados.", flush=True)


def process_is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except (ProcessLookupError, PermissionError):
        return False
    return True


def process_command(pid: int) -> str:
    path = Path(f"/proc/{pid}/cmdline")
    try:
        return path.read_bytes().replace(b"\x00", b" ").decode(
            "utf-8",
            errors="replace",
        )
    except OSError:
        return ""


def stop_managed_process(pid_file: Path, expected_marker: str) -> None:
    if not pid_file.exists():
        return
    try:
        pid = int(pid_file.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        pid_file.unlink(missing_ok=True)
        return
    if not process_is_alive(pid):
        pid_file.unlink(missing_ok=True)
        return
    command = process_command(pid)
    if expected_marker not in command:
        raise RuntimeError(
            f"PID {pid} não pertence ao processo esperado: {expected_marker}"
        )
    print(f"[PROCESS] Encerrando PID={pid} marcador={expected_marker}", flush=True)
    os.kill(pid, signal.SIGTERM)
    deadline = time.time() + 12
    while time.time() < deadline and process_is_alive(pid):
        time.sleep(0.25)
    if process_is_alive(pid):
        print(f"[PROCESS] SIGKILL PID={pid}", flush=True)
        os.kill(pid, signal.SIGKILL)
    pid_file.unlink(missing_ok=True)


def start_managed_process(
    command: list[str],
    *,
    pid_file: Path,
    log_file: Path,
    expected_marker: str,
    env: dict[str, str] | None = None,
) -> int:
    stop_managed_process(pid_file, expected_marker)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    log_stream = log_file.open("w", encoding="utf-8", buffering=1)
    print_command(command)
    process = subprocess.Popen(
        command,
        cwd=PROJECT_DIR,
        env=env,
        stdout=log_stream,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,
    )
    pid_file.write_text(str(process.pid), encoding="utf-8")
    print(
        f"[PROCESS] iniciado PID={process.pid} log={log_file}",
        flush=True,
    )
    return process.pid


def print_new_log_lines(log_file: Path, offset: int) -> int:
    if not log_file.exists():
        return offset
    with log_file.open("r", encoding="utf-8", errors="replace") as stream:
        stream.seek(offset)
        chunk = stream.read()
        new_offset = stream.tell()
    if chunk:
        print(chunk, end="" if chunk.endswith("\n") else "\n", flush=True)
    return new_offset


def wait_for_http(
    url: str,
    *,
    pid: int,
    log_file: Path,
    timeout_seconds: int,
) -> None:
    deadline = time.time() + timeout_seconds
    offset = 0
    last_error = ""
    while time.time() < deadline:
        offset = print_new_log_lines(log_file, offset)
        if not process_is_alive(pid):
            offset = print_new_log_lines(log_file, offset)
            raise RuntimeError(f"Processo PID={pid} encerrou antes de responder")
        try:
            with urllib.request.urlopen(url, timeout=3) as response:
                if 200 <= response.status < 500:
                    print(
                        f"[DASHBOARD] healthcheck={response.status} url={url}",
                        flush=True,
                    )
                    return
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = str(exc)
        time.sleep(1)
    print_new_log_lines(log_file, offset)
    raise RuntimeError(
        f"Timeout aguardando {url}. Último erro: {last_error}"
    )


def wait_for_tunnel_url(
    *,
    pid: int,
    log_file: Path,
    timeout_seconds: int,
) -> str:
    deadline = time.time() + timeout_seconds
    offset = 0
    while time.time() < deadline:
        offset = print_new_log_lines(log_file, offset)
        content = (
            log_file.read_text(encoding="utf-8", errors="replace")
            if log_file.exists()
            else ""
        )
        url = extract_public_url(content)
        if url:
            return url
        if not process_is_alive(pid):
            print_new_log_lines(log_file, offset)
            raise RuntimeError("Cloudflared encerrou antes de publicar a URL")
        time.sleep(1)
    print_new_log_lines(log_file, offset)
    raise RuntimeError("Timeout aguardando URL trycloudflare")


def collect(
    *,
    database: Path,
    cache_database: Path,
    queries: tuple[str, ...],
    limit_per_source: int,
    minimum_score: float,
) -> dict:
    from src.operations.runner_v2 import OpportunityRadarRunnerV2

    print(
        f"[COLLECT] banco={database} cache={cache_database} "
        f"consultas={len(queries)}",
        flush=True,
    )
    runner = OpportunityRadarRunnerV2(
        database_path=database,
        cache_database_path=cache_database,
    )
    result = runner.run(
        queries=queries,
        limit_per_source=limit_per_source,
        minimum_score=minimum_score,
    )
    payload = result.to_dict()
    print("[COLLECT] " + json.dumps(payload, ensure_ascii=False), flush=True)
    if result.status not in {"SUCCESS", "DEGRADED"}:
        raise RuntimeError(f"Coleta terminou com status={result.status}")
    return payload


def dashboard(
    *,
    database: Path,
    no_tunnel: bool,
    wait_seconds: int,
) -> str:
    if not database.exists():
        raise FileNotFoundError(f"Banco operacional não encontrado: {database}")
    runtime = runtime_dir()
    streamlit_pid = runtime / "streamlit.pid"
    tunnel_pid = runtime / "cloudflared.pid"
    streamlit_log = runtime / "streamlit.log"
    tunnel_log = runtime / "cloudflared.log"
    url_file = runtime / "dashboard_url.txt"

    environment = os.environ.copy()
    environment["OPPORTUNITY_RADAR_DATA_DIR"] = str(database.parent.resolve())
    port = int(os.getenv("OPPORTUNITY_RADAR_PORT", "8501"))

    streamlit_command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        "src/dashboard/app.py",
        "--server.address",
        "0.0.0.0",
        "--server.port",
        str(port),
        "--server.headless",
        "true",
        "--browser.gatherUsageStats",
        "false",
    ]
    streamlit_process = start_managed_process(
        streamlit_command,
        pid_file=streamlit_pid,
        log_file=streamlit_log,
        expected_marker="streamlit",
        env=environment,
    )
    wait_for_http(
        f"http://127.0.0.1:{port}/_stcore/health",
        pid=streamlit_process,
        log_file=streamlit_log,
        timeout_seconds=wait_seconds,
    )

    local_url = f"http://127.0.0.1:{port}"
    if no_tunnel:
        url_file.write_text(local_url, encoding="utf-8")
        print(f"[DASHBOARD] URL local: {local_url}", flush=True)
        return local_url

    cloudflared = ensure_cloudflared()
    tunnel_command = [
        str(cloudflared),
        "tunnel",
        "--url",
        local_url,
        "--no-autoupdate",
    ]
    tunnel_process = start_managed_process(
        tunnel_command,
        pid_file=tunnel_pid,
        log_file=tunnel_log,
        expected_marker="cloudflared",
        env=os.environ.copy(),
    )
    public_url = wait_for_tunnel_url(
        pid=tunnel_process,
        log_file=tunnel_log,
        timeout_seconds=wait_seconds,
    )
    url_file.write_text(public_url, encoding="utf-8")
    print(f"[DASHBOARD] URL pública: {public_url}", flush=True)
    return public_url


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Runner operacional V2 do Opportunity Radar no Colab"
    )
    parser.add_argument(
        "--mode",
        choices=("setup", "verify", "collect", "dashboard", "all"),
        default="all",
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=DEFAULT_DATABASE,
    )
    parser.add_argument(
        "--cache-database",
        type=Path,
        default=DEFAULT_CACHE_DATABASE,
    )
    parser.add_argument(
        "--query",
        action="append",
        dest="queries",
        help="Pode ser repetido. Ausente usa as três consultas oficiais.",
    )
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--minimum-score", type=float, default=35.0)
    parser.add_argument("--no-tunnel", action="store_true")
    parser.add_argument("--dashboard-wait-seconds", type=int, default=90)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    os.chdir(PROJECT_DIR)
    database = args.database.expanduser().resolve()
    cache_database = args.cache_database.expanduser().resolve()
    queries = tuple(args.queries or DEFAULT_QUERIES)

    if args.mode == "setup":
        setup()
    elif args.mode == "verify":
        verify()
    elif args.mode == "collect":
        collect(
            database=database,
            cache_database=cache_database,
            queries=queries,
            limit_per_source=args.limit,
            minimum_score=args.minimum_score,
        )
    elif args.mode == "dashboard":
        setup()
        dashboard(
            database=database,
            no_tunnel=args.no_tunnel,
            wait_seconds=args.dashboard_wait_seconds,
        )
    elif args.mode == "all":
        setup()
        verify()
        collect(
            database=database,
            cache_database=cache_database,
            queries=queries,
            limit_per_source=args.limit,
            minimum_score=args.minimum_score,
        )
        dashboard(
            database=database,
            no_tunnel=args.no_tunnel,
            wait_seconds=args.dashboard_wait_seconds,
        )
    return 0


def cli() -> int:
    try:
        return main()
    except KeyboardInterrupt:
        print("[FATAL] Execução interrompida pelo usuário.", file=sys.stderr, flush=True)
        return 130
    except Exception as exc:
        print(
            f"[FATAL] {type(exc).__name__}: {exc}",
            file=sys.stderr,
            flush=True,
        )
        traceback.print_exc(file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(cli())
