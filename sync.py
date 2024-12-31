import json
import random
import time
from typing import List

import requests
from playwright.sync_api import sync_playwright


class TraktDoubanSync:
    def __init__(self, trakt_username: str, trakt_api_key: str):
        self.trakt_username = trakt_username
        self.trakt_api_key = trakt_api_key
        self.headers = {"trakt-api-version": "2", "trakt-api-key": trakt_api_key}

    def get_watched_shows(self) -> List[str]:
        """获取已观看的剧集的IMDB IDs"""
        url = f"https://api.trakt.tv/users/{self.trakt_username}/watched/shows"
        response = requests.get(url, headers=self.headers)
        if response.status_code != 200:
            raise Exception(f"获取观看记录失败: {response.status_code}")

        shows = response.json()
        imdb_ids = []
        for show in shows:
            imdb_id = show.get("show", {}).get("ids", {}).get("imdb")
            if imdb_id:
                imdb_ids.append(imdb_id)

        return imdb_ids

    def mark_as_watched(self, page, douban_url: str):
        """在豆瓣上标记为看过"""
        # 进入详情页
        page.goto(douban_url)
        time.sleep(random.uniform(1, 2))

        # 点击"看过"按钮
        collect_btn = page.locator('a.collect_btn[name^="pbtn-"][class*="colbutt"]')
        collect_btn.click()
        time.sleep(random.uniform(1, 2))

        # 点击"保存"按钮
        save_btn = page.locator('input[type="submit"][value="保存"][name="save"]')
        save_btn.click()
        time.sleep(random.uniform(1, 2))

    def sync_to_douban(self, page):
        """同步到豆瓣"""
        imdb_ids = self.get_watched_shows()
        print(f"获取到 {len(imdb_ids)} 个节目")

        for imdb_id in imdb_ids:
            try:
                print(f"\n处理 IMDB ID: {imdb_id}")
                # 搜索页面
                search_url = f"https://www.douban.com/search?source=suggest&q={imdb_id}"
                page.goto(search_url)
                page.wait_for_load_state("domcontentloaded")
                page.wait_for_selector("div.result", timeout=30000)
                time.sleep(random.uniform(1, 2))

                # 获取搜索结果中的第一个链接
                result = page.locator(".DouWeb-SR-subject-info-name").first
                if not result:
                    print(f"未找到匹配的内容: {imdb_id}")
                    continue

                # 获取详情页URL
                href = result.get_attribute("href")
                if not href:
                    print(f"未找到详情页链接: {imdb_id}")
                    continue

                # 标记为看过
                self.mark_as_watched(page, href)
                print(f"已标记为看过: {imdb_id}")

            except Exception as e:
                print(f"处理 {imdb_id} 时出错: {str(e)}")
                continue


def main():
    # 从配置文件加载参数
    with open("config.json", "r") as f:
        config = json.load(f)

    syncer = TraktDoubanSync(
        trakt_username=config["trakt_username"], trakt_api_key=config["trakt_api_key"]
    )

    with sync_playwright() as p:
        # 使用已登录的浏览器上下文
        browser = p.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--start-maximized",
            ],
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        )
        page = context.new_page()

        # 添加自定义脚本以避免被检测
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

        # 先登录豆瓣
        from login import login_douban

        if not login_douban(page, config["douban_username"], config["douban_password"]):
            print("登录失败，退出程序")
            browser.close()
            return

        # 开始同步
        syncer.sync_to_douban(page)

        browser.close()


if __name__ == "__main__":
    main()
