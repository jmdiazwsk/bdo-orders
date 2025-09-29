# tests/integration/test_end_to_end.py
"""
End-to-end integration test for the BDO Orders Platform.

What this test does:
1) Discovers actual container names created by Docker Compose (db, kafka, consumer, api, kcat).
2) Prints system status (useful when debugging CI/locals).
3) Publishes a valid JSON message to Kafka using kcat (via docker exec with STDIN to avoid quoting issues).
4) Polls the public API until the order appears, then validates fields.
5) Optionally checks the /metrics endpoint for a basic sanity check.
6) On failure, prints consumer logs, DB info, and recent Kafka messages to help diagnose.

Notes:
- We intentionally avoid hard-coding container names; instead we derive them from labels and common patterns.
- DB check attempts to read DATABASE_URL from the API container; if not found, it falls back to a safe default.
- This test uses asserts (pytest-style). It does NOT return booleans from test functions.
"""

import json
import os
import subprocess
import time
from typing import Dict, Optional

import docker
import requests

API_URL = os.getenv("API_URL", "http://localhost:8000")


# ---------- Container discovery & helpers ----------

def find_container_by_service(service_name: str) -> Optional[str]:
    """
    Find a running container name by Docker Compose service name.
    We match against common naming patterns and the compose service label.
    """
    client = docker.from_env()
    containers = client.containers.list()

    # Typical naming patterns created by docker-compose
    possible_patterns = [
        f"{service_name}",                          # direct name
        f"bdo-{service_name}",                      # prefixed
        f"infra_{service_name}_1",                  # compose v1 style
        f"infra-{service_name}-1",                  # compose v2 style
        f"bdo-orders-platform_{service_name}_1",    # full project name (v1)
        f"bdo-orders-platform-{service_name}-1",    # full project name (v2)
    ]

    for container in containers:
        container_name = container.name
        labels = container.labels or {}
        compose_service = labels.get("com.docker.compose.service", "")

        if (
            container_name in possible_patterns
            or compose_service == service_name
            or service_name in container_name.lower()
        ):
            return container_name

    return None


def get_container_names() -> Dict[str, Optional[str]]:
    """
    Discover actual container names for the services we need.
    Returns a dict like: {'db': 'infra-db-1', 'kafka': 'infra-kafka-1', ...}
    """
    services = ["db", "kafka", "consumer", "api", "kcat"]
    container_map: Dict[str, Optional[str]] = {}

    print("=== Finding Container Names ===")
    for service in services:
        container_name = find_container_by_service(service)
        container_map[service] = container_name
        print(f"{service}: {container_name or 'NOT FOUND'}")

    return container_map


def print_system_status(containers: Dict[str, Optional[str]]) -> None:
    """
    Print the running status of each required container.
    """
    print("=== System Status ===")
    client = docker.from_env()

    for service, container_name in containers.items():
        if not container_name:
            print(f"{service}: NOT FOUND")
            continue

        try:
            container = client.containers.get(container_name)
            status = container.status
            print(f"{service} ({container_name}): {status}")
            if status != "running":
                print(f"  ⚠️  WARNING: {service} is not running!")
        except Exception as e:
            print(f"{service}: ERROR - {e}")
    print()


def print_consumer_logs(containers: Dict[str, Optional[str]], tail: int = 20) -> None:
    """
    Print the last N lines from the consumer container logs.
    """
    consumer_container = containers.get("consumer")
    if not consumer_container:
        print("❌ Consumer container not found - cannot check logs")
        return

    print(f"=== Consumer Logs ({consumer_container}) ===")
    cmd = f"docker logs --tail {tail} {consumer_container}"
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
    except Exception as e:
        print(f"Error getting logs: {e}")
    print()


# ---------- Database check (best-effort, non-fatal) ----------

def _parse_database_url(url: str):
    """
    Parse a postgres URL like postgresql://user:pass@host:port/db and return a dict.
    """
    from urllib.parse import urlparse

    if not url:
        return None

    p = urlparse(url)
    user = p.username or "postgres"
    password = p.password or ""
    host = p.hostname or "localhost"
    port = p.port or 5432
    db = (p.path or "/postgres").lstrip("/")
    return {"user": user, "password": password, "host": host, "port": port, "db": db}


def best_effort_print_db_info(containers: Dict[str, Optional[str]]) -> None:
    """
    Try to read DATABASE_URL from the API container and run a harmless query inside the DB container.
    This is for diagnostics only; the E2E assertions do not depend on it.
    """
    db_container = containers.get("db")
    api_container = containers.get("api")
    if not db_container:
        print("❌ Postgres container not found")
        return

    print(f"=== Database Check ({db_container}) ===")

    db_conf = None
    try:
        client = docker.from_env()
        if api_container:
            api = client.containers.get(api_container)
            # Try to read the env var from inside the container
            exec_res = api.exec_run("printenv DATABASE_URL")
            output = getattr(exec_res, "output", None)
            if output is None and isinstance(exec_res, tuple) and len(exec_res) == 2:
                # Some docker-py versions return (exit_code, output)
                output = exec_res[1]
            db_url = output.decode().strip() if output else ""
            if db_url:
                db_conf = _parse_database_url(db_url)
    except Exception as e:
        print(f"Warning: could not read DATABASE_URL from API: {e}")

    # Fallback if DATABASE_URL not found
    if not db_conf:
        db_conf = {"user": "postgres", "password": "", "host": "localhost", "port": 5432, "db": "postgres"}

    # Run a simple count across information_schema (safe on any DB)
    psql_user = db_conf["user"]
    psql_db = db_conf["db"]
    cmd = (
        f'docker exec {db_container} '
        f'psql -U {psql_user} -d {psql_db} -c "SELECT COUNT(*) FROM information_schema.tables;"'
    )
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=20)
        if result.stdout:
            print(result.stdout.strip())
        if result.stderr:
            print("STDERR:", result.stderr.strip())
    except Exception as e:
        print(f"Database check error: {e}")
    print()


# ---------- Kafka helpers ----------

def produce_with_kcat(msg_json: str, kcat_container: Optional[str]) -> None:
    """
    Produce a JSON message to Kafka using kcat inside the kcat container.

    IMPORTANT: We pass the JSON via STDIN (no printf/quoting) to avoid shell escaping issues
    that often turn JSON into invalid pseudo-JSON like {order_id: x, ...}.
    """
    if not kcat_container:
        raise RuntimeError("kcat container not found")

    cmd = f'docker exec -i {kcat_container} sh -lc "kcat -b kafka:29092 -t orders -P"'
    proc = subprocess.run(cmd, input=msg_json.encode("utf-8"), shell=True)
    if proc.returncode != 0:
        raise RuntimeError(f"kcat exited with code {proc.returncode}")



def test_e2e_order_flow():
    """
    E2E: Publish an order to Kafka -> consumer persists it -> API returns it -> metrics respond.
    """
    print("=== BDO Orders Platform - E2E Test ===")

    # 1) Discover containers and print status
    containers = get_container_names()
    print_system_status(containers)

    # 2) Ensure critical services are present
    for svc in ["kafka", "consumer", "db", "api", "kcat"]:
        assert containers.get(svc), f"Missing container for service: {svc}"

    # 3) (Optional) Pre-run diagnostics
    print_consumer_logs(containers, tail=20)
    best_effort_print_db_info(containers)

    # 4) Publish a well-formed JSON message to Kafka
    test_order_id = f"e2e-{int(time.time())}"
    payload = {
        "order_id": test_order_id,
        "user_id": "e2e-user-1",
        "amount": 125.0,
        "country": "ES",
        "created_at": "2025-09-28T13:00:00Z",
    }
    print("=== Testing Message Flow ===")
    print(f"Test order ID: {test_order_id}")

    produce_with_kcat(json.dumps(payload), containers["kcat"])
    print("✅ Message published to Kafka")

    # 5) Poll the API until the order appears (max ~10s)
    deadline_s = 10.0
    start = time.time()
    found = False
    last_error = None

    while time.time() - start < deadline_s:
        try:
            r = requests.get(f"{API_URL}/orders/{test_order_id}", timeout=2)
            if r.status_code == 200:
                data = r.json()
                assert data["order_id"] == test_order_id
                assert data["amount"] == payload["amount"]
                found = True
                print(f"✅ Order found via API after {time.time() - start:.1f}s!")
                break
        except Exception as e:
            last_error = e
        time.sleep(0.5)

    if not found:
        # Print diagnostics and fail
        print("❌ Order not found within 10 seconds")
        print_consumer_logs(containers, tail=100)
        best_effort_print_db_info(containers)

        # Show recent Kafka messages for the topic
        kcat_container = containers["kcat"]
        print("=== Checking Kafka Messages (last 5) ===")
        try:
            cmd = f"docker exec {kcat_container} kcat -b kafka:29092 -t orders -C -o -5 -e"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=8)
            out = (result.stdout or "").strip()
            print(out if out else "(no recent messages)")
        except Exception as e:
            print(f"Error checking Kafka messages: {e}")

        if last_error:
            raise AssertionError(f"Order not found and last error was: {last_error}")
        raise AssertionError("Order not found in API within timeout")

    # 6) Basic metrics check (non-blocking if fails)
    try:
        r2 = requests.get(f"{API_URL}/metrics?window=1h", timeout=3)
        assert r2.status_code == 200
        print("✅ Metrics endpoint working")
    except Exception as e:
        # We don't fail E2E due to a flaky metrics endpoint; print and continue
        print(f"⚠️ Metrics endpoint issue: {e}")
