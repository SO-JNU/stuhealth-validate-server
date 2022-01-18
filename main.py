import io
import json
import os
import random
import requests
import struct
import sys
import threading
import typing
from PIL import Image
from PIL import ImageChops
from http.server import BaseHTTPRequestHandler
from http.server import ThreadingHTTPServer
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import TimeoutException
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

# 获取图片的dhash
def getImageHash(img: Image) -> bytes:
    img = img.convert('L').resize((17, 16), Image.LANCZOS)
    imgBytes = img.tobytes()
    imgHash = [0 for _ in range(16)]
    for i in range(16):
        for j in range(16):
            if imgBytes[(i << 4) + j] < imgBytes[(i << 4) + j + 1]:
                imgHash[i] |= 1 << j
    return struct.pack('<HHHHHHHHHHHHHHHH', *imgHash)

# 计算两个dhash之间的汉明距离，范围是0-256，越低则图片越相似
# 使用了查表法
def getImageHashDiff(hashA: bytes, hashB: bytes) -> int:
    diff = 0
    for a, b in zip(hashA, hashB):
        diff += (
            0, 1, 1, 2, 1, 2, 2, 3, 1, 2, 2, 3, 2, 3, 3, 4,
            1, 2, 2, 3, 2, 3, 3, 4, 2, 3, 3, 4, 3, 4, 4, 5,
            1, 2, 2, 3, 2, 3, 3, 4, 2, 3, 3, 4, 3, 4, 4, 5,
            2, 3, 3, 4, 3, 4, 4, 5, 3, 4, 4, 5, 4, 5, 5, 6,
            1, 2, 2, 3, 2, 3, 3, 4, 2, 3, 3, 4, 3, 4, 4, 5,
            2, 3, 3, 4, 3, 4, 4, 5, 3, 4, 4, 5, 4, 5, 5, 6,
            2, 3, 3, 4, 3, 4, 4, 5, 3, 4, 4, 5, 4, 5, 5, 6,
            3, 4, 4, 5, 4, 5, 5, 6, 4, 5, 5, 6, 5, 6, 6, 7,
            1, 2, 2, 3, 2, 3, 3, 4, 2, 3, 3, 4, 3, 4, 4, 5,
            2, 3, 3, 4, 3, 4, 4, 5, 3, 4, 4, 5, 4, 5, 5, 6,
            2, 3, 3, 4, 3, 4, 4, 5, 3, 4, 4, 5, 4, 5, 5, 6,
            3, 4, 4, 5, 4, 5, 5, 6, 4, 5, 5, 6, 5, 6, 6, 7,
            2, 3, 3, 4, 3, 4, 4, 5, 3, 4, 4, 5, 4, 5, 5, 6,
            3, 4, 4, 5, 4, 5, 5, 6, 4, 5, 5, 6, 5, 6, 6, 7,
            3, 4, 4, 5, 4, 5, 5, 6, 4, 5, 5, 6, 5, 6, 6, 7,
            4, 5, 5, 6, 5, 6, 6, 7, 5, 6, 6, 7, 6, 7, 7, 8,
        )[a ^ b]
        # xored = a ^ b
        # while xored:
        #     diff += 1
        #     xored &= xored - 1
    return diff

# 计算多项式，每一项是pn * (x ** n)
def polynomialCalc(x: float, params: tuple[float]) -> float:
    return sum(p * (x ** n) for n, p in enumerate(params))

def untilFindElement(by: By, value: str) -> typing.Callable[[webdriver.Firefox], bool]:
    def func(d: webdriver.Firefox) -> bool:
        try:
            d.find_element(by, value)
            return True
        except NoSuchElementException:
            return False
    return func

# 一些全局变量
imgBackgroundWithHash = tuple((i, getImageHash(i)) for i in (Image.open(f'bgimg/{j}') for j in os.listdir('bgimg')))
lock = threading.Lock()
token: str = None
browser: webdriver.Firefox = None

# 获取验证码的validate token
def getValidateToken() -> typing.Optional[str]:
    # 触发验证码组件初始化
    # (document.querySelector('#captcha .yidun .yidun_bg-img[src^="https://"]') || {}).src = null;
    # window.initNECaptcha({
    #     element: "#captcha",
    #     captchaId: "7d856ac2068b41a1b8525f3fffe92d1c",
    #     width: "320px",
    #     mode: "float",
    # });
    browser.execute_script('(document.querySelector(\'#captcha .yidun .yidun_bg-img[src^="https://"]\')||{}).src=null;window.initNECaptcha({element:"#captcha",captchaId:"7d856ac2068b41a1b8525f3fffe92d1c",width:"320px",mode:"float"})')
    WebDriverWait(browser, 3).until(untilFindElement(By.CSS_SELECTOR, '#captcha .yidun .yidun_bg-img[src^="https://"]'))
    domYidunImg = browser.find_element(By.CSS_SELECTOR, '#captcha .yidun .yidun_bg-img')
    domYidunSlider = browser.find_element(By.CSS_SELECTOR, '#captcha .yidun .yidun_slider')
    domValidate = browser.find_element(By.CSS_SELECTOR, '#captcha input.yidun_input[name="NECaptchaValidate"]')

    # 重试3次
    for i in range(3):
        # 获取滑动验证码图片
        img = Image.open(io.BytesIO(requests.get(domYidunImg.get_attribute('src').replace('@2x', '').replace('@3x', '')).content))
        # print(domYidunImg.get_attribute('src'))
        imgHash = getImageHash(img)
        imgBackground = min(imgBackgroundWithHash, key=lambda i: getImageHashDiff(imgHash, i[1]))[0]

        # 获取滑动位置
        imgDiff = ImageChops.difference(img, imgBackground).convert('L')
        imgDiffBytes = imgDiff.tobytes()
        targetPosX = 0
        targetPixelCount = 0
        for x in range(imgDiff.width):
            for y in range(imgDiff.height):
                if imgDiffBytes[y * imgDiff.width + x] >= 16:
                    targetPosX += x
                    targetPixelCount += 1
        targetPosX = round(targetPosX / targetPixelCount) - 22
        # print(targetPosX)
        # for y in range(imgDiff.height):
        #     imgDiff.putpixel((targetPosX, y), 0xFFFFFF)
        # imgDiff.save('diff.png')
        targetPosX = targetPosX / 260 * 270

        # 模拟拖拽，时间单位为1/50s也就是20ms，根据滑动距离一共是500-800+-100ms
        # 另外鼠标放到滑块上等待400-700ms，松开再等待100-200ms
        # 拟合拖拽轨迹的多项式定义域和值域均为[0, 1]，且f(0)=0 f(1)=1
        polynomial = random.choice((
            (0, 7.27419, -23.0881, 40.86, -40.2374, 20.1132, -3.922),
            (0, 11.2642, -54.1671, 135.817, -180.721, 119.879, -31.0721),
            (0, 7.77852, -37.3727, 103.78, -155.152, 115.664, -33.6981),
            (0, 12.603, -61.815, 159.706, -227.619, 166.648, -48.5237),
            (0, 9.94916, -35.3439, 57.2436, -43.3425, 12.4937),
            (0, 8.88576, -29.9556, 49.0498, -39.2717, 12.2918),
            (0, 8.7663, -28.3669, 42.9499, -30.9548, 8.60551),
            (0, 7.36696, -20.605, 27.705, -18.1929, 4.72597),
            (0, -.360233, 15.4068, -36.168, 32.64, -10.5186),
            (0, -.260426, 10.5665, -17.711, 9.70626, -1.30134),
            (0, -.00431368, .131857, 15.3877, -26.4217, 11.9064),
            (0, -.607056, 19.5733, -56.8777, 62.7801, -23.8686),
            (0, 5.84619, -14.9367, 19.8566, -13.293, 3.52692),
        ))
        actionTime = round((500 + targetPosX / 270 * 300 + random.randint(-100, 100)) / 20)
        targetSeq = tuple(round(polynomialCalc(x / (actionTime - 1), polynomial) * targetPosX) for x in range(actionTime))
        ac: ActionChains = ActionChains(browser, 20).click_and_hold(domYidunSlider).pause(random.randint(400, 700) / 1000)
        for i in range(len(targetSeq) - 1):
            ac = ac.move_by_offset(targetSeq[i + 1] - targetSeq[i], 0)
        ac.pause(random.randint(100, 200) / 1000).release().perform()

        # 成功了吗？
        try:
            WebDriverWait(browser, 2).until(lambda d: domValidate.get_attribute('value'))
        except TimeoutException:
            pass
        validate = domValidate.get_attribute('value')
        if validate:
            break
    return validate

# http服务器相关
class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.headers.get('Authorization') != f'Bearer {token}':
            self.send_response(403)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                'validation_token': None,
                'error': 'Authorization token is required.',
            }).encode('utf-8'))
            return

        if not lock.acquire(True, 15):
            self.send_response(429)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                'validation_token': None,
                'error': 'Too many requests, try again later.',
            }).encode('utf-8'))
            return

        try:
            validate = getValidateToken()
            if not validate:
                raise Exception('Failed to fetch validation token.')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                'validation_token': validate,
            }).encode('utf-8'))
        except Exception as ex:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                'validation_token': None,
                'error': f'{type(ex).__name__}: {ex}',
            }).encode('utf-8'))
        finally:
            lock.release()

if __name__ == '__main__':
    print('stuhealth-validate-server\n\nSource on GitHub: https://github.com/SO-JNU/stuhealth-validate-server\nLicense: GNU AGPLv3\nAuthor: Akarin\n')
    if len(sys.argv) < 3:
        print(f'Usage: {sys.argv[0]} PORT TOKEN')
        sys.exit(0)

    port = int(sys.argv[1])
    token = sys.argv[2]
    options = webdriver.FirefoxOptions()
    options.headless = True
    browser = webdriver.Firefox(options=options)
    browser.get('https://stuhealth.jnu.edu.cn/')

    print(f'Server listening on port {port}.')
    try:
        ThreadingHTTPServer(('0.0.0.0', port), Handler).serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        browser.quit()
