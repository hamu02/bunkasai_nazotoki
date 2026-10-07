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

    const wrapper = document.querySelector('.game-wrapper');
    const teamName = wrapper ? wrapper.dataset.teamName : '';

    let targetTimestamp = null;
    let isPaused = false;
    let remainingSecondsWhenPaused = 0;
    const TOTAL_LIMIT = 1800; // 30分 (1800秒)

    // 1. 光の粉塵（少し落ち着いた密度に）
    const particles = Array.from({ length: 50 }, () => ({
        x: Math.random() * window.innerWidth,
        y: Math.random() * window.innerHeight,
        radius: Math.random() * 2.0 + 0.5,
        speedY: -(Math.random() * 0.3 + 0.1),
        speedX: (Math.random() - 0.5) * 0.2,
        alpha: Math.random() * 0.6 + 0.2
    }));

    // 2. 精密メカ歯車群（画面全体に適度な余白をもって配置：10個）
    const bgGears = [
        // 上部・左右
        { x: 0.12, y: 0.22, radius: 140, teeth: 22, speed: 0.0007, color: 'rgba(212, 175, 55, 0.28)', rot: 0.4 },
        { x: 0.62, y: 0.15, radius: 160, teeth: 26, speed: -0.0005, color: 'rgba(0, 255, 204, 0.28)', rot: 1.2 },
        // 中央周辺（薄め）
        { x: 0.88, y: 0.42, radius: 130, teeth: 18, speed: -0.0008, color: 'rgba(212, 175, 55, 0.28)', rot: 0.5 },
        { x: 0.08, y: 0.62, radius: 150, teeth: 22, speed: 0.0006, color: 'rgba(255, 77, 77, 0.25)', rot: 1.5 },
        // 下部（間引きしてスッキリ）
        { x: 0.32, y: 0.85, radius: 140, teeth: 20, speed: -0.0009, color: 'rgba(255, 204, 0, 0.3)', rot: -0.8 },
        { x: 0.58, y: 0.90, radius: 190, teeth: 28, speed: -0.0004, color: 'rgba(255, 170, 0, 0.32)', rot: 0.9 },
        { x: 0.82, y: 0.82, radius: 130, teeth: 18, speed: 0.0008, color: 'rgba(0, 255, 204, 0.28)', rot: -1.2 },
        { x: 0.02, y: 0.92, radius: 110, teeth: 16, speed: -0.001, color: 'rgba(212, 175, 55, 0.25)', rot: 0.8 },
        { x: 0.45, y: 0.65, radius: 90,  teeth: 14, speed: 0.0011, color: 'rgba(0, 255, 204, 0.22)', rot: -0.5 },
        { x: 0.72, y: 0.68, radius: 110, teeth: 16, speed: -0.0007, color: 'rgba(255, 170, 0, 0.25)', rot: 0.7 }
    ];

    // 3. 散らばる時計盤（重なりを減らし視覚的疲労を軽減：5個）
    const clocks = [
        { x: 0.25, y: 0.25, radius: 220, color: '#ffcc00', glow: 'rgba(255, 204, 0, 0.4)', alpha: 0.6 },
        { x: 0.78, y: 0.20, radius: 200, color: '#00ffcc', glow: 'rgba(0, 255, 204, 0.4)', alpha: 0.65 },
        { x: 0.48, y: 0.80, radius: 250, color: '#ffaa00', glow: 'rgba(255, 170, 0, 0.6)', alpha: 0.75 },
        { x: 0.10, y: 0.85, radius: 280, color: '#ff4d4d', glow: 'rgba(255, 77, 77, 0.4)', alpha: 0.45 },
        { x: 0.88, y: 0.85, radius: 260, color: '#e69900', glow: 'rgba(230, 153, 0, 0.4)', alpha: 0.5 }
    ];

    // 4. タイマー連動砂時計（倒れたり傾いたデザインを厳選して配置：8個）
    const hourglasses = [
        { x: 0.54, y: 0.22, scale: 0.65, alpha: 0.30, color: '#00ffcc', rot: -0.8 },
        { x: 0.08, y: 0.25, scale: 0.70, alpha: 0.32, color: '#ffaa00', rot: 0.25 },
        { x: 0.85, y: 0.52, scale: 0.75, alpha: 0.35, color: '#33ccff', rot: 0.6 },
        { x: 0.16, y: 0.58, scale: 0.80, alpha: 0.38, color: '#ffd700', rot: -0.35 },
        { x: 0.35, y: 0.92, scale: 0.70, alpha: 0.38, color: '#ffd700', rot: 0.85 },
        { x: 0.62, y: 0.88, scale: 0.80, alpha: 0.40, color: '#00ffcc', rot: -0.2 },
        { x: 0.80, y: 0.82, scale: 0.72, alpha: 0.35, color: '#ffaa00', rot: 0.7 },
        { x: 0.28, y: 0.72, scale: 0.65, alpha: 0.32, color: '#ff4d4d', rot: 1.1 }
    ];

    const romanNumerals = ["XII", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI"];

    // ── 描画：精密メカ歯車 ──
    function drawGear(g) {
        g.angle = (g.angle || g.rot) + g.speed;
        const cx = canvas.width * g.x;
        const cy = canvas.height * g.y;

        ctx.save();
        ctx.translate(cx, cy);
        ctx.rotate(g.angle);

        ctx.strokeStyle = g.color;
        ctx.fillStyle = g.color;

        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.arc(0, 0, g.radius * 0.85, 0, Math.PI * 2);
        ctx.stroke();

        ctx.lineWidth = 2.2;
        ctx.beginPath();
        const outerR = g.radius;
        const innerR = g.radius * 0.88;
        for (let i = 0; i < g.teeth; i++) {
            const a1 = (i / g.teeth) * Math.PI * 2;
            const a2 = a1 + (Math.PI / g.teeth) * 0.4;
            const a3 = a1 + (Math.PI / g.teeth) * 0.6;
            const a4 = a1 + (Math.PI / g.teeth);

            ctx.lineTo(Math.cos(a1) * innerR, Math.sin(a1) * innerR);
            ctx.lineTo(Math.cos(a2) * outerR, Math.sin(a2) * outerR);
            ctx.lineTo(Math.cos(a3) * outerR, Math.sin(a3) * outerR);
            ctx.lineTo(Math.cos(a4) * innerR, Math.sin(a4) * innerR);
        }
        ctx.closePath();
        ctx.stroke();

        ctx.beginPath();
        ctx.arc(0, 0, g.radius * 0.5, 0, Math.PI * 2);
        ctx.stroke();

        ctx.beginPath();
        ctx.arc(0, 0, g.radius * 0.2, 0, Math.PI * 2);
        ctx.stroke();

        ctx.lineWidth = 1.8;
        const spokeCount = g.teeth > 20 ? 6 : 4;
        for (let i = 0; i < spokeCount; i++) {
            const a = (i / spokeCount) * Math.PI * 2;
            ctx.beginPath();
            ctx.moveTo(Math.cos(a) * (g.radius * 0.2), Math.sin(a) * (g.radius * 0.2));
            ctx.lineTo(Math.cos(a) * (g.radius * 0.85), Math.sin(a) * (g.radius * 0.85));
            ctx.stroke();
        }

        ctx.restore();
    }

    // ── 描画：時計（リアルタイム連動） ──
    function drawClock(c, now) {
        const cx = canvas.width * c.x;
        const cy = canvas.height * c.y;

        ctx.save();
        ctx.translate(cx, cy);
        ctx.globalAlpha = c.alpha;

        ctx.shadowColor = c.glow;
        ctx.shadowBlur = 15;

        ctx.strokeStyle = c.color;
        ctx.lineWidth = 3.5;
        ctx.beginPath(); ctx.arc(0, 0, c.radius, 0, Math.PI * 2); ctx.stroke();
        ctx.lineWidth = 1.8;
        ctx.beginPath(); ctx.arc(0, 0, c.radius * 0.92, 0, Math.PI * 2); ctx.stroke();
        ctx.beginPath(); ctx.arc(0, 0, c.radius * 0.72, 0, Math.PI * 2); ctx.stroke();

        ctx.fillStyle = c.color;
        ctx.font = `bold ${Math.floor(c.radius * 0.11)}px 'Georgia', serif`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';

        for (let i = 0; i < 12; i++) {
            const a = (i / 12) * Math.PI * 2 - Math.PI / 2;
            const tx = Math.cos(a) * (c.radius * 0.82);
            const ty = Math.sin(a) * (c.radius * 0.82);
            ctx.fillText(romanNumerals[i], tx, ty);
        }

        const hours = now.getHours() % 12;
        const minutes = now.getMinutes();
        const seconds = now.getSeconds();
        const milliseconds = now.getMilliseconds();

        const secWithMs = seconds + milliseconds / 1000;
        const secondAngle = (secWithMs / 60) * Math.PI * 2 - Math.PI / 2;
        const minuteAngle = ((minutes + secWithMs / 60) / 60) * Math.PI * 2 - Math.PI / 2;
        const hourAngle = ((hours + minutes / 60) / 12) * Math.PI * 2 - Math.PI / 2;

        ctx.save();
        ctx.rotate(hourAngle + Math.PI / 2);
        ctx.lineWidth = 5;
        ctx.beginPath(); ctx.moveTo(0, 10); ctx.lineTo(0, -c.radius * 0.42); ctx.stroke();
        ctx.restore();

        ctx.save();
        ctx.rotate(minuteAngle + Math.PI / 2);
        ctx.lineWidth = 3.5;
        ctx.beginPath(); ctx.moveTo(0, 10); ctx.lineTo(0, -c.radius * 0.62); ctx.stroke();
        ctx.restore();

        ctx.save();
        ctx.rotate(secondAngle + Math.PI / 2);
        ctx.lineWidth = 1.8;
        ctx.beginPath(); ctx.moveTo(0, 15); ctx.lineTo(0, -c.radius * 0.78); ctx.stroke();
        ctx.restore();

        ctx.beginPath(); ctx.arc(0, 0, 6, 0, Math.PI * 2); ctx.fill();

        ctx.restore();
    }

    // ── 描画：タイマー連動の砂時計 ──
    function drawHourglass(hg, remainingRatio) {
        const cx = canvas.width * hg.x;
        const cy = canvas.height * hg.y;
        const w = 46 * hg.scale;
        const h = 78 * hg.scale;

        ctx.save();
        ctx.translate(cx, cy);
        ctx.rotate(hg.rot);
        ctx.globalAlpha = hg.alpha;

        ctx.strokeStyle = hg.color;
        ctx.fillStyle = hg.color;
        ctx.lineWidth = 1.8;

        // 枠組み
        ctx.strokeRect(-w / 2, -h / 2, w, 4);
        ctx.strokeRect(-w / 2, h / 2 - 4, w, 4);

        // ガラス
        ctx.beginPath();
        ctx.moveTo(-w / 2, -h / 2 + 4);
        ctx.lineTo(w / 2, -h / 2 + 4);
        ctx.lineTo(-3, 0);
        ctx.lineTo(w / 2, h / 2 - 4);
        ctx.lineTo(-w / 2, h / 2 - 4);
        ctx.lineTo(3, 0);
        ctx.closePath();
        ctx.stroke();

        // 砂の量連動
        if (remainingRatio > 0) {
            const topHeight = (h / 2 - 7) * remainingRatio;
            const topWidth = (w / 2 - 4) * remainingRatio;
            ctx.beginPath();
            ctx.moveTo(-topWidth, -h / 2 + 4 + (h / 2 - 7 - topHeight));
            ctx.lineTo(topWidth, -h / 2 + 4 + (h / 2 - 7 - topHeight));
            ctx.lineTo(0, 0);
            ctx.closePath();
            ctx.fill();
        }

        const bottomRatio = 1 - remainingRatio;
        if (bottomRatio > 0) {
            const bottomHeight = (h / 2 - 7) * bottomRatio;
            const bottomWidth = (w / 2 - 4) * bottomRatio;
            ctx.beginPath();
            ctx.moveTo(-bottomWidth, h / 2 - 4);
            ctx.lineTo(bottomWidth, h / 2 - 4);
            ctx.lineTo(0, h / 2 - 4 - bottomHeight);
            ctx.closePath();
            ctx.fill();
        }

        if (remainingRatio > 0 && remainingRatio < 1 && !isPaused) {
            ctx.lineWidth = 1.2;
            ctx.beginPath();
            ctx.moveTo(0, 0);
            ctx.lineTo(0, h / 2 - 4);
            ctx.stroke();
        }

        ctx.restore();
    }

    // ── メインループ ──
    function render() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        const now = new Date();

        let currentRemaining = TOTAL_LIMIT;
        if (isPaused) {
            currentRemaining = remainingSecondsWhenPaused;
        } else if (targetTimestamp) {
            currentRemaining = Math.max(0, Math.floor((targetTimestamp - Date.now()) / 1000));
        }
        const remainingRatio = Math.max(0, Math.min(1, currentRemaining / TOTAL_LIMIT));

        particles.forEach(p => {
            ctx.fillStyle = `rgba(255, 230, 150, ${p.alpha})`;
            ctx.beginPath();
            ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
            ctx.fill();

            p.y += p.speedY;
            p.x += p.speedX;
            if (p.y < 0) {
                p.y = canvas.height;
                p.x = Math.random() * canvas.width;
            }
        });

        bgGears.forEach(drawGear);
        hourglasses.forEach(hg => drawHourglass(hg, remainingRatio));
        clocks.forEach(c => drawClock(c, now));

        requestAnimationFrame(render);
    }

    async function syncState() {
        if (!teamName) return;
        try {
            const res = await fetch(`/api/state/${encodeURIComponent(teamName)}/`);
            if (res.ok) {
                const data = await res.json();
                isPaused = data.is_paused;
                remainingSecondsWhenPaused = data.time_remaining;
                if (data.target_timestamp) targetTimestamp = data.target_timestamp;
            }
        } catch (e) {
            console.error(e);
        }
    }

    syncState();
    setInterval(syncState, 2000);

    render();
});