document.addEventListener('DOMContentLoaded', () => {
    const monitorBox = document.getElementById('monitor-box');
    const teamName = monitorBox.dataset.teamName;

    const timerElement = document.getElementById('timer-display');
    const stageElement = document.getElementById('current-stage');

    let targetTimestamp = null;
    let isPaused = false;
    let remainingSecondsWhenPaused = 0;

    // モニター用の高精度描画（絶対時刻計算で巻き戻り防止）
    function renderTimer() {
        let totalSeconds = 0;

        if (isPaused) {
            totalSeconds = remainingSecondsWhenPaused;
        } else if (targetTimestamp) {
            const now = Date.now();
            const diffMs = targetTimestamp - now;
            totalSeconds = Math.max(0, Math.floor(diffMs / 1000));
        }

        const minutes = Math.floor(totalSeconds / 60);
        const seconds = totalSeconds % 60;
        timerElement.textContent = `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;

        if (totalSeconds <= 180 && !isPaused) {
            timerElement.classList.add('timer-warning');
        } else {
            timerElement.classList.remove('timer-warning');
        }

        if (isPaused) {
            timerElement.classList.add('timer-paused');
        } else {
            timerElement.classList.remove('timer-paused');
        }
    }

    setInterval(renderTimer, 100);

    // 2秒ごとにサーバーと同期
    async function syncWithServer() {
        try {
            const response = await fetch(`/api/state/${teamName}/`);
            if (response.ok) {
                const data = await response.json();

                isPaused = data.is_paused;
                remainingSecondsWhenPaused = data.time_remaining;

                if (data.target_timestamp) {
                    targetTimestamp = data.target_timestamp;
                }

                if (data.is_cleared) {
                    monitorBox.classList.add('hidden');
                    clearScreen.classList.remove('hidden');
                } else if (data.is_game_over) {
                    stageElement.textContent = "GAME OVER";
                    stageElement.style.color = "#ff3366";
                } else {
                    stageElement.textContent = `STAGE ${data.stage}`;
                }
            }
        } catch (e) {
            console.error("同期エラー:", e);
        }
    }

    syncWithServer();
    setInterval(syncWithServer, 2000);
});