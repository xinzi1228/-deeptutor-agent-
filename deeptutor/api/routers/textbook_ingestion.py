from __future__ import annotations

from hashlib import sha256
import os
from pathlib import Path
import stat
import tempfile

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
)
from fastapi.responses import FileResponse

from deeptutor.api.routers.auth import require_admin
from deeptutor.multi_user.paths import get_admin_path_service
from deeptutor.services.textbook_ingestion import TextbookJobStore, run_textbook_job
from deeptutor.utils.document_validator import DocumentValidator

router = APIRouter(dependencies=[Depends(require_admin)])

_TEXTBOOK_EXTENSIONS = {".pdf", ".docx", ".pptx", ".png", ".jpg", ".jpeg", ".webp"}


def get_textbook_root() -> Path:
    return get_admin_path_service().get_workspace_dir() / "textbooks"


async def _persist_original(file: UploadFile, root: Path) -> tuple[Path, str, str]:
    try:
        safe_name = DocumentValidator.validate_upload_safety(
            file.filename or "textbook",
            None,
            allowed_extensions=_TEXTBOOK_EXTENSIONS,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    incoming = root / "incoming"
    incoming.mkdir(parents=True, exist_ok=True)
    digest = sha256()
    written = 0
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(prefix="textbook-", suffix=".part", dir=incoming, delete=False) as handle:
            temp_path = Path(handle.name)
            while chunk := await file.read(1024 * 1024):
                written += len(chunk)
                if written > DocumentValidator.MAX_FILE_SIZE:
                    raise HTTPException(status_code=400, detail="教材文件不能超过 200MB")
                digest.update(chunk)
                handle.write(chunk)
        source_hash = digest.hexdigest()
        target_dir = root / "originals" / source_hash
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / safe_name
        if target.exists():
            temp_path.unlink(missing_ok=True)
        else:
            os.replace(temp_path, target)
            try:
                target.chmod(stat.S_IREAD)
            except OSError:
                pass
        return target, source_hash, safe_name
    except Exception:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
        raise


@router.post("/import", status_code=202)
async def import_textbook(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    engine: str | None = Form(default=None),
) -> dict:
    root = get_textbook_root()
    source_path, source_hash, safe_name = await _persist_original(file, root)
    normalized_engine = str(engine or "").strip().lower() or None
    job = TextbookJobStore(root).create(
        source_path=source_path,
        original_name=safe_name,
        source_hash=source_hash,
        engine=normalized_engine,
    )
    background_tasks.add_task(run_textbook_job, root, job.id)
    return {
        "job": job.model_dump(mode="json"),
        "message": "教材原件已只读保存，正在转换为可审核 Markdown。",
    }


@router.get("/jobs")
async def list_textbook_jobs(limit: int = Query(default=100, ge=1, le=200)) -> dict:
    rows = TextbookJobStore(get_textbook_root()).list(limit=limit)
    return {"jobs": [row.model_dump(mode="json") for row in rows]}


@router.get("/jobs/{job_id}")
async def get_textbook_job(job_id: str) -> dict:
    job = TextbookJobStore(get_textbook_root()).get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="找不到教材导入任务")
    return {"job": job.model_dump(mode="json")}


@router.post("/jobs/{job_id}/retry", status_code=202)
async def retry_textbook_job(job_id: str, background_tasks: BackgroundTasks) -> dict:
    store = TextbookJobStore(get_textbook_root())
    job = store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="找不到教材导入任务")
    if job.status not in {"failed", "running"}:
        raise HTTPException(status_code=409, detail="只有失败或中断的任务需要继续")
    job = store.update(job_id, status="queued", progress_message="已从原件和解析缓存继续排队", error="")
    background_tasks.add_task(run_textbook_job, get_textbook_root(), job_id)
    return {"job": job.model_dump(mode="json")}


@router.post("/jobs/{job_id}/cancel")
async def cancel_textbook_job(job_id: str) -> dict:
    store = TextbookJobStore(get_textbook_root())
    job = store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="找不到教材导入任务")
    job = store.update(job_id, status="cancelled", progress_message="已取消；原件保留，可重新创建任务")
    return {"job": job.model_dump(mode="json")}


@router.get("/jobs/{job_id}/markdown")
async def download_textbook_markdown(job_id: str) -> FileResponse:
    job = TextbookJobStore(get_textbook_root()).get(job_id)
    path = Path(job.markdown_path) if job and job.markdown_path else None
    if path is None or not path.is_file():
        raise HTTPException(status_code=404, detail="该任务还没有可下载的 Markdown")
    return FileResponse(path, filename=f"{Path(job.original_name).stem}.md", media_type="text/markdown")
