import hashlib
import hmac
import os
import secrets
import sqlite3
from contextlib import closing
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, Literal

from fastapi import Cookie, Depends, FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

Kind = Literal["lost", "found"]
RequestKind = Literal["claim", "lead"]
Moderation = Literal["待审核", "已通过", "已驳回"]
DB_DEFAULT = Path(os.getenv("HDUHELP_DB", "./data/hduhelp.sqlite3"))
COOKIE_NAME = "hduhelp_session"
SESSION_DAYS = 14


def now() -> str:
    return datetime.now(UTC).isoformat()


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 240_000)
    return f"{salt.hex()}:{derived.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        salt_hex, digest = encoded.split(":", 1)
        return hmac.compare_digest(hash_password(password, bytes.fromhex(salt_hex)), f"{salt_hex}:{digest}")
    except (ValueError, TypeError):
        return False


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    return connection


def initialize(path: Path, admin_username: str | None, admin_password: str | None) -> None:
    with closing(connect(path)) as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                nickname TEXT NOT NULL,
                student_number TEXT NOT NULL UNIQUE,
                role TEXT NOT NULL DEFAULT 'user' CHECK(role IN ('user','admin')),
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                expires_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY,
                author_id INTEGER NOT NULL REFERENCES users(id),
                kind TEXT NOT NULL CHECK(kind IN ('lost','found')),
                item_name TEXT NOT NULL,
                description TEXT NOT NULL,
                category TEXT,
                location TEXT,
                event_time TEXT,
                lifecycle_status TEXT NOT NULL,
                moderation_status TEXT NOT NULL DEFAULT '待审核',
                rejection_reason TEXT,
                withdrawn INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                approved_at TEXT
            );
            CREATE TABLE IF NOT EXISTS revisions (
                post_id INTEGER PRIMARY KEY REFERENCES posts(id) ON DELETE CASCADE,
                item_name TEXT NOT NULL,
                description TEXT NOT NULL,
                category TEXT,
                location TEXT,
                event_time TEXT,
                moderation_status TEXT NOT NULL DEFAULT '待审核',
                rejection_reason TEXT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS requests (
                id INTEGER PRIMARY KEY,
                post_id INTEGER NOT NULL REFERENCES posts(id),
                requester_id INTEGER NOT NULL REFERENCES users(id),
                kind TEXT NOT NULL CHECK(kind IN ('claim','lead')),
                explanation TEXT NOT NULL,
                contact_method TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT '待处理',
                resolution_reason TEXT,
                removed INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY,
                reporter_id INTEGER NOT NULL REFERENCES users(id),
                target_type TEXT NOT NULL CHECK(target_type IN ('post','request')),
                target_id INTEGER NOT NULL,
                explanation TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT '待处理',
                moderator_reason TEXT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY,
                actor_id INTEGER NOT NULL REFERENCES users(id),
                action TEXT NOT NULL,
                target_type TEXT NOT NULL,
                target_id INTEGER NOT NULL,
                reason TEXT,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS posts_public_order ON posts(moderation_status, withdrawn, approved_at DESC);
            CREATE INDEX IF NOT EXISTS requests_post_status ON requests(post_id, status);
            CREATE INDEX IF NOT EXISTS reports_status ON reports(status, created_at);
            """
        )
        if admin_username and admin_password:
            found = db.execute("SELECT id FROM users WHERE username = ?", (admin_username,)).fetchone()
            if not found:
                db.execute(
                    "INSERT INTO users(username,password_hash,nickname,student_number,role,created_at) VALUES(?,?,?,?,?,?)",
                    (admin_username, hash_password(admin_password), "系统管理员", f"admin:{admin_username}", "admin", now()),
                )
            else:
                existing = db.execute("SELECT role FROM users WHERE username=?", (admin_username,)).fetchone()
                if existing["role"] != "admin":
                    raise RuntimeError("管理员用户名已被普通账号占用；请为管理员选择独立用户名。")
        db.commit()


class RegisterInput(BaseModel):
    username: str = Field(min_length=2, max_length=32, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=10, max_length=128)
    nickname: str = Field(min_length=1, max_length=40)
    student_number: str = Field(min_length=4, max_length=32, pattern=r"^[A-Za-z0-9-]+$")

    @field_validator("nickname")
    @classmethod
    def nickname_has_visible_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("称呼不能为空")
        return value


class LoginInput(BaseModel):
    username: str
    password: str


class PostInput(BaseModel):
    kind: Kind
    item_name: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=5, max_length=3000)
    category: str | None = Field(default=None, max_length=40)
    location: str | None = Field(default=None, max_length=120)
    event_time: str | None = Field(default=None, max_length=80)

    @field_validator("item_name", "description")
    @classmethod
    def required_text_has_visible_content(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("内容不能为空")
        return value


class RequestInput(BaseModel):
    explanation: str = Field(min_length=5, max_length=2000)
    contact_method: str = Field(min_length=2, max_length=120)

    @field_validator("explanation", "contact_method")
    @classmethod
    def request_text_has_visible_content(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("内容不能为空")
        return value


class ReasonInput(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)

    @field_validator("reason")
    @classmethod
    def reason_has_visible_content(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("处理原因不能为空")
        return value


class ReportInput(BaseModel):
    explanation: str = Field(min_length=5, max_length=2000)


def create_app(
    db_path: str | Path | None = None,
    admin_username: str | None = None,
    admin_password: str | None = None,
) -> FastAPI:
    path = Path(db_path) if db_path is not None else DB_DEFAULT
    @asynccontextmanager
    async def lifespan(_app):
        initialize(path, admin_username or os.getenv("HDUHELP_ADMIN_USERNAME"), admin_password or os.getenv("HDUHELP_ADMIN_PASSWORD"))
        yield

    app = FastAPI(title="杭助失物招领", version="1.0.0", lifespan=lifespan)
    app.state.db_path = path
    app.state.admin_username = admin_username or os.getenv("HDUHELP_ADMIN_USERNAME")
    app.state.admin_password = admin_password or os.getenv("HDUHELP_ADMIN_PASSWORD")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=os.getenv("HDUHELP_CORS_ORIGINS", "http://localhost:5173").split(","),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type"],
    )

    def db_conn():
        with closing(connect(path)) as db:
            yield db

    Db = Annotated[sqlite3.Connection, Depends(db_conn)]

    def current_user(
        db: Db,
        session_cookie: Annotated[str | None, Cookie(alias=COOKIE_NAME)] = None,
    ) -> sqlite3.Row:
        if not session_cookie:
            raise HTTPException(401, "请先登录")
        token_hash = hashlib.sha256(session_cookie.encode()).hexdigest()
        user = db.execute(
            "SELECT users.* FROM sessions JOIN users ON users.id=sessions.user_id WHERE token_hash=? AND expires_at>?",
            (token_hash, now()),
        ).fetchone()
        if not user:
            raise HTTPException(401, "登录已失效，请重新登录")
        return user

    CurrentUser = Annotated[sqlite3.Row, Depends(current_user)]

    def administrator(user: CurrentUser) -> sqlite3.Row:
        if user["role"] != "admin":
            raise HTTPException(403, "需要管理员权限")
        return user

    Admin = Annotated[sqlite3.Row, Depends(administrator)]

    def user_view(user: sqlite3.Row, *, include_student: bool = False) -> dict:
        data = {"id": user["id"], "username": user["username"], "nickname": user["nickname"], "role": user["role"]}
        if include_student:
            data["student_number"] = user["student_number"]
            data["student_number_verified"] = False
        return data

    def post_view(row: sqlite3.Row, *, author: bool = False, revision: sqlite3.Row | None = None) -> dict:
        data = {
            "id": row["id"], "kind": row["kind"], "item_name": row["item_name"],
            "description": row["description"], "category": row["category"], "location": row["location"],
            "event_time": row["event_time"], "lifecycle_status": row["lifecycle_status"],
            "moderation_status": row["moderation_status"], "rejection_reason": row["rejection_reason"],
            "withdrawn": bool(row["withdrawn"]), "created_at": row["created_at"], "approved_at": row["approved_at"],
            "author_nickname": row["author_nickname"] if "author_nickname" in row.keys() else None,
        }
        if author:
            data["pending_revision"] = dict(revision) if revision else None
        if "author_student_number" in row.keys():
            data["author_student_number"] = row["author_student_number"]
            data["author_student_number_verified"] = False
        return data

    def log_action(db: sqlite3.Connection, actor: sqlite3.Row, action: str, target_type: str, target_id: int, reason: str | None = None):
        db.execute(
            "INSERT INTO audit_log(actor_id,action,target_type,target_id,reason,created_at) VALUES(?,?,?,?,?,?)",
            (actor["id"], action, target_type, target_id, reason, now()),
        )

    def get_post(db: sqlite3.Connection, post_id: int, *, public: bool = False) -> sqlite3.Row:
        row = db.execute("SELECT posts.*, users.nickname AS author_nickname FROM posts JOIN users ON users.id=posts.author_id WHERE posts.id=?", (post_id,)).fetchone()
        if not row or (public and (row["moderation_status"] != "已通过" or row["withdrawn"])):
            raise HTTPException(404, "内容不存在")
        return row

    def lifecycle(kind: str) -> tuple[str, ...]:
        return ("寻找中", "已找回", "已结束") if kind == "lost" else ("待认领", "已归还", "已结束")

    def close_open_requests(db: sqlite3.Connection, post_id: int, reason: str) -> None:
        db.execute("UPDATE requests SET status='已拒绝',resolution_reason=? WHERE post_id=? AND status='待处理'", (reason, post_id))

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    @app.post("/api/auth/register", status_code=201)
    def register(payload: RegisterInput, response: Response, db: Db):
        try:
            cursor = db.execute(
                "INSERT INTO users(username,password_hash,nickname,student_number,created_at) VALUES(?,?,?,?,?)",
                (payload.username, hash_password(payload.password), payload.nickname, payload.student_number, now()),
            )
            db.commit()
        except sqlite3.IntegrityError:
            raise HTTPException(409, "用户名或学号已注册")
        user = db.execute("SELECT * FROM users WHERE id=?", (cursor.lastrowid,)).fetchone()
        issue_session(db, response, user)
        return user_view(user, include_student=True)

    def issue_session(db: sqlite3.Connection, response: Response, user: sqlite3.Row):
        token = secrets.token_urlsafe(32)
        db.execute("INSERT INTO sessions(token_hash,user_id,expires_at) VALUES(?,?,?)", (
            hashlib.sha256(token.encode()).hexdigest(), user["id"], (datetime.now(UTC) + timedelta(days=SESSION_DAYS)).isoformat(),
        ))
        db.commit()
        response.set_cookie(COOKIE_NAME, token, httponly=True, samesite="lax", secure=os.getenv("HDUHELP_SECURE_COOKIE", "0") == "1", max_age=SESSION_DAYS * 86400, path="/")

    @app.post("/api/auth/login")
    def login(payload: LoginInput, response: Response, db: Db):
        user = db.execute("SELECT * FROM users WHERE username=?", (payload.username,)).fetchone()
        if not user or not verify_password(payload.password, user["password_hash"]):
            raise HTTPException(401, "用户名或密码错误")
        issue_session(db, response, user)
        return user_view(user, include_student=True)

    @app.post("/api/auth/logout")
    def logout(response: Response, db: Db, session_cookie: Annotated[str | None, Cookie(alias=COOKIE_NAME)] = None):
        if session_cookie:
            db.execute("DELETE FROM sessions WHERE token_hash=?", (hashlib.sha256(session_cookie.encode()).hexdigest(),))
            db.commit()
        response.delete_cookie(COOKIE_NAME, path="/")
        return {"ok": True}

    @app.get("/api/auth/me")
    def me(user: CurrentUser):
        return user_view(user, include_student=True)

    @app.get("/api/posts")
    def list_posts(
        db: Db,
        kind: Kind | None = None,
        status: str | None = None,
        location: str | None = None,
        q: str | None = None,
        limit: int = Query(20, ge=1, le=100),
        offset: int = Query(0, ge=0),
    ):
        clauses = ["posts.moderation_status='已通过'", "posts.withdrawn=0"]
        params: list[object] = []
        for column, value in (("posts.kind", kind), ("posts.lifecycle_status", status)):
            if value:
                clauses.append(f"{column}=?"); params.append(value)
        if location:
            clauses.append("posts.location LIKE ?"); params.append(f"%{location}%")
        if q:
            clauses.append("(posts.item_name LIKE ? OR posts.description LIKE ?)"); params.extend((f"%{q}%", f"%{q}%"))
        where = " AND ".join(clauses)
        total = db.execute(f"SELECT COUNT(*) FROM posts WHERE {where}", params).fetchone()[0]
        rows = db.execute(
            f"SELECT posts.*,users.nickname AS author_nickname FROM posts JOIN users ON users.id=posts.author_id WHERE {where} ORDER BY COALESCE(posts.approved_at,posts.created_at) DESC,posts.id DESC LIMIT ? OFFSET ?",
            (*params, limit, offset),
        ).fetchall()
        return {"items": [post_view(row) for row in rows], "total": total, "limit": limit, "offset": offset}

    @app.get("/api/posts/{post_id}")
    def public_post(post_id: int, db: Db):
        return post_view(get_post(db, post_id, public=True))

    @app.post("/api/posts", status_code=201)
    def create_post(payload: PostInput, user: CurrentUser, db: Db):
        cursor = db.execute(
            "INSERT INTO posts(author_id,kind,item_name,description,category,location,event_time,lifecycle_status,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (user["id"], payload.kind, payload.item_name.strip(), payload.description.strip(), payload.category, payload.location, payload.event_time, "寻找中" if payload.kind == "lost" else "待认领", now()),
        )
        db.commit()
        return post_view(get_post(db, cursor.lastrowid))

    @app.get("/api/my/posts")
    def my_posts(user: CurrentUser, db: Db):
        rows = db.execute("SELECT posts.*,users.nickname AS author_nickname FROM posts JOIN users ON users.id=posts.author_id WHERE author_id=? ORDER BY created_at DESC", (user["id"],)).fetchall()
        result = []
        for row in rows:
            revision = db.execute("SELECT * FROM revisions WHERE post_id=?", (row["id"],)).fetchone()
            result.append(post_view(row, author=True, revision=revision))
        return result

    @app.put("/api/posts/{post_id}")
    def update_post(post_id: int, payload: PostInput, user: CurrentUser, db: Db):
        row = get_post(db, post_id)
        if row["author_id"] != user["id"]:
            raise HTTPException(403, "只能编辑自己的内容")
        if row["kind"] != payload.kind:
            raise HTTPException(422, "不能更改内容类型")
        fields = (payload.item_name.strip(), payload.description.strip(), payload.category, payload.location, payload.event_time)
        if row["moderation_status"] != "已通过":
            db.execute("UPDATE posts SET item_name=?,description=?,category=?,location=?,event_time=?,moderation_status='待审核',rejection_reason=NULL WHERE id=?", (*fields, post_id))
        else:
            db.execute(
                "INSERT INTO revisions(post_id,item_name,description,category,location,event_time,moderation_status,rejection_reason,created_at) VALUES(?,?,?,?,?,?,'待审核',NULL,?) ON CONFLICT(post_id) DO UPDATE SET item_name=excluded.item_name,description=excluded.description,category=excluded.category,location=excluded.location,event_time=excluded.event_time,moderation_status='待审核',rejection_reason=NULL,created_at=excluded.created_at",
                (post_id, *fields, now()),
            )
        db.commit()
        updated = get_post(db, post_id)
        revision = db.execute("SELECT * FROM revisions WHERE post_id=?", (post_id,)).fetchone()
        return post_view(updated, author=True, revision=revision)

    @app.post("/api/posts/{post_id}/status")
    def set_post_status(post_id: int, data: dict, user: CurrentUser, db: Db):
        row = get_post(db, post_id)
        if row["author_id"] != user["id"]:
            raise HTTPException(403, "只能更新自己的内容")
        next_status = data.get("status")
        if next_status not in lifecycle(row["kind"]):
            raise HTTPException(422, "无效的内容状态")
        active_status = "寻找中" if row["kind"] == "lost" else "待认领"
        if row["lifecycle_status"] != active_status and next_status == active_status:
            raise HTTPException(409, "已解决或结束的内容不能重新开放")
        db.execute("UPDATE posts SET lifecycle_status=? WHERE id=?", (next_status, post_id))
        if next_status == "已结束" or next_status in ("已找回", "已归还"):
            close_open_requests(db, post_id, f"关联内容已更新为「{next_status}」")
        db.commit()
        return post_view(get_post(db, post_id))

    @app.delete("/api/posts/{post_id}")
    def delete_post(post_id: int, user: CurrentUser, db: Db):
        row = get_post(db, post_id)
        if row["author_id"] != user["id"]:
            raise HTTPException(403, "只能删除自己的内容")
        counts = db.execute("SELECT (SELECT COUNT(*) FROM requests WHERE post_id=?)+(SELECT COUNT(*) FROM reports WHERE target_type='post' AND target_id=?)", (post_id, post_id)).fetchone()[0]
        if counts:
            db.execute("UPDATE posts SET withdrawn=1 WHERE id=?", (post_id,))
            action = "withdraw"
        else:
            db.execute("DELETE FROM posts WHERE id=?", (post_id,))
            action = "delete"
        log_action(db, user, action, "post", post_id)
        db.commit()
        return {"ok": True, "withdrawn": bool(counts)}

    def get_request(db: sqlite3.Connection, request_id: int) -> sqlite3.Row:
        row = db.execute("SELECT requests.*,posts.author_id AS post_author_id,posts.kind AS post_kind,posts.withdrawn FROM requests JOIN posts ON posts.id=requests.post_id WHERE requests.id=?", (request_id,)).fetchone()
        if not row or row["removed"]:
            raise HTTPException(404, "请求不存在")
        return row

    def request_view(row: sqlite3.Row) -> dict:
        return {"id": row["id"], "post_id": row["post_id"], "kind": row["kind"], "explanation": row["explanation"], "contact_method": row["contact_method"], "status": row["status"], "resolution_reason": row["resolution_reason"], "created_at": row["created_at"]}

    @app.post("/api/posts/{post_id}/requests", status_code=201)
    def create_request(post_id: int, payload: RequestInput, user: CurrentUser, db: Db):
        post = get_post(db, post_id, public=True)
        if post["author_id"] == user["id"]:
            raise HTTPException(422, "不能对自己的内容提交请求")
        if post["lifecycle_status"] in ("已找回", "已归还", "已结束"):
            raise HTTPException(409, "该内容已结束处理")
        kind: RequestKind = "claim" if post["kind"] == "found" else "lead"
        cursor = db.execute("INSERT INTO requests(post_id,requester_id,kind,explanation,contact_method,created_at) VALUES(?,?,?,?,?,?)", (post_id, user["id"], kind, payload.explanation.strip(), payload.contact_method.strip(), now()))
        db.commit()
        row = db.execute("SELECT * FROM requests WHERE id=?", (cursor.lastrowid,)).fetchone()
        return request_view(row)

    @app.get("/api/my/requests")
    def my_requests(user: CurrentUser, db: Db):
        rows = db.execute("SELECT requests.*,posts.author_id AS post_author_id,posts.kind AS post_kind,posts.withdrawn,posts.item_name FROM requests JOIN posts ON posts.id=requests.post_id WHERE requester_id=? AND removed=0 ORDER BY created_at DESC", (user["id"],)).fetchall()
        return [{**request_view(row), "item_name": row["item_name"]} for row in rows]

    @app.get("/api/posts/{post_id}/requests")
    def post_requests(post_id: int, user: CurrentUser, db: Db):
        post = get_post(db, post_id)
        if post["author_id"] != user["id"]:
            raise HTTPException(403, "只有内容发布者能查看请求")
        rows = db.execute("SELECT requests.*,posts.author_id AS post_author_id,posts.kind AS post_kind,posts.withdrawn,users.nickname AS requester_nickname FROM requests JOIN posts ON posts.id=requests.post_id JOIN users ON users.id=requests.requester_id WHERE post_id=? AND removed=0 ORDER BY created_at DESC", (post_id,)).fetchall()
        return [{**request_view(row), "requester_nickname": row["requester_nickname"]} for row in rows]

    @app.get("/api/requests/{request_id}")
    def request_detail(request_id: int, user: CurrentUser, db: Db):
        row = get_request(db, request_id)
        if user["id"] not in (row["requester_id"], row["post_author_id"]):
            raise HTTPException(403, "没有权限查看此请求")
        return request_view(row)

    @app.post("/api/requests/{request_id}/withdraw")
    def withdraw_request(request_id: int, user: CurrentUser, db: Db):
        row = get_request(db, request_id)
        if row["requester_id"] != user["id"]:
            raise HTTPException(403, "只能撤回自己的请求")
        if row["status"] != "待处理":
            raise HTTPException(409, "只有待处理的请求可以撤回")
        db.execute("UPDATE requests SET status='已撤回' WHERE id=?", (request_id,)); db.commit()
        return {"ok": True}

    @app.post("/api/requests/{request_id}/accept")
    def accept_request(request_id: int, user: CurrentUser, db: Db):
        row = get_request(db, request_id)
        if row["post_author_id"] != user["id"]:
            raise HTTPException(403, "只有内容发布者能处理请求")
        if row["status"] != "待处理":
            raise HTTPException(409, "此请求已处理")
        resolved = "已归还" if row["post_kind"] == "found" else "已找回"
        db.execute("UPDATE requests SET status='已接受' WHERE id=?", (request_id,))
        db.execute("UPDATE posts SET lifecycle_status=? WHERE id=?", (resolved, row["post_id"]))
        close_open_requests(db, row["post_id"], "已有请求被接受")
        db.commit()
        return request_view(get_request(db, request_id))

    @app.post("/api/requests/{request_id}/reject")
    def reject_request(request_id: int, user: CurrentUser, db: Db, payload: ReasonInput):
        row = get_request(db, request_id)
        if row["post_author_id"] != user["id"]:
            raise HTTPException(403, "只有内容发布者能处理请求")
        if row["status"] != "待处理":
            raise HTTPException(409, "此请求已处理")
        db.execute("UPDATE requests SET status='已拒绝',resolution_reason=? WHERE id=?", (payload.reason, request_id)); db.commit()
        return request_view(get_request(db, request_id))

    def create_report(target_type: Literal["post", "request"], target_id: int, payload: ReportInput, user: CurrentUser, db: Db):
        if target_type == "post":
            target = get_post(db, target_id, public=True)
            if target["author_id"] == user["id"]:
                raise HTTPException(422, "不能举报自己的内容")
        else:
            target = get_request(db, target_id)
            if user["id"] not in (target["requester_id"], target["post_author_id"]):
                raise HTTPException(403, "只有请求参与者能举报私密请求")
        cursor = db.execute("INSERT INTO reports(reporter_id,target_type,target_id,explanation,created_at) VALUES(?,?,?,?,?)", (user["id"], target_type, target_id, payload.explanation.strip(), now()))
        db.commit()
        return {"id": cursor.lastrowid, "status": "待处理"}

    @app.post("/api/posts/{post_id}/reports", status_code=201)
    def report_post(post_id: int, payload: ReportInput, user: CurrentUser, db: Db):
        return create_report("post", post_id, payload, user, db)

    @app.post("/api/requests/{request_id}/reports", status_code=201)
    def report_request(request_id: int, payload: ReportInput, user: CurrentUser, db: Db):
        return create_report("request", request_id, payload, user, db)

    @app.get("/api/admin/reviews")
    def pending_reviews(admin: Admin, db: Db):
        posts = db.execute("SELECT posts.*,users.nickname AS author_nickname,users.student_number AS author_student_number FROM posts JOIN users ON users.id=posts.author_id WHERE moderation_status='待审核' ORDER BY created_at").fetchall()
        revisions = db.execute("SELECT revisions.*,posts.kind,posts.author_id,posts.lifecycle_status,posts.created_at,posts.approved_at,users.nickname AS author_nickname,users.student_number AS author_student_number FROM revisions JOIN posts ON posts.id=revisions.post_id JOIN users ON users.id=posts.author_id WHERE revisions.moderation_status='待审核' ORDER BY revisions.created_at").fetchall()
        return {"posts": [post_view(row) for row in posts], "revisions": [dict(row) for row in revisions]}

    @app.post("/api/admin/reviews/{post_id}/approve")
    def approve_post(post_id: int, admin: Admin, db: Db):
        row = get_post(db, post_id)
        revision = db.execute("SELECT * FROM revisions WHERE post_id=? AND moderation_status='待审核'", (post_id,)).fetchone()
        if revision:
            db.execute("UPDATE posts SET item_name=?,description=?,category=?,location=?,event_time=?,approved_at=? WHERE id=?", (revision["item_name"], revision["description"], revision["category"], revision["location"], revision["event_time"], now(), post_id))
            db.execute("UPDATE revisions SET moderation_status='已通过',rejection_reason=NULL WHERE post_id=?", (post_id,))
        elif row["moderation_status"] == "待审核":
            db.execute("UPDATE posts SET moderation_status='已通过',rejection_reason=NULL,approved_at=? WHERE id=?", (now(), post_id))
        else:
            raise HTTPException(409, "没有待审核的内容")
        log_action(db, admin, "approve", "post", post_id)
        db.commit()
        return post_view(get_post(db, post_id))

    @app.post("/api/admin/reviews/{post_id}/reject")
    def reject_post(post_id: int, payload: ReasonInput, admin: Admin, db: Db):
        row = get_post(db, post_id)
        revision = db.execute("SELECT post_id FROM revisions WHERE post_id=? AND moderation_status='待审核'", (post_id,)).fetchone()
        if revision:
            db.execute("UPDATE revisions SET moderation_status='已驳回',rejection_reason=? WHERE post_id=?", (payload.reason, post_id))
        elif row["moderation_status"] == "待审核":
            db.execute("UPDATE posts SET moderation_status='已驳回',rejection_reason=? WHERE id=?", (payload.reason, post_id))
        else:
            raise HTTPException(409, "没有待审核的内容")
        log_action(db, admin, "reject", "post", post_id, payload.reason); db.commit()
        return {"ok": True}

    @app.post("/api/admin/posts/{post_id}/take-down")
    def take_down(post_id: int, payload: ReasonInput, admin: Admin, db: Db):
        get_post(db, post_id)
        db.execute("UPDATE posts SET withdrawn=1 WHERE id=?", (post_id,))
        log_action(db, admin, "take-down", "post", post_id, payload.reason); db.commit()
        return {"ok": True}

    @app.get("/api/admin/reports")
    def admin_reports(admin: Admin, db: Db):
        rows = db.execute("SELECT reports.*,users.nickname AS reporter_nickname FROM reports JOIN users ON users.id=reports.reporter_id ORDER BY CASE status WHEN '待处理' THEN 0 ELSE 1 END,created_at DESC").fetchall()
        result = []
        for report in rows:
            data = {"id": report["id"], "reporter_nickname": report["reporter_nickname"], "target_type": report["target_type"], "target_id": report["target_id"], "explanation": report["explanation"], "status": report["status"], "moderator_reason": report["moderator_reason"], "created_at": report["created_at"]}
            if report["target_type"] == "post":
                target = db.execute("SELECT id,item_name,description,kind,withdrawn FROM posts WHERE id=?", (report["target_id"],)).fetchone()
                data["target"] = dict(target) if target else None
            else:
                target = db.execute("SELECT requests.id,requests.explanation,requests.contact_method,requests.kind,requests.status,posts.item_name,users.nickname AS requester_nickname FROM requests JOIN posts ON posts.id=requests.post_id JOIN users ON users.id=requests.requester_id WHERE requests.id=?", (report["target_id"],)).fetchone()
                data["target"] = dict(target) if target else None
            result.append(data)
        return result

    @app.post("/api/admin/reports/{report_id}/dismiss")
    def dismiss_report(report_id: int, payload: ReasonInput, admin: Admin, db: Db):
        report = db.execute("SELECT * FROM reports WHERE id=?", (report_id,)).fetchone()
        if not report: raise HTTPException(404, "举报不存在")
        db.execute("UPDATE reports SET status='已驳回',moderator_reason=? WHERE id=?", (payload.reason, report_id))
        log_action(db, admin, "dismiss-report", report["target_type"], report["target_id"], payload.reason); db.commit()
        return {"ok": True}

    @app.post("/api/admin/reports/{report_id}/remove")
    def remove_reported_target(report_id: int, payload: ReasonInput, admin: Admin, db: Db):
        report = db.execute("SELECT * FROM reports WHERE id=?", (report_id,)).fetchone()
        if not report: raise HTTPException(404, "举报不存在")
        if report["target_type"] == "post":
            db.execute("UPDATE posts SET withdrawn=1 WHERE id=?", (report["target_id"],))
        else:
            db.execute("UPDATE requests SET removed=1,status='已撤回',resolution_reason=? WHERE id=?", (payload.reason, report["target_id"]))
        db.execute("UPDATE reports SET status='已处理',moderator_reason=? WHERE id=?", (payload.reason, report_id))
        log_action(db, admin, "remove-reported-target", report["target_type"], report["target_id"], payload.reason); db.commit()
        return {"ok": True}

    return app


app = create_app()
