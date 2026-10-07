document.addEventListener('DOMContentLoaded', () => {
    const timerElement = document.getElementById('player-timer');
    const wrapper = document.querySelector('.game-wrapper');
    // HTMLの data-team-name からチーム名を取得
    const teamName = wrapper ? wrapper.dataset.teamName : '';

    let targetTimestamp = null;
    let isPaused = false;
    let remainingSecondsWhenPaused = 0;
    let isRedirecting = false;

    // タイマー描画機能
    function renderTimer() {
        if (!timerElement) return;

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
    }

    // 100msごとにタイマー表示更新
    setInterval(renderTimer, 100);

    // サーバーとの定期同期（2秒周期）
    async function syncWithServer() {
        if (!teamName) return;

        try {
            const response = await fetch(`/api/state/${encodeURIComponent(teamName)}/`);
            if (response.ok) {
                const data = await response.json();

                isPaused = data.is_paused;
                remainingSecondsWhenPaused = data.time_remaining;

                if (data.target_timestamp) {
                    targetTimestamp = data.target_timestamp;
                }

                // 🔻 判定結果に応じてクリア画面・ゲームオーバー画面へ自動遷移
                if (data.is_cleared) {
                    isRedirecting = true;
                    window.location.href = '/game_clear/';
                } else if (data.is_game_over) {
                    isRedirecting = true;
                    window.location.href = '/game_over/';
                }
            }
        } catch (e) {
            console.error("同期エラー:", e);
        }
    }

    // 初回同期実行 ＆ 2秒おきに監視
    syncWithServer();
    setInterval(syncWithServer, 2000);
});