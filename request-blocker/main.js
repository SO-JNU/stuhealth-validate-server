browser.webRequest.onBeforeRequest.addListener(
    () => ({cancel: true}),
    {
        urls: [
            '*://acstatic-dun.126.net/*/watchman.min.js*',
            '*://c.dun.163.com/api/v2/collect*',
            '*://da.dun.163.com/sn.gif*',
            '*://acstatic.dun.163yun.com/*/watchman.min.js*',
            '*://*.amap.com/*',
            '*://stuhealth.jnu.edu.cn/assets/image/svg/load.svg*',
            '*://stuhealth.jnu.edu.cn/favicon.ico',
            '*://stuhealth.jnu.edu.cn/glyphicons-halflings-regular.*.woff2*',
            '*://stuhealth.jnu.edu.cn/null',
            '*://stuhealth.jnu.edu.cn/styles.*.bundle.css*',
            '*://www.jnu.edu.cn/_upload/tpl/00/f5/245/template245/images/home/logo2.svg',
            '*://*.nstool.netease.com/ip.js',
        ],
    },
    ['blocking'],
);