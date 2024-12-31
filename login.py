import random
import time

import cv2


def random_delay(min_seconds=0.1, max_seconds=0.3):
    time.sleep(random.uniform(min_seconds, max_seconds))


def human_type(element, text):
    for char in text:
        element.type(char)
        random_delay(0.05, 0.15)


def get_slide_distance(bg_img, slide_img):
    """计算滑块移动距离"""
    # 首先使用高斯模糊去噪
    blurred = cv2.GaussianBlur(bg_img, (5, 5), 0, 0)

    # 边缘检测，得到图片轮廓
    canny = cv2.Canny(blurred, 200, 400)

    # 轮廓检测
    contours, hierarchy = cv2.findContours(
        canny, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )

    # 保存调试图片
    cv2.imwrite("debug_canny.png", canny)
    debug_img = bg_img.copy()

    for i, contour in enumerate(contours):
        M = cv2.moments(contour)

        if M["m00"] == 0:
            cx = cy = 0
        else:
            # 计算轮廓的质心
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])

            # 计算轮廓面积和周长
            area = cv2.contourArea(contour)
            perimeter = cv2.arcLength(contour, True)

            print(f"轮廓 {i}: 面积={area}, 周长={perimeter}, 质心=({cx}, {cy})")

            # 根据面积和周长筛选可能的缺口
            if 5000 < area < 8000 and 300 < perimeter < 500:
                if cx < 300:  # 排除左侧的误检
                    continue

                # 画出找到的轮廓（用于调试）
                x, y, w, h = cv2.boundingRect(contour)
                cv2.rectangle(debug_img, (x, y), (x + w, y + h), (0, 0, 255), 2)
                cv2.imwrite("debug_contours.png", debug_img)

                print(f"找到缺口：x={x}, y={y}, w={w}, h={h}")
                return x

    print("未找到符合条件的缺口")
    return 0


def simulate_human_slide(page, slider, distance):
    """模拟人类滑动轨迹"""
    # 生成轨迹
    tracks = []
    current = 0
    mid = distance * 3 / 4
    t = 0.2
    v = 0

    while current < distance:
        if current < mid:
            a = 5  # 增加加速度
        else:
            a = -3  # 保持减速度
        v0 = v
        v = v0 + a * t
        move = v0 * t + 1 / 2 * a * t * t
        current += move
        tracks.append(round(move))

    # 执行滑动
    box = slider.bounding_box()
    # 移动到滑块中心
    start_x = box["x"] + box["width"] / 2
    start_y = box["y"] + box["height"] / 2
    page.mouse.move(start_x, start_y)
    page.mouse.down()

    current_x = start_x
    for track in tracks:
        current_x += track
        page.mouse.move(
            current_x,
            start_y + random.randint(-2, 2),  # 减小垂直抖动
            steps=random.randint(2, 5),
        )
        random_delay(0.005, 0.01)  # 减小延迟，使移动更流畅

    random_delay(0.2, 0.3)
    page.mouse.up()


def handle_slider_captcha(page):
    """处理滑块验证码"""
    try:
        print("\n开始处理验证码...")
        # 等待验证码 iframe 出现
        print("等待验证码 iframe 加载...")
        page.wait_for_selector("#tcaptcha_iframe_dy", timeout=5000)
        print("验证码 iframe 已加载")

        # 切换到验证码 iframe
        iframe = page.frame_locator("#tcaptcha_iframe_dy")
        print("已切换到验证码 iframe")

        # 获取背景图和滑块图
        print("正在获取背景图和滑块图元素...")
        bg_img = iframe.locator(".tc-bg-img")
        slide_img = iframe.locator(
            '.tc-fg-item[style*="width: 60.7143px"][style*="height: 60.7143px"]'
        )
        print("已找到图片元素")

        # 下载图片
        print("正在提取图片样式...")
        bg_style = bg_img.get_attribute("style")
        slide_style = slide_img.get_attribute("style")
        print(f"背景图样式: {bg_style}")
        print(f"滑块图样式: {slide_style}")

        # 从 style 中提取图片 URL
        print("正在解析图片 URL...")
        bg_url = bg_style.split('url("')[1].split('")')[0]
        slide_url = slide_style.split('url("')[1].split('")')[0]
        print(f"背景图 URL: {bg_url}")
        print(f"滑块图 URL: {slide_url}")

        # 下载图片
        import requests

        print("正在下载图片...")
        bg_content = requests.get(bg_url).content
        slide_content = requests.get(slide_url).content
        print("图片下载完成")

        # 保存图片
        print("正在保存图片到本地...")
        with open("bg.png", "wb") as f:
            f.write(bg_content)
        with open("slide.png", "wb") as f:
            f.write(slide_content)
        print("图片已保存到本地")

        # 读取图片
        bg = cv2.imread("bg.png")
        slide = cv2.imread("slide.png")
        if bg is None:
            raise Exception("背景图读取失败")
        if slide is None:
            raise Exception("滑块图读取失败")
        print(f"背景图尺寸: {bg.shape}")
        print(f"滑块图尺寸: {slide.shape}")

        # 计算滑动距离
        print("正在计算滑动距离...")
        distance = get_slide_distance(bg, slide)  # 传入两张图片
        if distance == 0:
            print("警告：未找到缺口，使用固定距离")
            distance = 200
        print(f"计算得到的滑动距离: {distance}像素")

        # 获取滑块元素并滑动
        print("正在获取滑块元素...")
        slider = iframe.locator(".tc-slider-normal")
        box = slider.bounding_box()
        print(f"滑块位置信息: {box}")

        # 调整实际滑动距离
        real_distance = int(distance * 0.41)  # 浏览器中图片像素约为实际图片的41%
        print(f"调整后的滑动距离: {real_distance}像素")

        print("开始模拟滑动...")
        simulate_human_slide(page, slider, real_distance)
        print("滑动完成")

        # 等待验证结果
        random_delay(1, 2)
        print("验证码处理完成")

        # 清理下载的图片
        import os

        print("正在清理临时文件...")
        files_to_delete = [
            "bg.png",
            "slide.png",
            "debug_canny.png",
            "debug_contours.png",
            "debug_bg_edges.png",
            "debug_slide_edges.png",
        ]
        for file in files_to_delete:
            try:
                if os.path.exists(file):
                    os.remove(file)
            except Exception as e:
                print(f"删除文件 {file} 失败: {str(e)}")
        print("临时文件清理完成")

        return True

    except Exception as e:
        print("\n验证码处理失败!")
        print(f"错误类型: {type(e).__name__}")
        print(f"错误信息: {str(e)}")
        print("错误位置: ", end="")
        import traceback

        traceback.print_exc()

        # 即使失败也清理文件
        try:
            import os

            files_to_delete = [
                "bg.png",
                "slide.png",
                "debug_canny.png",
                "debug_contours.png",
                "debug_bg_edges.png",
                "debug_slide_edges.png",
            ]
            for file in files_to_delete:
                if os.path.exists(file):
                    os.remove(file)
        except:
            pass

        return False


def login_douban(page, username, password):
    # 访问登录页面
    page.goto("https://accounts.douban.com/passport/login")
    random_delay(1, 2)

    # 切换到密码登录
    page.locator("li.account-tab-account").click()
    random_delay(0.5, 1)

    # 输入账号密码
    username_input = page.locator('input[name="username"]')
    password_input = page.locator('input[name="password"]')

    human_type(username_input, username)
    random_delay(0.3, 0.8)
    human_type(password_input, password)
    random_delay(0.5, 1)

    # 点击登录按钮
    login_button = page.locator("a.btn.btn-account.btn-active")
    login_button.click()

    # 处理可能出现的验证码
    if handle_slider_captcha(page):
        print("验证码处理完成")

    # 等待登录完成
    random_delay(3, 5)

    # 检查是否登录成功
    try:
        # 等待重定向完成，最多等待10秒
        page.wait_for_url("**/www.douban.com/**", timeout=10000)
        print("登录成功!")
        return page
    except Exception:
        print("登录可能失败，请检查")
        print(f"当前URL: {page.url}")
        return None


if __name__ == "__main__":
    username = ""
    password = ""
    login_douban(username, password)
