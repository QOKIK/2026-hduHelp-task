from fastapi.testclient import TestClient

from app.main import create_app


def account(client: TestClient, username: str, student_number: str):
    response = client.post(
        "/api/auth/register",
        json={
            "username": username,
            "password": "a-long-password",
            "nickname": username.title(),
            "student_number": student_number,
        },
    )
    assert response.status_code == 201
    return response.json()


def create_post(client: TestClient, kind: str, item_name: str):
    response = client.post(
        "/api/posts",
        json={
            "kind": kind,
            "item_name": item_name,
            "description": "物品颜色和发现位置等补充说明",
            "location": "图书馆",
        },
    )
    assert response.status_code == 201
    return response.json()


def login_admin(client: TestClient):
    response = client.post(
        "/api/auth/login", json={"username": "moderator", "password": "safe-review-password"}
    )
    assert response.status_code == 200


def test_revision_keeps_approved_version_until_review_and_rejection_keeps_it(tmp_path):
    app = create_app(tmp_path / "revision.db", "moderator", "safe-review-password")
    with TestClient(app) as author, TestClient(app) as moderator:
        account(author, "lin", "23010001")
        post = create_post(author, "lost", "黑色耳机盒")
        login_admin(moderator)
        assert moderator.post(f"/api/admin/reviews/{post['id']}/approve").status_code == 200

        author.put(
            f"/api/posts/{post['id']}",
            json={"kind": "lost", "item_name": "黑色耳机盒（已补充贴纸特征）", "description": "黑色耳机盒，外面贴有白色小花贴纸。"},
        )
        public_before = author.get(f"/api/posts/{post['id']}").json()
        assert public_before["item_name"] == "黑色耳机盒"
        assert author.get("/api/my/posts").json()[0]["pending_revision"]["item_name"] == "黑色耳机盒（已补充贴纸特征）"

        assert moderator.post(
            f"/api/admin/reviews/{post['id']}/reject", json={"reason": "请移除个人联系方式后再发布"}
        ).status_code == 200
        public_after = author.get(f"/api/posts/{post['id']}").json()
        own_after = author.get("/api/my/posts").json()[0]
        assert public_after["item_name"] == "黑色耳机盒"
        assert own_after["pending_revision"] is None
        assert own_after["latest_revision"]["rejection_reason"] == "请移除个人联系方式后再发布"
        resubmitted = author.put(
            f"/api/posts/{post['id']}",
            json={"kind": "lost", "item_name": "黑色耳机盒（已修正）", "description": "黑色耳机盒，外壳有白色贴纸。"},
        )
        assert resubmitted.json()["pending_revision"]["item_name"] == "黑色耳机盒（已修正）"
        assert author.get(f"/api/posts/{post['id']}").json()["item_name"] == "黑色耳机盒"


def test_request_details_are_private_until_a_participant_reports_them(tmp_path):
    app = create_app(tmp_path / "privacy.db", "moderator", "safe-review-password")
    with TestClient(app) as finder, TestClient(app) as owner, TestClient(app) as stranger, TestClient(app) as moderator:
        account(finder, "finder", "23010001")
        account(owner, "owner", "23010002")
        account(stranger, "stranger", "23010003")
        post = create_post(finder, "found", "银色校园卡")
        login_admin(moderator)
        moderator.post(f"/api/admin/reviews/{post['id']}/approve")

        claim = owner.post(
            f"/api/posts/{post['id']}/requests",
            json={"explanation": "卡片上有我的名字，我可以描述卡套颜色。", "contact_method": "微信 owner_private"},
        ).json()
        assert stranger.get(f"/api/requests/{claim['id']}").status_code == 403
        assert stranger.get(f"/api/posts/{post['id']}/requests").status_code == 403
        author_view = finder.get(f"/api/posts/{post['id']}/requests").json()
        assert author_view[0]["contact_method"] == "微信 owner_private"
        assert moderator.get("/api/admin/reports").json() == []
        assert moderator.get("/api/admin/reviews").json()["posts"] == []

        assert owner.post(f"/api/requests/{claim['id']}/reports", json={"explanation": "请求里出现不合规内容，请核查。"}).status_code == 201
        report = moderator.get("/api/admin/reports").json()[0]
        assert report["target"]["contact_method"] == "微信 owner_private"
        assert "student_number" not in report["target"]
        assert moderator.post(
            f"/api/admin/reports/{report['id']}/remove", json={"reason": "经核查确认违规，移除相关请求。"}
        ).status_code == 200
        assert owner.get(f"/api/requests/{claim['id']}").status_code == 404
        retained = moderator.get("/api/admin/reports").json()[0]
        assert retained["target"]["contact_method"] == "微信 owner_private"


def test_accepting_one_claim_resolves_post_and_closes_other_pending_requests(tmp_path):
    app = create_app(tmp_path / "accept.db", "moderator", "safe-review-password")
    with TestClient(app) as finder, TestClient(app) as first_owner, TestClient(app) as second_owner, TestClient(app) as moderator:
        account(finder, "finder", "23010001")
        account(first_owner, "ownerone", "23010002")
        account(second_owner, "ownertwo", "23010003")
        post = create_post(finder, "found", "绿色水壶")
        login_admin(moderator)
        moderator.post(f"/api/admin/reviews/{post['id']}/approve")
        first = first_owner.post(
            f"/api/posts/{post['id']}/requests", json={"explanation": "我可以说出壶身的刮痕。", "contact_method": "mail one@example.com"}
        ).json()
        second = second_owner.post(
            f"/api/posts/{post['id']}/requests", json={"explanation": "这个水壶是我的，底部有姓名贴。", "contact_method": "mail two@example.com"}
        ).json()

        accepted = finder.post(f"/api/requests/{first['id']}/accept")
        assert accepted.status_code == 200
        assert finder.get(f"/api/posts/{post['id']}").json()["lifecycle_status"] == "已归还"
        assert second_owner.get(f"/api/requests/{second['id']}").json()["status"] == "已拒绝"


def test_regular_user_cannot_review_content_and_pagination_search_are_public(tmp_path):
    app = create_app(tmp_path / "permissions.db", "moderator", "safe-review-password")
    with TestClient(app) as author, TestClient(app) as visitor, TestClient(app) as moderator:
        profile = account(author, "lin", "23010001")
        first = create_post(author, "lost", "蓝色水杯")
        second = create_post(author, "found", "黑色雨伞")
        assert profile["student_number_verified"] is False
        assert author.post(f"/api/admin/reviews/{first['id']}/approve").status_code == 403
        login_admin(moderator)
        moderator.post(f"/api/admin/reviews/{first['id']}/approve")
        moderator.post(f"/api/admin/reviews/{second['id']}/approve")
        result = visitor.get("/api/posts?q=水杯&limit=1").json()
        assert result["total"] == 1
        assert result["items"][0]["item_name"] == "蓝色水杯"
        assert "student_number" not in result["items"][0]


def test_terminal_post_state_cannot_be_reopened(tmp_path):
    app = create_app(tmp_path / "terminal.db", "moderator", "safe-review-password")
    with TestClient(app) as author:
        account(author, "lin", "23010001")
        post = create_post(author, "lost", "红色笔记本")
        assert author.post(f"/api/posts/{post['id']}/status", json={"status": "已找回"}).status_code == 200
        reopened = author.post(f"/api/posts/{post['id']}/status", json={"status": "寻找中"})
        assert reopened.status_code == 409
        assert author.get("/api/my/posts").json()[0]["lifecycle_status"] == "已找回"


def test_post_with_handling_history_is_withdrawn_and_retained(tmp_path):
    app = create_app(tmp_path / "withdraw.db", "moderator", "safe-review-password")
    with TestClient(app) as author, TestClient(app) as visitor:
        account(author, "lin", "23010001")
        post = create_post(author, "lost", "紫色文件夹")
        account(visitor, "reader", "23010002")
        login_admin(visitor)
        visitor.post(f"/api/admin/reviews/{post['id']}/approve")
        assert visitor.get(f"/api/posts/{post['id']}").status_code == 200
        assert visitor.post(
            f"/api/posts/{post['id']}/reports", json={"explanation": "用于验证有关联记录时保留处理历史。"}
        ).status_code == 201

        result = author.delete(f"/api/posts/{post['id']}")
        assert result.json() == {"ok": True, "withdrawn": True}
        assert visitor.get(f"/api/posts/{post['id']}").status_code == 404
        retained = author.get("/api/my/posts").json()
        assert retained[0]["item_name"] == "紫色文件夹"
        assert retained[0]["withdrawn"] is True


def test_administrator_can_take_down_approved_public_post_with_a_reason(tmp_path):
    app = create_app(tmp_path / "takedown.db", "moderator", "safe-review-password")
    with TestClient(app) as author, TestClient(app) as moderator, TestClient(app) as visitor:
        account(author, "lin", "23010001")
        post = create_post(author, "found", "黑色折叠伞")
        assert author.post(
            f"/api/admin/posts/{post['id']}/take-down", json={"reason": "理由必须由管理员填写"}
        ).status_code == 403

        login_admin(moderator)
        moderator.post(f"/api/admin/reviews/{post['id']}/approve")
        removed = moderator.post(
            f"/api/admin/posts/{post['id']}/take-down", json={"reason": "失主确认物品并要求撤下"}
        )
        assert removed.status_code == 200
        assert visitor.get("/api/posts").json()["total"] == 0
        assert visitor.get(f"/api/posts/{post['id']}").status_code == 404
        assert author.get("/api/my/posts").json()[0]["withdrawn"] is True
