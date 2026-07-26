from __future__ import annotations

import argparse
import os
import re
import shlex
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Sequence

PROJECT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_DIR / "data"
DEFAULT_DATABASE = DATA_DIR / "opportunity_radar_operational.db"
DEFAULT_QUERIES = (
    "repetitive data entry",
    "spreadsheet automation",
    "customer support automation",
)
DASHBOARD_PORT = 8501
STREAMLIT_LOG = Path("/content/opportunity_radar_streamlit.log")
TUNNEL_LOG = Path("/content/opportunity_radar_tunnel.log")
CLOUDFLARED_PATH = Path("/content/cloudflared")
PUBLIC_URL_PATTERN = re.compile(
    r"https://[a-z0-9-]+\.trycloudflare\.com",
    re.IGNORECASE,
)


def run_command(
    command: Sequence[str],
    *,
    check: bool = True,
    env: dict[str, str] | None = None,
    secrets: Sequence[str] = (),
) -> subprocess.CompletedProcess[str]:
    shown = " ".join(shlex.quote(str(part)) for part in command)
    for secret in secrets:
        if secret:
            shown = shown.replace(secret, "<secret>")
    print(f"\n$ {shown}")

    result = subprocess.run(
        [str(part) for part in command],
        cwd=PROJECT_DIR,
        text=True,
        capture_output=True,
        env=env,
    )

    stdout = result.stdout or ""
    stderr = result.stderr or ""
    for secret in secrets:
        if secret:
            stdout = stdout.replace(secret, "<secret>")
            stderr = stderr.replace(secret, "<secret>")

    if stdout.strip():
        print(stdout.rstrip())
    if stderr.strip():
        print(stderr.rstrip())

    if check and result.returncode != 0:
        raise RuntimeError(
            f"Comando falhou com código {result.returncode}: {shown}"
        )
    return result


def read_colab_secret(name: str) -> str:
    current = os.getenv(name, "").strip()
    if current:
        return current

    try:
        from google.colab import userdata

        value = str(userdata.get(name) or "").strip()
        if value:
            os.environ[name] = value
            return value
    except Exception:
        pass

    return ""


def configure_secrets() -> None:
    github_token = read_colab_secret("GITHUB_TOKEN")
    if not github_token:
        github_token = read_colab_secret("GH_TOKEN")
    if github_token:
        os.environ.setdefault("GITHUB_TOKEN", github_token)
        os.environ.setdefault("GH_TOKEN", github_token)

    stackexchange_key = read_colab_secret("STACKEXCHANGE_KEY")
    if stackexchange_key:
        os.environ["STACKEXCHANGE_KEY"] = stackexchange_key


def ensure_repository(skip_update: bool) -> str:
    tracked_status = run_command(
        ["git", "status", "--porcelain", "--untracked-files=no"]
    ).stdout.strip()
    if tracked_status:
        raise RuntimeError(
            "Existem alterações rastreadas não salvas:\n"
            + tracked_status
        )

    if not skip_update:
        run_command(["git", "pull", "--ff-only", "origin", "main"])

    return run_command(
        ["git", "rev-parse", "--short", "HEAD"]
    ).stdout.strip()


def install_dependencies() -> None:
    run_command(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "-q",
            "streamlit>=1.35,<2",
            "pandas>=2,<3",
            "altair>=5,<6",
            "pytest>=8,<9",
        ]
    )


def validate_project(skip_tests: bool) -> None:
    run_command(
        [
            sys.executable,
            "-m",
            "compileall",
            "-q",
            "src",
            "scripts",
            "tests",
            "main.py",
        ]
    )
    if not skip_tests:
        run_command([sys.executable, "-m", "pytest", "-q"])


def build_collection_command(
    query: str,
    database_path: Path,
    *,
    limit: int,
    minimum_score: float,
    top: int,
    max_attempts: int,
    retry_delay_seconds: float,
    inter_query_delay_seconds: float,
) -> list[str]:
    return [
        sys.executable,
        "scripts/run_expanded_query.py",
        "--query",
        query,
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
        "--database",
        str(database_path),
    ]


def collect_queries(
    queries: Sequence[str],
    database_path: Path,
    *,
    fresh: bool,
    limit: int,
    minimum_score: float,
    top: int,
    max_attempts: int,
    retry_delay_seconds: float,
    inter_query_delay_seconds: float,
) -> None:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    if fresh:
        database_path.unlink(missing_ok=True)

    for position, query in enumerate(queries, start=1):
        print("\n" + "=" * 78)
        print(f"COLETA OPERACIONAL {position}/{len(queries)} — {query}")
        print("=" * 78)

        command = build_collection_command(
            query,
            database_path,
            limit=limit,
            minimum_score=minimum_score,
            top=top,
            max_attempts=max_attempts,
            retry_delay_seconds=retry_delay_seconds,
            inter_query_delay_seconds=inter_query_delay_seconds,
        )
        run_command(command)


def port_is_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def stop_existing_services() -> None:
    subprocess.run(
        ["pkill", "-f", "streamlit run src/dashboard/app.py"],
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["pkill", "-f", "cloudflared tunnel"],
        capture_output=True,
        text=True,
    )
    time.sleep(2)


def ensure_cloudflared() -> Path:
    if CLOUDFLARED_PATH.exists():
        return CLOUDFLARED_PATH

    print("⬇️ Instalando Cloudflare Tunnel.")
    urllib.request.urlretrieve(
        "https://github.com/cloudflare/cloudflared/releases/latest/download/"
        "cloudflared-linux-amd64",
        CLOUDFLARED_PATH,
    )
    CLOUDFLARED_PATH.chmod(0o755)
    return CLOUDFLARED_PATH


def wait_for_dashboard(
    process: subprocess.Popen[bytes],
    timeout_seconds: int = 90,
) -> None:
    health_url = (
        f"http://127.0.0.1:{DASHBOARD_PORT}/_stcore/health"
    )

    for _ in range(timeout_seconds):
        if process.poll() is not None:
            log = STREAMLIT_LOG.read_text(
                encoding="utf-8",
                errors="replace",
            )
            raise RuntimeError(
                "Streamlit foi encerrado:\n" + log[-4000:]
            )

        try:
            with urllib.request.urlopen(
                health_url,
                timeout=2,
            ) as response:
                if response.status == 200:
                    return
        except Exception:
            pass

        time.sleep(1)

    log = STREAMLIT_LOG.read_text(
        encoding="utf-8",
        errors="replace",
    )
    raise RuntimeError(
        "Streamlit não respondeu ao health check:\n"
        + log[-4000:]
    )


def extract_public_url(log_text: str) -> str:
    match = PUBLIC_URL_PATTERN.search(log_text)
    return match.group(0) if match else ""


def start_dashboard() -> str:
    stop_existing_services()
    cloudflared_path = ensure_cloudflared()

    with STREAMLIT_LOG.open("w", encoding="utf-8") as log_file:
        streamlit_process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                "src/dashboard/app.py",
                "--server.port",
                str(DASHBOARD_PORT),
                "--server.address",
                "0.0.0.0",
                "--server.headless",
                "true",
                "--browser.gatherUsageStats",
                "false",
            ],
            cwd=PROJECT_DIR,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )

    wait_for_dashboard(streamlit_process)

    with TUNNEL_LOG.open("w", encoding="utf-8") as log_file:
        tunnel_process = subprocess.Popen(
            [
                str(cloudflared_path),
                "tunnel",
                "--url",
                f"http://127.0.0.1:{DASHBOARD_PORT}",
                "--protocol",
                "http2",
                "--no-autoupdate",
            ],
            cwd=PROJECT_DIR,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )

    for _ in range(90):
        if tunnel_process.poll() is not None:
            log = TUNNEL_LOG.read_text(
                encoding="utf-8",
                errors="replace",
            )
            raise RuntimeError(
                "Cloudflare Tunnel foi encerrado:\n"
                + log[-4000:]
            )

        log_text = TUNNEL_LOG.read_text(
            encoding="utf-8",
            errors="replace",
        )
        public_url = extract_public_url(log_text)
        if public_url:
            return public_url
        time.sleep(1)

    log = TUNNEL_LOG.read_text(
        encoding="utf-8",
        errors="replace",
    )
    raise RuntimeError(
        "A URL pública não foi localizada:\n" + log[-4000:]
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Atualiza, testa, coleta as seis fontes e abre a dashboard "
            "do Opportunity Radar."
        )
    )
    parser.add_argument(
        "--query",
        action="append",
        dest="queries",
        help=(
            "Consulta original. Pode ser repetida. "
            "Sem este argumento, usa as três consultas padrão."
        ),
    )
    parser.add_argument(
        "--database",
        default=str(DEFAULT_DATABASE),
    )
    parser.add_argument("--limit", type=int, default=12)
    parser.add_argument("--minimum-score", type=float, default=0)
    parser.add_argument("--top", type=int, default=100)
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument(
        "--retry-delay-seconds",
        type=float,
        default=15,
    )
    parser.add_argument(
        "--inter-query-delay-seconds",
        type=float,
        default=7,
    )
    parser.add_argument("--fresh", action="store_true")
    parser.add_argument("--skip-update", action="store_true")
    parser.add_argument("--skip-tests", action="store_true")
    parser.add_argument("--skip-collection", action="store_true")
    parser.add_argument("--no-dashboard", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    queries = tuple(args.queries or DEFAULT_QUERIES)
    database_path = Path(args.database).expanduser().resolve()

    configure_secrets()
    commit = ensure_repository(args.skip_update)
    install_dependencies()
    validate_project(args.skip_tests)

    if not args.skip_collection:
        collect_queries(
            queries,
            database_path,
            fresh=args.fresh,
            limit=args.limit,
            minimum_score=args.minimum_score,
            top=args.top,
            max_attempts=args.max_attempts,
            retry_delay_seconds=args.retry_delay_seconds,
            inter_query_delay_seconds=args.inter_query_delay_seconds,
        )

    public_url = ""
    if not args.no_dashboard:
        public_url = start_dashboard()

    print("\n" + "=" * 78)
    print("✅ OPPORTUNITY RADAR OPERACIONAL")
    print("=" * 78)
    print(f"Commit: {commit}")
    print(f"Banco: {database_path}")
    print(f"Consultas: {len(queries)}")
    print("Fontes configuradas: 6")
    if public_url:
        print(f"Dashboard: {public_url}")
        print("Mantenha esta sessão do Colab conectada.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
