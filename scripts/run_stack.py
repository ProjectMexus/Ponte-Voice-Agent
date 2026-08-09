"""Start Ponte's mock backend, middleware, MCP child, and frontend together."""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = PROJECT_ROOT / "database"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from middleware.config import load_dotenv


@dataclass(frozen=True)
class StackCommands:
    backend: list[str]
    middleware: list[str]
    frontend: list[str]


def build_commands(
    python_executable: str,
    *,
    backend_port: int,
    middleware_port: int,
    frontend_port: int,
    data_dir: str | Path,
    medical_data_profile: str = "legacy",
) -> StackCommands:
    return StackCommands(
        backend=[
            python_executable,
            "-m",
            "mock_backends.server",
            "--host",
            "127.0.0.1",
            "--port",
            str(backend_port),
            "--data-dir",
            str(data_dir),
        ] + (["--medical-data-profile", medical_data_profile] if medical_data_profile != "legacy" else []),
        middleware=[
            python_executable,
            "-m",
            "middleware.server",
            "--host",
            "127.0.0.1",
            "--port",
            str(middleware_port),
        ],
        frontend=[
            python_executable,
            "-m",
            "frontend.server",
            "--host",
            "127.0.0.1",
            "--port",
            str(frontend_port),
        ],
    )


def middleware_environment(
    backend_url: str,
    *,
    base_environment: dict[str, str] | None = None,
) -> dict[str, str]:
    environment = dict(base_environment or os.environ)
    environment["PONTE_BACKEND_URL"] = backend_url
    return environment


def frontend_url(frontend_port: int, middleware_port: int) -> str:
    return f"http://127.0.0.1:{frontend_port}/?middleware=http://127.0.0.1:{middleware_port}"


def wait_for_url(url: str, *, timeout: float = 15.0, poll_interval: float = 0.1) -> int:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    opener = build_opener(ProxyHandler({}))
    while time.monotonic() < deadline:
        try:
            request = Request(url, method="GET")
            with opener.open(request, timeout=min(1.0, max(0.1, deadline - time.monotonic()))) as response:
                return int(response.status)
        except (HTTPError, URLError, OSError, TimeoutError) as error:
            last_error = error
            time.sleep(poll_interval)
    raise RuntimeError(f"Timed out waiting for {url}: {last_error}")


def stop_process(process: subprocess.Popen[str], *, timeout: float = 5.0) -> None:
    if process.poll() is not None:
        return
    try:
        process.send_signal(signal.SIGINT)
    except OSError:
        process.terminate()
    try:
        process.wait(timeout=timeout)
        return
    except subprocess.TimeoutExpired:
        pass
    process.terminate()
    try:
        process.wait(timeout=1.0)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=1.0)


def run_stack(
    *,
    backend_port: int = 8080,
    middleware_port: int = 8090,
    frontend_port: int = 5173,
    data_dir: str | Path | None = None,
    demo_agent_mode: str | None = None,
    medical_data_profile: str | None = None,
) -> None:
    load_dotenv()
    demo_mode = demo_agent_mode if demo_agent_mode is not None else os.environ.get("PONTE_DEMO_AGENT_MODE", "off")
    if demo_mode not in {"off", "scripted", "real"}:
        raise ValueError("demo agent mode must be off, scripted, or real")
    profile = medical_data_profile if medical_data_profile is not None else os.environ.get("PONTE_MEDICAL_DATA_PROFILE", "legacy")
    if profile not in {"legacy", "live-demo-v2"}:
        raise ValueError("medical data profile must be legacy or live-demo-v2")
    default_data = PROJECT_ROOT / ".demo-data-cardiology" if demo_mode != "off" else DEFAULT_DATA_DIR
    if profile == "live-demo-v2":
        default_data = PROJECT_ROOT / ".demo-data-medical-v2"
    data_path = default_data if data_dir is None else Path(data_dir).resolve()
    data_path.mkdir(parents=True, exist_ok=True)

    commands = build_commands(
        sys.executable,
        backend_port=backend_port,
        middleware_port=middleware_port,
        frontend_port=frontend_port,
        data_dir=data_path,
        medical_data_profile=profile,
    )
    backend_url = f"http://127.0.0.1:{backend_port}"
    middleware_url = f"http://127.0.0.1:{middleware_port}"
    processes: list[tuple[str, subprocess.Popen[str]]] = []

    def start(name: str, command: list[str], environment: dict[str, str] | None = None):
        process = subprocess.Popen(
            command,
            cwd=str(PROJECT_ROOT),
            env=environment,
            text=True,
        )
        processes.append((name, process))
        return process

    try:
        backend_env = dict(os.environ)
        # Explicit CLI legacy must also override an inherited v2 environment.
        backend_env["PONTE_MEDICAL_DATA_PROFILE"] = profile
        start("backend", commands.backend, backend_env)
        wait_for_url(f"{backend_url}/mock/medical/v1/departments")

        middleware_env = middleware_environment(backend_url)
        middleware_env["PONTE_DEMO_AGENT_MODE"] = demo_mode
        middleware_env["PONTE_FRONTEND_ORIGINS"] = f"http://127.0.0.1:{frontend_port},http://localhost:{frontend_port}"
        start("middleware", commands.middleware, middleware_env)
        wait_for_url(f"{middleware_url}/api/health")

        start("frontend", commands.frontend)
        wait_for_url(f"http://127.0.0.1:{frontend_port}/")

        print("Ponte stack is ready.")
        print(f"Frontend: {frontend_url(frontend_port, middleware_port)}")
        print(f"Middleware: {middleware_url}")
        print(f"Backend: {backend_url}")
        print(f"Demo agent: {demo_mode}; data: {data_path}")
        print(f"Medical data: {profile}; synthetic shared patient sandbox.")
        if demo_mode != "off":
            print("Cardiology story: 心臟科下週二下午 → 改為下午3點後 → press 確認掛號")
            if demo_mode == "scripted":
                print("SCRIPTED model decisions; real local HTTP → MCP → JSON mock backend.")
        else:
            print("Browser smoke input: 我想查詢醫療預約")
        while True:
            for name, process in processes:
                return_code = process.poll()
                if return_code is not None:
                    raise RuntimeError(f"{name} exited with status {return_code}")
            time.sleep(0.25)
    except KeyboardInterrupt:
        print("Stopping Ponte stack.")
    finally:
        for _, process in reversed(processes):
            stop_process(process)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the complete local Ponte demo stack.")
    parser.add_argument("--backend-port", type=int, default=8080)
    parser.add_argument("--middleware-port", type=int, default=8090)
    parser.add_argument("--frontend-port", type=int, default=5173)
    parser.add_argument("--data-dir", default=None)
    parser.add_argument("--demo-agent", choices=("off", "scripted", "real"), default=None)
    parser.add_argument("--medical-data-profile", choices=("legacy", "live-demo-v2"), default=None)
    args = parser.parse_args()
    run_stack(
        backend_port=args.backend_port,
        middleware_port=args.middleware_port,
        frontend_port=args.frontend_port,
        data_dir=args.data_dir,
        demo_agent_mode=args.demo_agent,
        medical_data_profile=args.medical_data_profile,
    )


if __name__ == "__main__":
    main()
