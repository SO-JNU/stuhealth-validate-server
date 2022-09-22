import io
import json
import os
import random
import requests
import sys
import threading
import typing
from PIL import Image
from http.server import BaseHTTPRequestHandler
from http.server import ThreadingHTTPServer
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import TimeoutException
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from urllib import parse

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
lock = threading.Lock()
session = requests.Session()
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
    WebDriverWait(browser, 3, .05).until(untilFindElement(By.CSS_SELECTOR, '#captcha .yidun .yidun_bg-img[src^="https://"]'))
    domYidunImg = browser.find_element(By.CSS_SELECTOR, '#captcha .yidun .yidun_bg-img')
    domYidunControl = browser.find_element(By.CSS_SELECTOR, '#captcha .yidun .yidun_control')
    domValidate = browser.find_element(By.CSS_SELECTOR, '#captcha input.yidun_input[name="NECaptchaValidate"]')

    validate = None
    # 重试5次
    for i in range(5):
        # 获取滑动验证码图片
        img = Image.open(io.BytesIO(session.get(domYidunImg.get_attribute('src').replace('@2x', '').replace('@3x', '')).content))
        # print(domYidunImg.get_attribute('src'))
        img = img.convert('HSV')
        for x in range(img.width):
            for y in range(img.height):
                p = list(img.getpixel((x, y)))
                p[2] = 255
                img.putpixel((x, y), tuple(p))

        # 图片大小320x160，每块80x80
        # +---+---+---+---+ Block:
        # |   |   |   |   | 0123
        # |  V|0 V|1 V|2  | 4567
        # | H | H | H | H |
        # +---+---+---+---+
        # | 0 | 1 | 2 | 3 |
        # |  V|3 V|4 V|5  |
        # |   |   |   |   |
        # +---+---+---+---+
        borderH = [False for _ in range(4)]
        borderV = [False for _ in range(6)]
        img = img.convert('RGB')

        for index, (rangeYA, rangeYB, rangeX) in enumerate((
            (range(80 - 4, 80), range(80, 80 + 4), range(  0,  80)),
            (range(80 - 4, 80), range(80, 80 + 4), range( 80, 160)),
            (range(80 - 4, 80), range(80, 80 + 4), range(160, 240)),
            (range(80 - 4, 80), range(80, 80 + 4), range(240, 320)),
        )):
            diffPixel = 0
            for x in rangeX:
                colorSumA = [0, 0, 0]
                colorSumB = [0, 0, 0]
                for ya, yb in zip(rangeYA, rangeYB):
                    colorA = img.getpixel((x, ya))
                    colorB = img.getpixel((x, yb))
                    for i in range(3):
                        colorSumA[i] += colorA[i]
                        colorSumB[i] += colorB[i]
                diffColor = 0
                for i in range(3):
                    if abs(colorSumA[i] - colorSumB[i]) / 4 > 24:
                        diffColor += 1
                if diffColor > 1:
                    diffPixel += 1
            borderH[index] = diffPixel > 20

        for index, (rangeXA, rangeXB, rangeY) in enumerate((
            (range(80  - 4,  80), range( 80,  80 + 4), range(  0,  80)),
            (range(160 - 4, 160), range(160, 240 + 4), range(  0,  80)),
            (range(240 - 4, 240), range(240, 240 + 4), range(  0,  80)),
            (range(80  - 4,  80), range( 80,  80 + 4), range(  80, 160)),
            (range(160 - 4, 160), range(160, 240 + 4), range(  80, 160)),
            (range(240 - 4, 240), range(240, 240 + 4), range(  80, 160)),
        )):
            diffPixel = 0
            for y in rangeY:
                colorSumA = [0, 0, 0]
                colorSumB = [0, 0, 0]
                for xa, xb in zip(rangeXA, rangeXB):
                    colorA = img.getpixel((xa, y))
                    colorB = img.getpixel((xb, y))
                    for i in range(3):
                        colorSumA[i] += colorA[i]
                        colorSumB[i] += colorB[i]
                diffColor = 0
                for i in range(3):
                    if abs(colorSumA[i] - colorSumB[i]) / 4 > 24:
                        diffColor += 1
                if diffColor > 1:
                    diffPixel += 1
            borderV[index] = diffPixel > 20

        # print(borderH, borderV)

        blocks = [
            (0, (borderH[0], borderV[0])),
            (1, (borderH[1], borderV[0], borderV[1])),
            (2, (borderH[2], borderV[1], borderV[2])),
            (3, (borderH[3], borderV[2])),
            (4, (borderH[0], borderV[3])),
            (5, (borderH[1], borderV[3], borderV[4])),
            (6, (borderH[2], borderV[4], borderV[5])),
            (7, (borderH[3], borderV[5])),
        ]
        random.shuffle(blocks)
        blocks.sort(key=lambda e: sum(e[1]) / len(e[1]), reverse=True)
        imgFromBlock, imgToBlock = tuple(x[0] for x in blocks[:2])
        # print(imgFromBlock, imgToBlock)

        domYidunImgFromBlock = browser.find_element(By.CSS_SELECTOR, f'#captcha .yidun .yidun_bgimg .yidun_inference.yidun_inference--{imgFromBlock}')
        domYidunImgToBlock = browser.find_element(By.CSS_SELECTOR, f'#captcha .yidun .yidun_bgimg .yidun_inference.yidun_inference--{imgToBlock}')

        ActionChains(browser, 20).move_to_element(domYidunControl).pause(.5).perform()
        moveOffsetX = (domYidunImgToBlock.rect['x'] + random.randint(0, round(domYidunImgToBlock.rect['width']))) - (domYidunImgFromBlock.rect['x'] + random.randint(0, round(domYidunImgFromBlock.rect['width'])))
        moveOffsetY = (domYidunImgToBlock.rect['y'] + random.randint(0, round(domYidunImgToBlock.rect['height']))) - (domYidunImgFromBlock.rect['y'] + random.randint(0, round(domYidunImgFromBlock.rect['height'])))
        # print(moveOffsetX, moveOffsetY)
        ActionChains(browser, round(50 + .5 * (moveOffsetX ** 2 + moveOffsetY ** 2) ** .5)).drag_and_drop_by_offset(domYidunImgFromBlock, moveOffsetX, moveOffsetY).perform()

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

    port, token = int(sys.argv[1]), sys.argv[2]
    options = webdriver.FirefoxOptions()
    options.headless = True

    s = requests.Session()
    s.hooks['response'].append(lambda r, *args, **kwargs: r.raise_for_status())
    s.get('https://stuhealth.jnu.edu.cn/', allow_redirects=False)
    r = s.get('https://stuhealth.jnu.edu.cn/jnu_authentication/public/redirect', allow_redirects=False)
    verifyID = parse.parse_qs(parse.urlparse(r.headers['Location']).query)['verifyID'][0]
    s.get('https://auth7.jnu.edu.cn/wechat_auth/wechat/wechatScanAsync', params={'verifyID': verifyID})

    browser = webdriver.Firefox(options=options)
    browser.install_addon(os.path.realpath('webdriver-cleaner'), temporary=True)
    browser.get('https://stuhealth.jnu.edu.cn/jnu_authentication/public/error')
    browser.add_cookie({
        'name': 'JNU_AUTH_VERIFY_COOKIE',
        'value': s.cookies.get('JNU_AUTH_VERIFY_COOKIE'),
        'path': '/',
        'secure': True,
        'httpOnly': True,
    })
    browser.get('https://stuhealth.jnu.edu.cn/')

    print(f'Server listening on port {port}.')
    try:
        ThreadingHTTPServer(('0.0.0.0', port), Handler).serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        browser.quit()
