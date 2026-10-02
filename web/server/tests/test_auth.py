from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from arc_arena.app import create_app
from arc_arena.auth import AuthManager, hash_password, verify_password
from arc_arena.config import Config
from arc_arena.db import init_db


def make_cfg(tmp_path: Path) -> Config:
    backend = tmp_path / "backend"
    (backend / ".venv" / "bin").mkdir(parents=True, exist_ok=True)
    (backend / ".venv" / "bin" / "arc").write_text("#!/bin/sh\n")
    cfg = Config(backend_root=backend, data_dir=tmp_path / "data")
    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    cfg.uploads_dir.mkdir(parents=True, exist_ok=True)
    cfg.jobs_log_dir.mkdir(parents=True, exist_ok=True)
    return cfg


@pytest.fixture()
def app_client(tmp_path: Path):
    cfg = make_cfg(tmp_path)
    init_db(cfg.db_path)
    app = create_app(cfg)
    auth = AuthManager(cfg.db_path)
    auth.create_user("alice", "password1")
    with TestClient(app) as client:
        yield client, cfg


def test_password_hash_roundtrip():
    stored = hash_password("s3cret!")
    assert verify_password("s3cret!", stored)
    assert not verify_password("wrong", stored)
    assert not verify_password("s3cret!", "garbage")


def test_login_flow_and_guard(app_client):
    client, _ = app_client

    # 未登录访问受保护接口 -> 401
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/runs").status_code == 401

    # 错误密码 -> 401
    r = client.post("/api/auth/login", json={"username": "alice", "password": "nope"})
    assert r.status_code == 401

    # 正确登录 -> cookie 会话生效
    r = client.post("/api/auth/login", json={"username": "alice", "password": "password1"})
    assert r.status_code == 200
    assert r.json()["user"]["username"] == "alice"
    assert client.get("/api/auth/me").status_code == 200

    # 登出后失效
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/auth/me").status_code == 401


def test_login_lockout_after_failures(app_client):
    client, cfg = app_client
    auth = AuthManager(cfg.db_path)
    auth.create_user("bob", "password1")

    for _ in range(5):
        r = client.post("/api/auth/login", json={"username": "bob", "password": "bad"})
    assert r.status_code in (401, 429)

    # 锁定期间即使密码正确也 429
    r = client.post("/api/auth/login", json={"username": "bob", "password": "password1"})
    assert r.status_code == 429


def test_deactivated_user_cannot_login(app_client):
    client, cfg = app_client
    auth = AuthManager(cfg.db_path)
    auth.create_user("carol", "password1")
    auth.set_active("carol", False)
    r = client.post("/api/auth/login", json={"username": "carol", "password": "password1"})
    assert r.status_code == 401
