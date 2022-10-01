# stuhealth-validate-server

> 2022 年 9 月 18 日起，打卡系统强制要求使用微信扫码登录才能访问。~~遗憾的是，扫码登录的过程目前还可以绕过。~~
>
> 2022 年 9 月 22 日起，打卡系统将验证码形式更改为在 4x2 的图块中“拖动交换 2 个图块复原图片”。为此编写了一些比较 naive 的算法，原理是将图片转换到 HSV 颜色空间并统一 V 通道后，再根据 RGB 通道判断图块之间的 10 条分界线是否为相邻图案。目前的单次成功率在 1/3 左右，五次成功至少一次的概率大于 3/4，虽然足够使用但是仍然有很大的提升空间。
>
> 2022 年 10 月 1 日起，扫码登录的绕过问题被修复了 ( ﾟ∀。) 拿手机扫🐴这种事情应该就没有办法自动化了啊 (　^ω^) 这里的代码和说明文本将作为存档，不再更新。
>
> **如果有人仍然要求你进行充满形式主义的打卡，我的建议是不打。**

提供给[自动打卡工具](https://github.com/SO-JNU/stuhealth)使用的，一个比较简单的滑动验证码自动完成 API 服务。使用 Python、Selenium 和 GeckoDriver 实现。

这个项目是一个“最简的可行产品”（Minimum viable product），因此存在一些局限性：

* 只能同时使用一个浏览器进程，因此同时响应多个请求的话需要排队。
* 鉴权机制使用的是简单的固定 token。
* HTTP 服务仅使用 Python 内置的 `BaseHTTPRequestHandler` 和 `ThreadingHTTPServer` 实现，不支持其他高级功能。
    * 如果一定要将 API 服务对公网暴露，建议使用 Nginx 等功能完整的 Web 服务器进行反向代理。

## 使用方式

使用前请安装好 Firefox 和 [GeckoDriver](https://github.com/mozilla/geckodriver)，然后 `pip3 install -r requirements.txt`。

> 如果你使用的是 Ubuntu 22.04 或更新的系统，则安装 Firefox 时默认会使用 Snap 而不是 apt，但是使用 Snap 安装后的浏览器无法在无头模式下运行。你可以参考[这个教程](https://ubuntuhandbook.org/index.php/2022/04/install-firefox-deb-ubuntu-22-04/)修改为传统的使用 apt 安装的方式。

`python3 main.py PORT TOKEN`

* `PORT` 为占用的端口。
* `TOKEN` 为调用 API 所需的 token，对应打卡工具中的 `-vt` 参数。
    * 你可以使用 `python3 -c "print(__import__('secrets').token_urlsafe(24))"` 随机生成一个。

服务启动后将在 `/` 路径响应请求。

你也可以使用 pm2 管理服务，配置文件参考：

```json
{
    "apps": [
        {
            "name": "stuhealth-validate-server",
            "interpreter": "python3",
            "script": "main.py",
            "args": [
                "PORT",
                "TOKEN"
            ],
            "instances": "1",
            "max_restarts": 16,
            "restart_delay": 1000,
            "min_uptime": "10s"
        }
    ]
}
```

虽然每次请求时会重试最多 5 次，但是仍然有概率无法自动完成验证码，因此我们建议在调用这个服务时另外自行添加重试机制。

服务运行时，GeckoDriver 会持续向 `geckodriver.log` 写入日志。如果你不需要，可以将日志文件删除后重定向到空设备：`ln -s geckodriver.log /dev/null`。

## TODO

* 更通用的缺口识别方式。
* 增加并发数。
* 减少无头浏览器的内存占用。
* 更丰富的鉴权机制（例如限制次数、频率之类的）。
* 除 Firefox 以外，也添加对 Chrome 的支持。
* 进一步优化模拟验证方式。
* ……

欢迎各位巨佬们提交 Pull Requests |ω•`)

（虽然大概是没有的，写了这些的结果可能就是鸽了）