"""Compatibility test: nginx:1.25-bookworm (original) vs custom-nginx (ours)."""
import http.client
import socket
import subprocess
import time
import pytest
import os

ORIG_IMAGE = "nginx:1.25-bookworm"
MINE_IMAGE = "custom-nginx:latest"
ORIG_PORT = 8081
MINE_PORT = 8082
CUSTOM_CONF = os.path.join(os.path.dirname(os.path.abspath(__file__)), "custom.conf")

# These headers change between builds or requests, so they say nothing about behavior.
IGNORED_HEADERS = {"date", "last-modified", "etag"}


def start(image, name, port, conf=None):
    """Run a container in the background and publish its port 80 on `port`.
    If `conf` is given, mount it as the default server config."""
    cmd = ["docker", "run", "-d", "--rm", "--name", name, "-p", f"{port}:80"]
    if conf:
        cmd += ["-v", f"{conf}:/etc/nginx/conf.d/default.conf:ro"]
    subprocess.run(cmd + [image], check=True, capture_output=True)

def stop(*names):
    """Stop containers. --rm in start() removes them afterwards."""
    subprocess.run(["docker", "stop", *names], capture_output=True)


def request(port, method, path, body=None):
    """Send one HTTP request. Return (status, headers, body)."""
    conn = http.client.HTTPConnection("localhost", port, timeout=10)
    try:
        conn.request(method, path, body=body)
        resp = conn.getresponse()
        headers = {k.lower(): v for k, v in resp.getheaders()
                   if k.lower() not in IGNORED_HEADERS}
        return resp.status, headers, resp.read()
    finally:
        conn.close()


def wait_ready(port, timeout=15, path="/"):
    """Poll until nginx answers an HTTP request, or fail after `timeout` seconds."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            request(port, "GET", path)
            return
        except (OSError, http.client.HTTPException):
            time.sleep(0.3)
    raise RuntimeError(f"nginx on port {port} did not become ready")


@pytest.fixture(scope="module")
def servers():
    """Start both containers once for the whole file, stop them at the end."""
    stop("t-orig", "t-mine")  # clean leftovers from an earlier crashed run
    start(ORIG_IMAGE, "t-orig", ORIG_PORT)
    start(MINE_IMAGE, "t-mine", MINE_PORT)
    try:
        wait_ready(ORIG_PORT)
        wait_ready(MINE_PORT)
        yield
    finally:
        stop("t-orig", "t-mine")

@pytest.fixture(scope="module")
def custom_servers():
    """Same as `servers`, but both containers use test/custom.conf."""
    stop("t-orig-c", "t-mine-c")
    start(ORIG_IMAGE, "t-orig-c", 8083, CUSTOM_CONF)
    start(MINE_IMAGE, "t-mine-c", 8084, CUSTOM_CONF)
    try:
        wait_ready(8083, path="/hello")
        wait_ready(8084, path="/hello")
        yield
    finally:
        stop("t-orig-c", "t-mine-c")

def assert_same(method, path, body=None, ports=(ORIG_PORT, MINE_PORT)):
    """Send the same request to both containers and require identical answers."""
    orig = request(ports[0], method, path, body)
    mine = request(ports[1], method, path, body)
    assert orig == mine, f"{method} {path} differs:\noriginal: {orig}\nmine:     {mine}"

def raw(port, data):
    """Send raw bytes over a TCP socket and return everything the server answers."""
    with socket.create_connection(("localhost", port), timeout=10) as s:
        s.sendall(data)
        chunks = []
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            chunks.append(chunk)
    return b"".join(chunks)


def test_root(servers):
    assert_same("GET", "/")


def test_not_found(servers):
    assert_same("GET", "/no-such-page")


def test_head(servers):
    assert_same("HEAD", "/")


CUSTOM_PORTS = (8083, 8084)


def test_custom_hello(custom_servers):
    assert_same("GET", "/hello", ports=CUSTOM_PORTS)


def test_custom_redirect(custom_servers):
    assert_same("GET", "/old", ports=CUSTOM_PORTS)


def test_post_small(custom_servers):
    assert_same("POST", "/hello", body=b"x" * 100, ports=CUSTOM_PORTS)


def test_post_too_large(custom_servers):
    assert_same("POST", "/hello", body=b"x" * 5000, ports=CUSTOM_PORTS)


def test_malformed_request(servers):
    data = b"THIS IS NOT HTTP\r\n\r\n"
    orig = raw(ORIG_PORT, data)
    mine = raw(MINE_PORT, data)
    assert orig.split(b"\r\n\r\n")[0].split(b"\r\n")[0] == mine.split(b"\r\n\r\n")[0].split(b"\r\n")[0]