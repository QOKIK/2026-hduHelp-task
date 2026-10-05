from fastapi.testclient import TestClient

from app.main import create_app


def test_new_post_stays_private_until_admin_approves(tmp_path):
    app = create_app(tmp_path / "test.db", admin_username="moderator", admin_password="safe-review-password")
    with TestClient(app) as client:
        registered = client.post(
            "/api/auth/register",
            json={
                "username": "lin",
                "password": "a-long-password",
                "nickname": "小林",
                "student_number": "23010001",
            },
        )
        assert registered.status_code == 201
        post = client.post(
            "/api/posts",
            json={
                "kind": "lost",
                "item_name": "蓝色水杯",
                "description": "图书馆三楼可能遗失",
                "category": "水杯",
                "location": "图书馆",
            },
        )
        assert post.status_code == 201
        assert post.json()["moderation_status"] == "待审核"
        assert client.get("/api/posts").json()["items"] == []

        login = client.post(
            "/api/auth/login", json={"username": "moderator", "password": "safe-review-password"}
        )
        assert login.status_code == 200
        review_queue = client.get("/api/admin/reviews").json()
        assert review_queue["posts"][0]["author_student_number"] == "23010001"
        reviewed = client.post(f"/api/admin/reviews/{post.json()['id']}/approve")
        assert reviewed.status_code == 200

        public = client.get("/api/posts").json()["items"]
        assert len(public) == 1
        assert public[0]["item_name"] == "蓝色水杯"
        assert "student_number" not in public[0]
