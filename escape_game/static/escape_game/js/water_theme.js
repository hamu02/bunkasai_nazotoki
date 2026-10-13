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

    // 水中でゆらゆら昇る泡（バブル）と光の粒
    const bubbles = [];
    const bubbleCount = 45;

    for (let i = 0; i < bubbleCount; i++) {
        bubbles.push({
            x: Math.random() * canvas.width,
            y: Math.random() * canvas.height,
            size: Math.random() * 6 + 2,          // 泡の大きさ
            speedY: -(Math.random() * 0.8 + 0.3), // 下から上へ昇る速度
            speedX: (Math.random() - 0.5) * 0.4,  // 左右の揺れ
            wobbleSpeed: Math.random() * 0.05 + 0.02,
            wobbleDist: Math.random() * 15 + 5,   // 揺れの幅
            alpha: Math.random() * 0.6 + 0.2      // 透明感
        });
    }

    let time = 0;

    function render() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        time += 0.02;

// 1. 水中の美しい縦グラデーション（下部の緑味を消してクリアな青緑に修正）
        const bgGrad = ctx.createLinearGradient(0, 0, 0, canvas.height);
        bgGrad.addColorStop(0, '#00acc1'); // 上部（光が差し込む水面側）
        bgGrad.addColorStop(0.5, '#00838f'); // 中間
        bgGrad.addColorStop(1, '#005f73'); // 下部（濁りを取った美しい深海ブルー）
        ctx.fillStyle = bgGrad;
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        // 2. 水面から差し込む光の筋（うっすらと揺らぐ光のカーテン）
        ctx.save();
        ctx.globalCompositeOperation = 'screen';
        for (let i = 0; i < 5; i++) {
            const xPos = (canvas.width / 5) * i + Math.sin(time * 0.3 + i) * 50;
            const grad = ctx.createLinearGradient(xPos, 0, xPos + 100, canvas.height);
            grad.addColorStop(0, `rgba(255, 255, 255, ${0.08 + Math.sin(time + i) * 0.03})`);
            grad.addColorStop(1, 'rgba(255, 255, 255, 0)');

            ctx.fillStyle = grad;
            ctx.beginPath();
            ctx.moveTo(xPos - 50, 0);
            ctx.lineTo(xPos + 150, 0);
            ctx.lineTo(xPos + 300, canvas.height);
            ctx.lineTo(xPos + 100, canvas.height);
            ctx.closePath();
            ctx.fill();
        }
        ctx.restore();

        // 3. 下からポコポコと昇る泡の描画と更新
        bubbles.forEach(b => {
            b.y += b.speedY;
            // 左右にゆらゆらと蛇行しながら昇る
            const xOffset = Math.sin(b.y * b.wobbleSpeed + time) * b.wobbleDist;
            const currentX = b.x + xOffset;

            // 画面の上に到達したら下から再登場
            if (b.y < -20) {
                b.y = canvas.height + 20;
                b.x = Math.random() * canvas.width;
            }

            ctx.save();
            ctx.globalAlpha = b.alpha;

            // 泡の本体（半透明の丸に白いハイライト）
            ctx.fillStyle = 'rgba(178, 235, 242, 0.25)';
            ctx.strokeStyle = 'rgba(255, 255, 255, 0.7)';
            ctx.lineWidth = 1.2;

            ctx.beginPath();
            ctx.arc(currentX, b.y, b.size, 0, Math.PI * 2);
            ctx.fill();
            ctx.stroke();

            // 泡のハイライト（ツヤ）
            ctx.fillStyle = 'rgba(255, 255, 255, 0.9)';
            ctx.beginPath();
            ctx.arc(currentX - b.size * 0.3, b.y - b.size * 0.3, b.size * 0.25, 0, Math.PI * 2);
            ctx.fill();

            ctx.restore();
        });

        requestAnimationFrame(render);
    }

    render();
});