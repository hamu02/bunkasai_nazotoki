document.addEventListener('DOMContentLoaded', () => {
    const canvas = document.getElementById('effect-canvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    function resize() {
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
    }
    resize();
    window.addEventListener('resize', resize);

    // 1. 火の粉（スパーク）
    const sparkCount = 75;
    const sparks = [];

    function createSpark(fromTop = false) {
        return {
            x: Math.random() * canvas.width,
            y: fromTop ? -20 : canvas.height + Math.random() * 20,
            vx: (Math.random() - 0.5) * 2.5,
            vy: fromTop ? (Math.random() * 2 + 1) : -(Math.random() * 3.5 + 1.5),
            size: Math.random() * 2 + 0.8,
            life: 0,
            maxLife: Math.random() * 120 + 60,
            color: Math.random() < 0.2 ? '#ffffff' : (Math.random() < 0.6 ? '#ffaa00' : '#ff3300')
        };
    }

    for (let i = 0; i < sparkCount; i++) {
        const s = createSpark(Math.random() < 0.3);
        s.life = Math.random() * s.maxLife;
        sparks.push(s);
    }

    let step = 0;

    function getMagmaMaxHeight() {
        return canvas.height * 0.48;
    }

    // 複雑な層で質感を出したマグマ描画
    function drawTexturedMagma() {
        const maxHeight = getMagmaMaxHeight();

        ctx.save();

        // 背後の熱気グラデーション
        const bgGrad = ctx.createLinearGradient(0, canvas.height, 0, canvas.height - maxHeight - 80);
        bgGrad.addColorStop(0, '#550000');
        bgGrad.addColorStop(0.5, '#220000');
        bgGrad.addColorStop(1, 'rgba(0,0,0,0)');

        ctx.fillStyle = bgGrad;
        ctx.fillRect(0, canvas.height - maxHeight - 80, canvas.width, maxHeight + 80);

        // 程よいブラーで波をなじませる
        ctx.filter = 'blur(10px)';

        // 色の交互構造（深紅 -> オレンジ -> 濃い赤 -> ずらした発光オレンジ -> 底部深紅）
        const magmaLayers = [
            // 1. 最深部：黒ずんだ深紅
            { height: maxHeight * 0.95, color: 'rgba(140, 0, 0, 0.9)', speed: 0.008, freq: 0.005, phaseShift: 0 },
            // 2. 上層：鮮やかな発光オレンジ
            { height: maxHeight * 0.78, color: 'rgba(255, 100, 0, 0.85)', speed: 0.014, freq: 0.007, phaseShift: 1.2 },
            // 3. オレンジのすぐ下に入る濃い赤の層
            { height: maxHeight * 0.62, color: 'rgba(180, 15, 0, 0.9)', speed: 0.020, freq: 0.010, phaseShift: 2.5 },
            // 4. 赤の下から少しずらして見え隠れするオレンジ層
            { height: maxHeight * 0.45, color: 'rgba(255, 120, 10, 0.8)', speed: 0.026, freq: 0.013, phaseShift: 4.0 },
            // 5. 底面の深み（最手前の濃い赤）
            { height: maxHeight * 0.28, color: 'rgba(120, 0, 0, 0.95)', speed: 0.018, freq: 0.008, phaseShift: 5.5 }
        ];

        // 各層を描画（lighterとsource-overを混ぜて質感を出す）
        magmaLayers.forEach((layer, index) => {
            // 一部の層を重ね合わせて発光感・色の深みを作る
            if (index % 2 === 1) {
                ctx.globalCompositeOperation = 'lighter';
            } else {
                ctx.globalCompositeOperation = 'source-over';
            }

            ctx.fillStyle = layer.color;
            ctx.beginPath();
            ctx.moveTo(0, canvas.height);

            for (let x = 0; x <= canvas.width; x += 12) {
                const y = canvas.height - layer.height
                    + Math.sin(x * layer.freq + step * layer.speed + layer.phaseShift) * 18
                    + Math.cos(x * 0.015 - step * layer.speed * 0.8) * 12;
                ctx.lineTo(x, y);
            }

            ctx.lineTo(canvas.width, canvas.height);
            ctx.closePath();
            ctx.fill();
        });

        ctx.restore();
    }

    function render() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        step++;

        // 1. 質感重視のマグマ描画
        drawTexturedMagma();

        // 2. 火の粉描画
        sparks.forEach((s, idx) => {
            s.life++;
            s.x += s.vx + Math.sin(s.life * 0.04) * 0.6;
            s.y += s.vy;

            if (s.life >= s.maxLife || s.x < -30 || s.x > canvas.width + 30 || s.y < -30 || s.y > canvas.height + 30) {
                sparks[idx] = createSpark(Math.random() < 0.3);
            }

            ctx.save();
            ctx.globalCompositeOperation = 'lighter';
            const alpha = 1 - (s.life / s.maxLife);
            ctx.strokeStyle = s.color;
            ctx.lineWidth = s.size;
            ctx.lineCap = 'round';
            ctx.globalAlpha = Math.max(0, alpha);

            ctx.beginPath();
            ctx.moveTo(s.x, s.y);
            ctx.lineTo(s.x - s.vx * 3, s.y - s.vy * 3);
            ctx.stroke();
            ctx.restore();
        });

        requestAnimationFrame(render);
    }

    render();
});