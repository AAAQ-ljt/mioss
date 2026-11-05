from __future__ import annotations

import json
import random
import sqlite3
import threading
import time
import uuid
from typing import Any

from ..config import DB_PATH
from .comfy import ComfyClient, build_graph
from .projects import get_page, list_pages, project_dir
from .prompt import compose_for_page


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def get_job(conn: sqlite3.Connection, job_id: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM generation_job WHERE id = ?", (job_id,)).fetchone()
    return dict(row) if row else None


def _create_job(
    conn: sqlite3.Connection,
    page_id: str,
    prompt: str,
    negative: str,
    seed: int,
    profile: str,
    status: str,
    comfy_prompt_id: str | None = None,
    error: str | None = None,
) -> str:
    job_id = uuid.uuid4().hex[:12]
    conn.execute(
        """
        INSERT INTO generation_job(
          id, page_id, prompt, negative, seed, workflow_profile, comfy_prompt_id,
          status, error, started_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """,
        (job_id, page_id, prompt, negative, seed, profile, comfy_prompt_id, status, error),
    )
    conn.execute("UPDATE page SET status = ?, updated_at = datetime('now') WHERE id = ?", (status, page_id))
    conn.commit()
    return job_id


def _poll(job_id: str, prompt_id: str, page_id: str, project_id: str, order_no: int) -> None:
    conn = _connect()
    client = ComfyClient()
    try:
        conn.execute("UPDATE generation_job SET status = 'running' WHERE id = ?", (job_id,))
        conn.execute("UPDATE page SET status = 'running', updated_at = datetime('now') WHERE id = ?", (page_id,))
        conn.commit()
        history = client.wait(prompt_id)
        image = client.output_image(history)
        if not image:
            raise RuntimeError("ComfyUI finished without output image")
        data = client.download(image)
        output_path = project_dir(project_id) / "images" / image["filename"]
        output_path.write_bytes(data)
        conn.execute(
            "UPDATE generation_job SET status = 'succeeded', output_path = ?, finished_at = datetime('now') WHERE id = ?",
            (str(output_path), job_id),
        )
        conn.execute(
            "UPDATE page SET status = 'done', image_path = ?, updated_at = datetime('now') WHERE id = ?",
            (str(output_path), page_id),
        )
    except Exception as error:
        conn.execute(
            "UPDATE generation_job SET status = 'failed', error = ?, finished_at = datetime('now') WHERE id = ?",
            (str(error), job_id),
        )
        conn.execute("UPDATE page SET status = 'failed', updated_at = datetime('now') WHERE id = ?", (page_id,))
    finally:
        conn.commit()
        conn.close()
        client.close()


def list_jobs(conn: sqlite3.Connection, limit: int = 50) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT j.*, p.order_no, p.project_id
        FROM generation_job j JOIN page p ON p.id = j.page_id
        ORDER BY j.started_at DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [dict(row) for row in rows]


def cancel_job(job_id: str) -> dict[str, Any] | None:
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM generation_job WHERE id = ?", (job_id,)).fetchone()
        if not row:
            return None
        job = dict(row)
        client = ComfyClient()
        try:
            if job["status"] == "queued" and job.get("comfy_prompt_id"):
                client.delete_pending([job["comfy_prompt_id"]])
            elif job["status"] == "running":
                client.interrupt()
        finally:
            client.close()
        conn.execute(
            "UPDATE generation_job SET status = 'cancelled', finished_at = datetime('now') WHERE id = ?",
            (job_id,),
        )
        conn.execute(
            "UPDATE page SET status = 'cancelled', updated_at = datetime('now') WHERE id = ?",
            (job["page_id"],),
        )
        conn.commit()
        return get_job(conn, job_id)
    finally:
        conn.close()


def wait_for_job(job_id: str, timeout: float = 900.0) -> dict[str, Any]:
    conn = _connect()
    try:
        deadline = time.time() + timeout
        while time.time() < deadline:
            job = get_job(conn, job_id)
            if job and job["status"] in {"succeeded", "failed", "cancelled"}:
                return job
            time.sleep(2)
        raise TimeoutError(f"job did not finish: {job_id}")
    finally:
        conn.close()


def _generate_project(project_id: str, seed: int | None, profile: dict[str, Any] | None) -> None:
    conn = _connect()
    try:
        pages = list_pages(conn, project_id)
    finally:
        conn.close()

    for page in pages:
        conn = _connect()
        try:
            if not page.get("prompt"):
                compose_for_page(conn, page["id"], save=True)
                page = get_page(conn, page["id"]) or page
        finally:
            conn.close()
        if not page.get("prompt"):
            continue
        job_id = submit_page(page["id"], seed=seed, profile=profile)
        try:
            wait_for_job(job_id)
        except TimeoutError:
            continue


def generate_project(project_id: str, seed: int | None = None, profile: dict[str, Any] | None = None) -> dict[str, Any]:
    threading.Thread(target=_generate_project, args=(project_id, seed, profile), daemon=True).start()
    return {"project_id": project_id, "status": "started"}


def submit_page(page_id: str, seed: int | None = None, profile: dict[str, Any] | None = None) -> str:
    conn = _connect()
    try:
        page = get_page(conn, page_id)
        if not page:
            raise KeyError(f"page not found: {page_id}")
        if not page.get("prompt"):
            raise ValueError("page prompt is empty")

        resolved_seed = int(seed if seed is not None else page.get("seed") or random.randint(1, 2**53))
        merged_profile = {
            **(profile or {}),
            "filename_prefix": f"mioss/{page['project_id']}/page-{int(page['order_no']):03d}",
        }
        client = ComfyClient()
        try:
            client.validate_profile(merged_profile)
            graph = build_graph(page["prompt"], page.get("negative") or "", resolved_seed, merged_profile)
            response = client.queue(graph)
            prompt_id = response["prompt_id"]
            job_id = _create_job(
                conn,
                page_id,
                page["prompt"],
                page.get("negative") or "",
                resolved_seed,
                json.dumps(merged_profile, ensure_ascii=False),
                "queued",
                prompt_id,
            )
        except Exception as error:
            job_id = _create_job(
                conn,
                page_id,
                page["prompt"],
                page.get("negative") or "",
                resolved_seed,
                json.dumps(merged_profile, ensure_ascii=False),
                "failed",
                None,
                str(error),
            )
            return job_id
        finally:
            client.close()

        threading.Thread(
            target=_poll,
            args=(job_id, prompt_id, page_id, page["project_id"], int(page["order_no"])),
            daemon=True,
        ).start()
        return job_id
    finally:
        conn.close()
