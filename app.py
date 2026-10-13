"""Smart Campus Hub - single Flask app (API + website) for Render."""
import io
import os
import re
import time
import uuid

from flask import Flask, jsonify, request, send_file, send_from_directory
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import (Column, Integer, LargeBinary, String, Text, create_engine,
                        select, update, delete)
from sqlalchemy.orm import DeclarativeBase, Session
from werkzeug.security import check_password_hash, generate_password_hash

from classifier import classify

BASE = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, static_folder=None)
app.config["MAX_CONTENT_LENGTH"] = 6 * 1024 * 1024

SECRET = os.environ.get("SECRET_KEY", "dev-only-change-me")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "").strip().lower()
TOKEN_TTL = 7 * 24 * 3600
signer = URLSafeTimedSerializer(SECRET, salt="auth")

db_url = os.environ.get("DATABASE_URL", "sqlite:///campus.db")
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+psycopg2://", 1)
elif db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+psycopg2://", 1)
engine = create_engine(db_url, pool_pre_ping=True)

STATUSES = ["OPEN", "IN_PROGRESS", "RESOLVED", "REJECTED"]
ALLOWED_TYPES = {"image/png", "image/jpeg", "application/pdf"}


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id = Column(String(36), primary_key=True)
    email = Column(String(200), unique=True, nullable=False)
    name = Column(String(120), nullable=False)
    pw_hash = Column(String(300), nullable=False)
    is_admin = Column(Integer, default=0)


class Complaint(Base):
    __tablename__ = "complaints"
    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), index=True, nullable=False)
    user_name = Column(String(120))
    user_email = Column(String(200))
    title = Column(String(120))
    description = Column(Text)
    location = Column(String(120))
    category = Column(String(60))
    priority = Column(String(10))
    sentiment = Column(String(20), default="UNKNOWN")
    status = Column(String(20), default="OPEN", index=True)
    admin_note = Column(String(500), default="")
    handled_by = Column(String(200), default="")
    attachment_id = Column(String(36))
    created_at = Column(Integer)
    updated_at = Column(Integer)


class Notice(Base):
    __tablename__ = "notices"
    id = Column(String(36), primary_key=True)
    title = Column(String(150))
    content = Column(Text)
    audience = Column(String(10))
    posted_by = Column(String(120))
    created_at = Column(Integer, index=True)


class Attachment(Base):
    __tablename__ = "attachments"
    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False)
    content_type = Column(String(50))
    data = Column(LargeBinary)


Base.metadata.create_all(engine)


# ---------------- helpers ----------------
def clean(text, max_len):
    if not isinstance(text, str):
        return ""
    text = re.sub(r"[<>]", "", text)
    text = re.sub(r"[ \t]+", " ", text).strip()
    return text[:max_len]


def err(msg, code=400):
    return jsonify({"message": msg}), code


def user_dict(u):
    return {"id": u.id, "email": u.email, "name": u.name, "isAdmin": bool(u.is_admin)}


def current_user(s):
    auth = request.headers.get("Authorization", "")
    token = auth.removeprefix("Bearer ").strip()
    try:
        uid = signer.loads(token, max_age=TOKEN_TTL)["uid"]
    except (BadSignature, SignatureExpired, KeyError):
        return None
    return s.get(User, uid)


def complaint_dict(c):
    return {
        "complaintId": c.id, "userName": c.user_name, "userEmail": c.user_email,
        "title": c.title, "description": c.description, "location": c.location,
        "category": c.category, "priority": c.priority, "sentiment": c.sentiment,
        "status": c.status, "adminNote": c.admin_note, "createdAt": c.created_at,
        "updatedAt": c.updated_at, "attachmentKey": c.attachment_id,
    }


def authed(admin_only=False):
    """Decorator-free guard: returns (session, user, error_response)."""
    s = Session(engine)
    u = current_user(s)
    if not u:
        s.close()
        return None, None, err("Please sign in", 401)
    if admin_only and not u.is_admin:
        s.close()
        return None, None, err("Admins only", 403)
    return s, u, None


# ---------------- auth ----------------
@app.post("/api/auth/signup")
def signup():
    b = request.get_json(silent=True) or {}
    email = clean(b.get("email"), 200).lower()
    name = clean(b.get("name"), 120)
    pw = b.get("password") or ""
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        return err("Enter a valid e-mail")
    if len(name) < 2:
        return err("Enter your name")
    if len(pw) < 8 or not re.search(r"[a-z]", pw) or not re.search(r"[A-Z]", pw) or not re.search(r"\d", pw):
        return err("Password needs 8+ characters with upper, lower and a number")
    with Session(engine) as s:
        if s.scalar(select(User).where(User.email == email)):
            return err("An account with this e-mail already exists", 409)
        u = User(id=str(uuid.uuid4()), email=email, name=name,
                 pw_hash=generate_password_hash(pw), is_admin=1 if email == ADMIN_EMAIL else 0)
        s.add(u)
        s.commit()
        return jsonify({"token": signer.dumps({"uid": u.id}), "user": user_dict(u)}), 201


@app.post("/api/auth/login")
def login():
    b = request.get_json(silent=True) or {}
    email = clean(b.get("email"), 200).lower()
    with Session(engine) as s:
        u = s.scalar(select(User).where(User.email == email))
        if not u or not check_password_hash(u.pw_hash, b.get("password") or ""):
            return err("Incorrect e-mail or password", 401)
        if email == ADMIN_EMAIL and not u.is_admin:
            u.is_admin = 1
            s.commit()
        return jsonify({"token": signer.dumps({"uid": u.id}), "user": user_dict(u)})


@app.get("/api/me")
def me():
    s, u, e = authed()
    if e:
        return e
    with s:
        return jsonify(user_dict(u))


# ---------------- notices ----------------
@app.get("/api/notices")
def list_notices():
    s, u, e = authed()
    if e:
        return e
    with s:
        rows = s.scalars(select(Notice).order_by(Notice.created_at.desc()).limit(50)).all()
        return jsonify({"items": [{"sk": n.id, "title": n.title, "content": n.content,
                                   "audience": n.audience, "postedBy": n.posted_by,
                                   "createdAt": n.created_at} for n in rows]})


@app.post("/api/notices")
def create_notice():
    s, u, e = authed(admin_only=True)
    if e:
        return e
    with s:
        b = request.get_json(silent=True) or {}
        title, content = clean(b.get("title"), 150), clean(b.get("content"), 3000)
        aud = b.get("audience", "ALL")
        if len(title) < 3 or len(content) < 5:
            return err("Title and content are required")
        if aud not in ("ALL", "STUDENTS", "STAFF"):
            aud = "ALL"
        n = Notice(id=str(uuid.uuid4()), title=title, content=content, audience=aud,
                   posted_by=u.name, created_at=int(time.time()))
        s.add(n)
        s.commit()
        return jsonify({"sk": n.id, "title": title}), 201


@app.delete("/api/notices/<nid>")
def delete_notice(nid):
    s, u, e = authed(admin_only=True)
    if e:
        return e
    with s:
        s.execute(delete(Notice).where(Notice.id == nid))
        s.commit()
        return jsonify({"message": "Deleted"})


# ---------------- uploads ----------------
@app.post("/api/uploads")
def upload():
    s, u, e = authed()
    if e:
        return e
    with s:
        f = request.files.get("file")
        if not f or f.mimetype not in ALLOWED_TYPES:
            return err("Only PNG, JPEG or PDF allowed")
        data = f.read()
        if not data or len(data) > 5 * 1024 * 1024:
            return err("File must be between 1 byte and 5 MB")
        a = Attachment(id=str(uuid.uuid4()), user_id=u.id, content_type=f.mimetype, data=data)
        s.add(a)
        s.commit()
        return jsonify({"key": a.id}), 201


@app.get("/api/attachments/<aid>")
def get_attachment(aid):
    s, u, e = authed()
    if e:
        return e
    with s:
        a = s.get(Attachment, aid)
        owner_ok = a and (a.user_id == u.id or u.is_admin)
        if not owner_ok:
            return err("Not found", 404)
        return send_file(io.BytesIO(a.data), mimetype=a.content_type)


# ---------------- complaints ----------------
@app.post("/api/complaints")
def create_complaint():
    s, u, e = authed()
    if e:
        return e
    with s:
        b = request.get_json(silent=True) or {}
        title = clean(b.get("title"), 120)
        desc = clean(b.get("description"), 2000)
        loc = clean(b.get("location"), 120)
        if len(title) < 3 or len(desc) < 10:
            return err("Title (min 3) and description (min 10 chars) are required")
        att = clean(b.get("attachmentKey"), 36) or None
        if att:
            a = s.get(Attachment, att)
            if not a or a.user_id != u.id:
                return err("Invalid attachment", 403)
        tags = classify(f"{title}. {desc}")
        now = int(time.time())
        c = Complaint(id=str(uuid.uuid4()), user_id=u.id, user_name=u.name, user_email=u.email,
                      title=title, description=desc, location=loc, category=tags["category"],
                      priority=tags["priority"], sentiment=tags["sentiment"], status="OPEN",
                      attachment_id=att, created_at=now, updated_at=now)
        s.add(c)
        s.commit()
        return jsonify(complaint_dict(c)), 201


@app.get("/api/complaints")
def list_complaints():
    s, u, e = authed()
    if e:
        return e
    with s:
        q = select(Complaint).order_by(Complaint.created_at.desc()).limit(100)
        if request.args.get("scope") == "all":
            if not u.is_admin:
                return err("Admins only", 403)
            st = request.args.get("status")
            if st in STATUSES:
                q = q.where(Complaint.status == st)
        else:
            q = q.where(Complaint.user_id == u.id)
        return jsonify({"items": [complaint_dict(c) for c in s.scalars(q).all()]})


@app.get("/api/complaints/<cid>")
def get_complaint(cid):
    s, u, e = authed()
    if e:
        return e
    with s:
        c = s.get(Complaint, cid)
        if not c or (c.user_id != u.id and not u.is_admin):
            return err("Complaint not found", 404)
        return jsonify(complaint_dict(c))


@app.patch("/api/complaints/<cid>")
def update_complaint(cid):
    s, u, e = authed(admin_only=True)
    if e:
        return e
    with s:
        c = s.get(Complaint, cid)
        if not c:
            return err("Complaint not found", 404)
        b = request.get_json(silent=True) or {}
        if b.get("status") not in STATUSES:
            return err(f"status must be one of {STATUSES}")
        c.status = b["status"]
        c.admin_note = clean(b.get("adminNote"), 500)
        c.handled_by = u.email
        c.updated_at = int(time.time())
        s.commit()
        return jsonify({"message": "Updated", "status": c.status})


# ---------------- website ----------------
@app.get("/healthz")
def healthz():
    return "ok"


@app.get("/")
def index():
    return send_from_directory(os.path.join(BASE, "static"), "index.html")


@app.get("/<path:p>")
def static_files(p):
    return send_from_directory(os.path.join(BASE, "static"), p)


if __name__ == "__main__":
    app.run(debug=True, port=int(os.environ.get("PORT", 5000)))
