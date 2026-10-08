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

    // ==========================================
    // 1. 上から下に降る「粉雪」
    // ==========================================
    const fallingSnow = [];
    const snowCount = 60;

    class SnowParticle {
        constructor() {
            this.reset(true);
        }

        reset(initial = false) {
            this.x = Math.random() * canvas.width;
            this.y = initial ? Math.random() * canvas.height : -10;
            this.size = Math.random() * 3 + 1;
            this.speedY = Math.random() * 0.8 + 0.4;
            this.speedX = Math.sin(Math.random() * Math.PI) * 0.4;
            this.alpha = Math.random() * 0.7 + 0.3;
        }

        update() {
            this.y += this.speedY;
            this.x += Math.sin(this.y * 0.02) * 0.3;
            if (this.y > canvas.height + 10) {
                this.reset();
            }
        }

        draw() {
            ctx.save();
            ctx.globalAlpha = this.alpha;
            ctx.fillStyle = '#ffffff';
            ctx.shadowColor = '#80d8ff';
            ctx.shadowBlur = 4;
            ctx.beginPath();
            ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);
            ctx.fill();
            ctx.restore();
        }
    }

    // ==========================================
    // 2. 画面いっぱいに現れる超特大の雪結晶
    // ==========================================
    const giantCrystals = [];
    const giantCount = 6;

    class GiantSnowCrystal {
        constructor() {
            this.reset(true);
        }

        reset(initial = false) {
            this.x = Math.random() * canvas.width;
            this.y = Math.random() * canvas.height;
            this.size = Math.random() * 120 + 100;

            this.scale = 0.4;
            this.alpha = 0;
            this.maxAlpha = Math.random() * 0.35 + 0.2;
            this.life = 0;
            this.maxLife = Math.random() * 260 + 200;

            this.rotation = Math.random() * Math.PI * 2;
            this.rotSpeed = (Math.random() - 0.5) * 0.003;
            this.pattern = Math.floor(Math.random() * 3);
        }

        update() {
            this.life++;
            this.rotation += this.rotSpeed;

            const progress = this.life / this.maxLife;

            if (progress < 0.2) {
                this.alpha = (progress / 0.2) * this.maxAlpha;
                this.scale = 0.5 + (progress / 0.2) * 0.5;
            } else if (progress > 0.65) {
                this.alpha = (1 - (progress - 0.65) / 0.35) * this.maxAlpha;
            } else {
                this.alpha = this.maxAlpha;
                this.scale = 1.0;
            }

            if (this.life >= this.maxLife) {
                this.reset();
            }
        }

        draw() {
            ctx.save();
            ctx.translate(this.x, this.y);
            ctx.rotate(this.rotation);
            ctx.scale(this.scale, this.scale);
            ctx.globalAlpha = Math.max(0, this.alpha);

            ctx.strokeStyle = '#ffffff';
            ctx.shadowColor = '#00e5ff';
            ctx.shadowBlur = 20;
            ctx.lineWidth = 2.2;

            ctx.beginPath();
            for (let i = 0; i < 6; i++) {
                ctx.moveTo(0, 0);
                ctx.lineTo(0, -this.size);

                if (this.pattern === 0) {
                    for (let j = 1; j <= 3; j++) {
                        const pos = -this.size * (j * 0.25);
                        const span = this.size * (0.35 - j * 0.05);
                        ctx.moveTo(0, pos);
                        ctx.lineTo(-span, pos - span * 0.5);
                        ctx.moveTo(0, pos);
                        ctx.lineTo(span, pos - span * 0.5);
                    }
                } else if (this.pattern === 1) {
                    ctx.moveTo(0, -this.size * 0.3);
                    ctx.lineTo(-this.size * 0.2, -this.size * 0.5);
                    ctx.lineTo(0, -this.size * 0.7);
                    ctx.lineTo(this.size * 0.2, -this.size * 0.5);
                    ctx.closePath();

                    ctx.moveTo(0, -this.size * 0.7);
                    ctx.lineTo(-this.size * 0.25, -this.size * 0.85);
                    ctx.moveTo(0, -this.size * 0.7);
                    ctx.lineTo(this.size * 0.25, -this.size * 0.85);
                } else {
                    ctx.moveTo(0, -this.size * 0.4);
                    ctx.lineTo(-this.size * 0.3, -this.size * 0.6);
                    ctx.moveTo(0, -this.size * 0.4);
                    ctx.lineTo(this.size * 0.3, -this.size * 0.6);

                    ctx.moveTo(0, -this.size * 0.75);
                    ctx.lineTo(-this.size * 0.2, -this.size * 0.9);
                    ctx.moveTo(0, -this.size * 0.75);
                    ctx.lineTo(this.size * 0.2, -this.size * 0.9);
                }

                ctx.rotate(Math.PI / 3);
            }
            ctx.stroke();

            ctx.fillStyle = '#e0f7fa';
            ctx.beginPath();
            ctx.arc(0, 0, this.size * 0.08, 0, Math.PI * 2);
            ctx.fill();

            ctx.restore();
        }
    }

    // 初期化
    for (let i = 0; i < snowCount; i++) fallingSnow.push(new SnowParticle());
    for (let i = 0; i < giantCount; i++) giantCrystals.push(new GiantSnowCrystal());

    // ==========================================
    // 3. メインアニメーションループ
    // ==========================================
    function render() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        // 時間計算（タイマー連動）
        let currentRemaining = TOTAL_LIMIT;
        if (isPaused) {
            currentRemaining = remainingSecondsWhenPaused;
        } else if (targetTimestamp) {
            currentRemaining = Math.max(0, Math.floor((targetTimestamp - Date.now()) / 1000));
        }

        // 粉雪の更新・描画
        fallingSnow.forEach(s => {
            s.update();
            s.draw();
        });

        // 超特大雪結晶の更新・描画
        giantCrystals.forEach(g => {
            g.update();
            g.draw();
        });

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

    // ==========================================
    // 4. タイマー連動の凍結（フロスト）処理
    // ==========================================
    let freezeOverlay = document.getElementById('freeze-overlay');
    if (!freezeOverlay) {
        freezeOverlay = document.createElement('div');
        freezeOverlay.id = 'freeze-overlay';
        document.body.appendChild(freezeOverlay);
    }

    function updateFreezeProgress() {
        let currentRemaining = TOTAL_LIMIT;
        if (isPaused) {
            currentRemaining = remainingSecondsWhenPaused;
        } else if (targetTimestamp) {
            currentRemaining = Math.max(0, Math.floor((targetTimestamp - Date.now()) / 1000));
        }

        const elapsedRatio = Math.max(0, Math.min(1, (TOTAL_LIMIT - currentRemaining) / TOTAL_LIMIT));
        const freezePercent = elapsedRatio * 100;

        freezeOverlay.style.setProperty('--freeze-level', `${freezePercent}%`);
    }

    setInterval(updateFreezeProgress, 1000);
    updateFreezeProgress();
});