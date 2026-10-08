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

    // ── 1. 風の状態管理（基本：左向き、たまに右向き / 1〜2分で変化） ──
    let currentWindX = -1.2; // パーティクル用の風（初期値：左向き）
    let currentWindY = 0.2;
    let targetWindX = -1.2;
    let targetWindY = 0.2;
    let lastWindChange = 0;

    // 初回の風切り替えタイマー（1分〜2分）
    let nextWindInterval = 60000 + Math.random() * 60000;

    function updateWind(time) {
        if (time - lastWindChange > nextWindInterval) {
            const randPattern = Math.random();

            if (randPattern < 0.70) {
                // 基本パターン (約70%): 左向きの風 (強〜弱)
                targetWindX = -(Math.random() * 1.2 + 0.6);
                targetWindY = (Math.random() - 0.4) * 0.5;
            } else {
                // たまに吹くパターン (約30%): 右向きの風
                targetWindX = Math.random() * 1.0 + 0.5;
                targetWindY = (Math.random() - 0.4) * 0.5;
            }

            lastWindChange = time;
            nextWindInterval = 60000 + Math.random() * 60000;
        }

        // 風向きを時間をかけて滑らかに変化
        currentWindX += (targetWindX - currentWindX) * 0.003;
        currentWindY += (targetWindY - currentWindY) * 0.003;
    }

    // ── 2. 雲の準備（常に右へ流れる設定） ──
    const clouds = [];
    const cloudCount = 12;

    for (let i = 0; i < cloudCount; i++) {
        const isFar = Math.random() < 0.5;
        clouds.push({
            x: Math.random() * 1.6 - 0.3,
            y: Math.random() * 0.8 + 0.05,
            scale: isFar ? Math.random() * 0.8 + 0.6 : Math.random() * 1.2 + 1.4,
            baseSpeed: isFar ? 0.03 + Math.random() * 0.02 : 0.07 + Math.random() * 0.04, // 常に右向きの速度
            opacity: isFar ? 0.35 + Math.random() * 0.2 : 0.65 + Math.random() * 0.2,
            isFar: isFar,
            blobs: Array.from({ length: Math.floor(Math.random() * 4) + 4 }, (_, idx) => ({
                rx: idx * 25 - 30 + (Math.random() - 0.5) * 15,
                ry: (Math.random() - 0.5) * 20,
                r: Math.random() * 20 + 30
            }))
        });
    }

    // ── 3. 舞い散る葉・花びらの準備 ──
    const particles = [];
    const particleCount = 80;

    const greenColors = ['#2e7d32', '#388e3c', '#4caf50', '#81c784', '#a5d6a7'];
    const autumnColors = ['#fbc02d', '#f57f17', '#e53935', '#d32f2f'];
    const flowerColors = [
        { main: '#ff80ab', sub: '#f50057' },
        { main: '#ea80fc', sub: '#aa00ff' },
        { main: '#80d8ff', sub: '#0091ea' },
        { main: '#ffd180', sub: '#ff6d00' },
        { main: '#ffffff', sub: '#ff4081' }
    ];

    for (let i = 0; i < particleCount; i++) {
        const rand = Math.random();
        let type = 'green_leaf';
        let colorData = greenColors[Math.floor(Math.random() * greenColors.length)];

        if (rand > 0.75) {
            type = 'flower_petal';
            colorData = flowerColors[Math.floor(Math.random() * flowerColors.length)];
        } else if (rand > 0.60) {
            type = 'flower_5petal';
            colorData = flowerColors[Math.floor(Math.random() * flowerColors.length)];
        } else if (rand > 0.45) {
            type = 'autumn_leaf';
            colorData = autumnColors[Math.floor(Math.random() * autumnColors.length)];
        }

        particles.push({
            type: type,
            x: Math.random() * window.innerWidth,
            y: Math.random() * window.innerHeight,
            size: Math.random() * 6 + 5,
            weight: Math.random() * 0.5 + 0.8,
            angle: Math.random() * Math.PI * 2,
            rotSpeed: (Math.random() - 0.5) * 0.05,
            color: colorData,
            oscl: Math.random() * Math.PI * 2,
            osclSpeed: Math.random() * 0.03 + 0.01
        });
    }

    // ── 描画：雲（風向きに関係なく右向き固定移動） ──
    function drawCloud(c) {
        // 雲は常に右方向（プラス方向）へ移動
        c.x += c.baseSpeed / 1000;

        // 右端から消えたら左端から再登場
        if (c.x > 1.4) c.x = -0.4;

        const cx = canvas.width * c.x;
        const cy = canvas.height * c.y;

        ctx.save();
        const grad = ctx.createLinearGradient(cx, cy - 30 * c.scale, cx, cy + 40 * c.scale);
        grad.addColorStop(0, `rgba(255, 255, 255, ${c.opacity})`);
        grad.addColorStop(0.65, `rgba(242, 246, 252, ${c.opacity * 0.95})`);
        grad.addColorStop(1, `rgba(195, 215, 235, ${c.opacity * 0.5})`);

        ctx.fillStyle = grad;
        ctx.beginPath();

        c.blobs.forEach(b => {
            const bx = cx + b.rx * c.scale;
            const by = cy + b.ry * c.scale;
            const br = b.r * c.scale;
            ctx.moveTo(bx + br, by);
            ctx.arc(bx, by, br, 0, Math.PI * 2);
        });

        ctx.fill();
        ctx.restore();
    }

    // ── 描画：花びら・お花・葉っぱ ──
    function drawParticle(p) {
        ctx.save();
        ctx.translate(p.x, p.y);
        ctx.rotate(p.angle);
        ctx.globalAlpha = 0.88;

        if (p.type === 'flower_petal') {
            const grad = ctx.createRadialGradient(0, 0, 1, 0, 0, p.size);
            grad.addColorStop(0, p.color.main);
            grad.addColorStop(1, p.color.sub);
            ctx.fillStyle = grad;

            ctx.beginPath();
            ctx.moveTo(0, p.size);
            ctx.bezierCurveTo(-p.size * 1.2, p.size * 0.3, -p.size * 0.8, -p.size, 0, -p.size);
            ctx.bezierCurveTo(p.size * 0.8, -p.size, p.size * 1.2, p.size * 0.3, 0, p.size);
            ctx.fill();

        } else if (p.type === 'flower_5petal') {
            ctx.fillStyle = p.color.main;
            const petals = 5;
            for (let i = 0; i < petals; i++) {
                ctx.rotate((Math.PI * 2) / petals);
                ctx.beginPath();
                ctx.arc(0, p.size * 0.6, p.size * 0.45, 0, Math.PI * 2);
                ctx.fill();
            }
            ctx.fillStyle = '#fff59d';
            ctx.beginPath();
            ctx.arc(0, 0, p.size * 0.3, 0, Math.PI * 2);
            ctx.fill();

        } else {
            ctx.fillStyle = p.color;
            ctx.beginPath();
            ctx.moveTo(0, -p.size);
            ctx.quadraticCurveTo(p.size * 0.8, 0, 0, p.size);
            ctx.quadraticCurveTo(-p.size * 0.8, 0, 0, -p.size);
            ctx.fill();

            ctx.strokeStyle = 'rgba(255, 255, 255, 0.3)';
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(0, -p.size * 0.8);
            ctx.lineTo(0, p.size * 0.8);
            ctx.stroke();
        }

        ctx.restore();
    }

    // ── メインアニメーションループ ──
    function render(time) {
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        // 風向き・強さを更新（パーティクルに適用）
        updateWind(time);

        // 1. 遠景の雲
        clouds.filter(c => c.isFar).forEach(drawCloud);

        // 2. 舞い散る葉・花びら（左ベース、たまに右向きの風に影響される）
        particles.forEach(p => {
            p.oscl += p.osclSpeed;

            const flutterX = Math.sin(p.oscl) * 0.8;
            const flutterY = Math.cos(p.oscl * 0.7) * 0.6;

            p.x += (currentWindX * p.weight) + flutterX;
            p.y += (currentWindY * p.weight + 0.3) + flutterY;
            p.angle += p.rotSpeed + (currentWindX * 0.008);

            // 画面外へ出たときのループ（左右上下対応）
            if (p.x < -40) p.x = canvas.width + 30;
            if (p.x > canvas.width + 40) p.x = -30;
            if (p.y > canvas.height + 30) p.y = -30;
            if (p.y < -40) p.y = canvas.height + 30;

            drawParticle(p);
        });

        // 3. 近景の雲
        clouds.filter(c => !c.isFar).forEach(drawCloud);

        requestAnimationFrame(render);
    }

    requestAnimationFrame(render);
});