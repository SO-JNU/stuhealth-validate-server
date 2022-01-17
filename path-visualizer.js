// 记录并展示手动完成滑动验证码时的轨迹

(() => {

const slider = document.querySelector('.yidun_slider');
const colors = ['#f68', '#39e', '#5bb', '#fc5', '#96f'];

slider.addEventListener('mousedown', async () => {
    /** @type {{x: Number, y: Number}[]} */
    const path = [{x: 0, y: 0}];
    const ts = Date.now();
    const record = () => path.push({
        x: Date.now() - ts,
        y: parseInt(slider.style.left.replace('px', '')) || 0,
    });

    slider.addEventListener('mousemove', record);
    /** @type {() => null} */
    let resolveFn;
    await new Promise(resolve => slider.addEventListener('mouseup', resolveFn = resolve));
    slider.removeEventListener('mouseup', resolveFn);
    slider.removeEventListener('mousemove', record);
    if (path.length < 16) return;
    console.log(path);
    const endY = path[path.length - 1].y;
    const color = colors[Math.floor(Math.random() * colors.length)];

    console.log((await fetch('https://quickchart.io/chart/create', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            format: 'svg',
            width: 320,
            height: 320,
            devicePixelRatio: 2,
            chart: {
                type: 'line',
                data: {
                    labels: path.map(e => e.x),
                    datasets: [
                        {
                            label: `Path (endY = ${endY})`,
                            backgroundColor: color,
                            borderColor: color,
                            lineTension: .5,
                            data: path.map(e => e.y / endY),
                            fill: false,
                        },
                    ],
                },
            },
            options: {
                scales: {
                    x: {
                        type: 'linear',
                        ticks: {
                            stepSize: 1,
                        },
                    },
                },
            },
        }),
    }).then(r => r.json())).url);
});

})()
