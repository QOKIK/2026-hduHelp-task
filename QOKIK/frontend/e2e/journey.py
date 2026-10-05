from playwright.sync_api import expect, sync_playwright
from time import time_ns
import os


def register(page, username, nickname, student_number):
    page.get_by_role("button", name="登录 / 注册").click()
    page.get_by_role("button", name="还没有账号？创建一个").click()
    page.get_by_label("用户名").fill(username)
    page.get_by_label("密码").fill("local-demo-password")
    page.get_by_label("称呼").fill(nickname)
    page.get_by_label("学号").fill(student_number)
    page.get_by_role("button", name="创建账号").click()
    expect(page.locator(".account-actions .user-name")).to_have_text(nickname)


def main():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        suffix = str(time_ns())[-7:]
        silver_item = "银色校园卡-" + suffix
        notebook_item = "绿色笔记本-" + suffix
        author_context = browser.new_context()
        author = author_context.new_page()
        author.goto("http://127.0.0.1:5174")
        author.wait_for_load_state("networkidle")
        register(author, "e2efinder" + suffix, "拾获同学", "2399" + suffix)
        author.get_by_role("button", name="发布一条信息").click()
        author.get_by_role("button", name="我捡到了").click()
        author.get_by_label("物品名称").fill(silver_item)
        author.get_by_label("描述").fill("卡套背面贴有一枚绿色小叶子贴纸。")
        author.get_by_label("物品类别").fill("校园卡")
        author.get_by_label("大概地点").fill("图书馆一楼")
        author.get_by_role("button", name="提交管理员审核").click()
        expect(author.get_by_text("已提交审核，通过后会出现在广场。", exact=True)).to_be_visible()

        admin = browser.new_page()
        admin.goto("http://127.0.0.1:5174")
        admin.wait_for_load_state("networkidle")
        admin.get_by_role("button", name="登录 / 注册").click()
        admin.get_by_label("用户名").fill(os.environ.get("HDUHELP_E2E_ADMIN_USERNAME", "moderator"))
        admin.get_by_label("密码").fill(os.environ["HDUHELP_E2E_ADMIN_PASSWORD"])
        admin.locator(".account-dialog form button").click()
        expect(admin.locator(".account-actions .user-name")).to_have_text("系统管理员")
        admin.reload()
        admin.wait_for_load_state("networkidle")
        expect(admin.get_by_role("button", name="管理工作台")).to_be_visible()
        admin.get_by_role("button", name="管理工作台").click()
        admin.locator(".moderation-card").filter(has_text=silver_item).get_by_role("button", name="通过", exact=True).click()
        expect(admin.get_by_text("内容已审核通过。", exact=True)).to_be_visible()

        claimant = browser.new_page()
        claimant.goto("http://127.0.0.1:5174")
        claimant.wait_for_load_state("networkidle")
        claimant.reload()
        claimant.locator(".post-card").filter(has_text=silver_item).first.click()
        register(claimant, "e2eowner" + suffix, "认领同学", "2388" + suffix)
        claimant.get_by_label("说说情况").fill("这张卡的卡套确实贴有绿色小叶子。")
        claimant.get_by_label("方便联系你的方式").fill("邮箱 owner@example.test")
        claimant.get_by_role("button", name="提交认领").click()
        expect(claimant.get_by_text("已私密发送给发布者。", exact=True)).to_be_visible()

        author.get_by_role("button", name="我的发布").click()
        author.locator(".own-title", has_text=silver_item).click()
        expect(author.get_by_text("收到的申请")).to_be_visible()
        author.get_by_role("button", name="接受申请").click()
        expect(author.locator(".aside-status").get_by_text("已归还")).to_be_visible()
        expect(author.get_by_text("已接受，相关内容状态已更新。", exact=True)).to_be_visible()

        claimant.get_by_role("button", name="我的发布").click()
        claimant.get_by_role("button", name="发布新信息").click()
        claimant.get_by_role("button", name="我丢失了").click()
        claimant.get_by_label("物品名称").fill(notebook_item)
        claimant.get_by_label("描述").fill("封面有一条白色横线，内页写着课程笔记。")
        claimant.get_by_label("大概地点").fill("教学楼 C 区")
        claimant.get_by_role("button", name="提交管理员审核").click()
        expect(claimant.get_by_text("已提交审核，通过后会出现在广场。", exact=True)).to_be_visible()

        admin.get_by_role("button", name="失物广场").click()
        admin.get_by_role("button", name="管理工作台").click()
        admin.locator(".moderation-card").filter(has_text=notebook_item).get_by_role("button", name="通过", exact=True).click()
        expect(admin.get_by_text("内容已审核通过。", exact=True)).to_be_visible()

        author.get_by_role("button", name="失物广场").click()
        author.locator(".post-card").filter(has_text=notebook_item).click()
        author.get_by_label("说说情况").fill("我在教学楼 C 区看见一本封面有白色横线的笔记本。")
        author.get_by_label("方便联系你的方式").fill("邮箱 finder@example.test")
        author.get_by_role("button", name="发送线索").click()
        expect(author.get_by_text("已私密发送给发布者。", exact=True)).to_be_visible()
        author.get_by_role("button", name="举报此内容").click()
        author.get_by_label("情况说明").fill("请管理员核查这条公开信息。")
        author.get_by_role("button", name="提交举报").click()
        expect(author.get_by_text("举报已提交，管理员会按流程处理。", exact=True)).to_be_visible()

        claimant.get_by_role("button", name="我的发布").click()
        claimant.locator(".own-title", has_text=notebook_item).click()
        expect(claimant.get_by_text("收到的申请")).to_be_visible()
        claimant.get_by_role("button", name="接受申请").click()
        expect(claimant.locator(".aside-status").get_by_text("已找回")).to_be_visible()

        admin.get_by_role("button", name="失物广场").click()
        admin.get_by_role("button", name="管理工作台").click()
        admin.locator(".report-card").filter(has_text="请管理员核查这条公开信息").get_by_role("button", name="驳回举报").click()
        expect(admin.locator(".report-card").get_by_text("已驳回")).to_be_visible()
        print("浏览器流程通过：注册 → 发布/审核 → 认领与线索 → 接受结案 → 举报处理")
        browser.close()


if __name__ == "__main__":
    main()
