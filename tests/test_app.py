import io, os, sys
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["ADMIN_EMAIL"] = "admin@college.edu"
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import app as m
from sqlalchemy.pool import StaticPool
from sqlalchemy import create_engine
m.engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
m.Base.metadata.create_all(m.engine)
c = m.app.test_client()

def signup(email, name="Test User"):
    r = c.post("/api/auth/signup", json={"email": email, "name": name, "password": "Passw0rdX"})
    assert r.status_code == 201, r.json
    return {"Authorization": "Bearer " + r.json["token"]}

def test_flow():
    stu = signup("stu@college.edu"); adm = signup("admin@college.edu", "Admin")
    assert c.get("/").status_code == 200
    assert c.get("/api/complaints").status_code == 401
    up = c.post("/api/uploads", headers=stu, data={"file": (io.BytesIO(b"\x89PNG"), "a.png", "image/png")}, content_type="multipart/form-data")
    assert up.status_code == 201
    r = c.post("/api/complaints", headers=stu, json={"title": "Sparking socket", "description": "Sparking socket near Lab 3, danger of fire", "attachmentKey": up.json["key"]})
    assert r.status_code == 201 and r.json["priority"] == "HIGH" and r.json["category"] == "Electricity"
    cid = r.json["complaintId"]
    assert c.get("/api/complaints?scope=all", headers=stu).status_code == 403
    assert len(c.get("/api/complaints?scope=all", headers=adm).json["items"]) == 1
    assert c.patch(f"/api/complaints/{cid}", headers=stu, json={"status": "RESOLVED"}).status_code == 403
    assert c.patch(f"/api/complaints/{cid}", headers=adm, json={"status": "RESOLVED", "adminNote": "fixed"}).status_code == 200
    assert c.get("/api/complaints", headers=stu).json["items"][0]["status"] == "RESOLVED"
    assert c.get(f"/api/attachments/{up.json['key']}", headers=adm).status_code == 200
    assert c.post("/api/notices", headers=stu, json={"title": "Hello", "content": "World!!"}).status_code == 403
    assert c.post("/api/notices", headers=adm, json={"title": "Hello", "content": "World!!"}).status_code == 201
    assert len(c.get("/api/notices", headers=stu).json["items"]) == 1
    assert c.post("/api/auth/login", json={"email": "stu@college.edu", "password": "bad"}).status_code == 401
