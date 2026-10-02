from __future__ import annotations

import socket
from pathlib import Path
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .auth import AuthError, AuthManager, COOKIE_NAME, User
from .arcstore import ArcStore
from .artifacts import ArtifactError, Artifacts
from .config import Config, load_config
from .db import init_db
from .jobs import JobError, JobManager
from .run_versions import RunVersions, VersionError
from .versioned_artifacts import VersionedArtifacts

CLIENT_DIST = Path(__file__).resolve().parent.parent.parent / "client" / "dist"


class LoginBody(BaseModel):
    username: str
    password: str


class JobBody(BaseModel):
    mode: str
    params: dict = {}


class CurrentVersionBody(BaseModel):
    problem_id: str
    run_id: str


class NewVersionBody(CurrentVersionBody):
    previous_run_id: str


class RelatedStageBody(BaseModel):
    run_id: str
    parent_run_id: str


class SelectVersionBody(CurrentVersionBody):
    expected_selected: str
    reviewed: bool = False


def create_app(cfg: Config | None = None) -> FastAPI:
    cfg = cfg or load_config()
    init_db(cfg.db_path)
    auth = AuthManager(cfg.db_path, session_days=cfg.session_days)
    jobs = JobManager(cfg)
    arts = Artifacts(ArcStore(cfg.arc_db), cfg.arc_reports, jobs)
    arts = VersionedArtifacts(arts, RunVersions(cfg.data_dir / "run_versions.json"))
    jobs.recover()

    app = FastAPI(title="arc-arena", docs_url=None, redoc_url=None, openapi_url=None)

    # ------------------------------------------------------------ guards
    def require_user(request: Request) -> User:
        token = request.cookies.get(COOKIE_NAME, "")
        user = auth.session_user(token)
        if user is None:
            raise HTTPException(status_code=401, detail="未登录或会话过期")
        return user

    def require_admin(user: User = Depends(require_user)) -> User:
        if not user.is_admin:
            raise HTTPException(status_code=403, detail="仅管理员可管理运行版本")
        return user

    @app.exception_handler(VersionError)
    async def _version_error(_request, exc: VersionError):
        body = {"detail": exc.message}
        if exc.current_run_id:
            body["current_run_id"] = exc.current_run_id
        return JSONResponse(body, status_code=exc.status)

    @app.exception_handler(AuthError)
    async def _auth_error(_request, exc: AuthError):
        return JSONResponse({"detail": exc.message}, status_code=exc.status)

    @app.exception_handler(JobError)
    async def _job_error(_request, exc: JobError):
        return JSONResponse({"detail": exc.message}, status_code=exc.status)

    @app.exception_handler(ArtifactError)
    async def _art_error(_request, exc: ArtifactError):
        return JSONResponse({"detail": exc.message}, status_code=exc.status)

    # -------------------------------------------------------------- auth
    @app.post("/api/auth/login")
    def login(body: LoginBody):
        user, token = auth.login(body.username, body.password)
        response = JSONResponse({"user": {"username": user.username, "is_admin": user.is_admin}})
        response.set_cookie(
            COOKIE_NAME, token,
            httponly=True, samesite="lax", max_age=cfg.session_days * 86400, path="/",
        )
        return response

    @app.post("/api/auth/logout")
    def logout(request: Request):
        auth.logout(request.cookies.get(COOKIE_NAME, ""))
        response = JSONResponse({"ok": True})
        response.delete_cookie(COOKIE_NAME, path="/")
        return response

    @app.get("/api/auth/me")
    def me(user: User = Depends(require_user)):
        return {"username": user.username, "is_admin": user.is_admin}

    # ------------------------------------------------------------ health
    def _tcp_ok(host: str, port: int, timeout: float = 1.5) -> bool:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except OSError:
            return False

    def _env_value(key: str) -> str | None:
        try:
            for line in (cfg.backend_root / ".env").read_text(encoding="utf-8").splitlines():
                if line.startswith(key + "="):
                    return line.split("=", 1)[1].strip().strip('"')
        except OSError:
            pass
        return None

    def _sse_service_ok(env_key: str) -> bool:
        url = _env_value(env_key)
        if not url:
            return False
        try:
            parsed = urlparse(url if "//" in url else f"http://{url}")
            host = parsed.hostname or "127.0.0.1"
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
        except ValueError:
            return False
        return _tcp_ok(host, port)

    @app.get("/api/health")
    def health(user: User = Depends(require_user)):
        webresearch_ok = False
        webresearch_cmd = _env_value("ARC_MCP_WEBRESEARCH_CMD")
        if webresearch_cmd:
            webresearch_ok = Path(webresearch_cmd.split()[0]).exists()
        running = len([j for j in jobs.list_jobs(200) if j["status"] == "running"])
        return {
            "scholartrace": _sse_service_ok("ARC_SCHOLARTRACE_URL"),
            "scholaranalysis": _sse_service_ok("ARC_SCHOLARANALYSIS_URL"),
            "webresearch": webresearch_ok,
            "running_jobs": running,
            "max_jobs": cfg.max_concurrent_jobs,
        }

    # -------------------------------------------------------------- jobs
    @app.post("/api/jobs")
    def submit_job(body: JobBody, user: User = Depends(require_user)):
        return jobs.submit(body.mode, body.params, user)

    @app.get("/api/jobs")
    def list_jobs(user: User = Depends(require_user)):
        return {"jobs": arts.visible_jobs(jobs.list_jobs())}

    @app.get("/api/jobs/{job_id}/visibility")
    def job_visibility(job_id: str, user: User = Depends(require_user)):
        return arts.job_visibility(jobs.status(job_id)["job"])

    @app.get("/api/jobs/{job_id}")
    def job_status(job_id: str, user: User = Depends(require_user)):
        value = jobs.status(job_id)
        arts.require_visible_job(value["job"])
        return value

    @app.delete("/api/jobs/{job_id}")
    def cancel_job(job_id: str, user: User = Depends(require_user)):
        return jobs.cancel(job_id, user)

    # Display metadata is separate from ARC's scientific records.
    @app.get("/api/run-versions")
    def version_records(user: User = Depends(require_admin)):
        return arts.versions.snapshot()

    @app.post("/api/run-versions/current")
    def register_current(body: CurrentVersionBody, user: User = Depends(require_admin)):
        return arts.register_current(body.problem_id, body.run_id, user.username)

    @app.post("/api/run-versions/versions")
    def register_version(body: NewVersionBody, user: User = Depends(require_admin)):
        return arts.register_version(body.problem_id, body.run_id, body.previous_run_id, user.username)

    @app.post("/api/run-versions/stages")
    def register_stage(body: RelatedStageBody, user: User = Depends(require_admin)):
        return arts.register_stage(body.run_id, body.parent_run_id, user.username)

    @app.post("/api/run-versions/selection")
    def select_version(body: SelectVersionBody, user: User = Depends(require_admin)):
        return arts.select_version(body.problem_id, body.run_id, body.expected_selected,
            body.reviewed, user.username)

    @app.get("/api/run-versions/runs/{run_dir}")
    def archived_run(run_dir: str, user: User = Depends(require_admin)):
        return arts.artifacts.run_detail(run_dir)

    @app.get("/api/run-versions/runs/{run_dir}/file")
    def archived_file(run_dir: str, name: str, user: User = Depends(require_admin)):
        return arts.artifacts.read_file(run_dir, name)

    # -------------------------------------------------------------- runs
    @app.get("/api/runs")
    def list_runs(user: User = Depends(require_user)):
        return {"runs": arts.list_runs()}

    @app.get("/api/runs/{run_dir}/visibility")
    def run_visibility(run_dir: str, user: User = Depends(require_user)):
        return arts.visibility(run_dir)

    @app.get("/api/runs/{run_dir}")
    def run_detail(run_dir: str, user: User = Depends(require_user)):
        return arts.run_detail(run_dir)

    @app.get("/api/runs/{run_dir}/file")
    def run_file(run_dir: str, name: str, user: User = Depends(require_user)):
        return arts.read_file(run_dir, name)

    # ------------------------------------------------------------ static
    if CLIENT_DIST.exists():
        app.mount("/assets", StaticFiles(directory=CLIENT_DIST / "assets"), name="assets")

        @app.get("/", include_in_schema=False)
        def index():
            return FileResponse(CLIENT_DIST / "index.html")

        @app.exception_handler(404)
        async def spa_fallback(request: Request, _exc):
            if request.url.path.startswith("/api"):
                return JSONResponse({"detail": "not found"}, status_code=404)
            f = CLIENT_DIST / "index.html"
            if f.exists():
                return FileResponse(f)
            return JSONResponse({"detail": "not found"}, status_code=404)

    return app
