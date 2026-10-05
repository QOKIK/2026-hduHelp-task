from playwright.sync_api import expect, sync_playwright
from time import time_ns


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
        author_context = browser.new_context()
        author = author_context.new_page()
        author.goto("http://127.0.0.1:5174")
        author.wait_for_load_state("networkidle")
        register(author, "e2efinder" + suffix, "拾获同学", "2399" + suffix)
        author.get_by_role("button", name="发布一条信息").click()
        author.get_by_role("button", name="我捡到了").click()
        author.get_by_label("物品名称").fill("银色校园卡")
        author.get_by_label("描述").fill("卡套背面贴有一枚绿色小叶子贴纸。")
        author.get_by_label("物品类别").fill("校园卡")
        author.get_by_label("大概地点").fill("图书馆一楼")
        author.get_by_role("button", name="提交管理员审核").click()
        expect(author.get_by_text("已提交审核，通过后会出现在广场。", exact=True)).to_be_visible()

        admin = browser.new_page()
        admin.goto("http://127.0.0.1:5174")
        admin.wait_for_load_state("networkidle")
        admin.get_by_role("button", name="登录 / 注册").click()
        admin.get_by_label("用户名").fill("moderator")
        admin.get_by_label("密码").fill("e2e-moderator-password")
        admin.locator(".account-dialog form button").click()
        admin.get_by_role("button", name="管理工作台").click()
        admin.get_by_role("button", name="通过", exact=True).first.click()
        expect(admin.get_by_text("内容已审核通过。", exact=True)).to_be_visible()

        claimant = browser.new_page()
        claimant.goto("http://127.0.0.1:5174")
        claimant.wait_for_load_state("networkidle")
        claimant.reload()
        claimant.locator(".post-card").filter(has_text="银色校园卡").click()
        register(claimant, "e2eowner" + suffix, "认领同学", "2388" + suffix)
        claimant.get_by_label("说说情况").fill("这张卡的卡套确实贴有绿色小叶子。")
        claimant.get_by_label("方便联系你的方式").fill("邮箱 owner@example.test")
        claimant.get_by_role("button", name="提交认领").click()
        expect(claimant.get_by_text("已私密发送给发布者。", exact=True)).to_be_visible()

        author.get_by_role("button", name="我的发布").click()
        author.locator(".own-title", has_text="银色校园卡").click()
        expect(author.get_by_text("收到的申请")).to_be_visible()
        author.get_by_role("button", name="接受申请").click()
        expect(author.locator(".aside-status").get_by_text("已归还")).to_be_visible()
        expect(author.get_by_text("已接受，相关内容状态已更新。", exact=True)).to_be_visible()
        print("浏览器流程通过：发布 → 审核 → 私密认领 → 接受并更新状态")
        browser.close()


if __name__ == "__main__":
    main()
