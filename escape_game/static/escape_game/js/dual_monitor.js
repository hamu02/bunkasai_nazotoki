document.addEventListener('DOMContentLoaded', () => {
    async function updateDualMonitor() {
        try {
            const response = await fetch('/api/active_teams/');
            if (response.ok) {
                const data = await response.json();
                const teams = data.teams || [];

                for (let i = 0; i < 2; i++) {
                    const slot = document.getElementById(`slot-${i}`);
                    const team = teams[i];

                    if (team) {
                        // 班が存在する場合のHTML構築
                        let timerText = formatTime(team.time_remaining);
                        let warningClass = team.time_remaining <= 180 ? 'timer-warning' : '';
                        let stageText = team.is_cleared ? "CLEAR!" : (team.is_game_over ? "GAME OVER" : `STAGE ${team.stage}`);

                        slot.className = "monitor-slot";
                        if (team.is_cleared) slot.classList.add('slot-cleared');

                        slot.innerHTML = `
                            <div class="slot-left">
                                <div class="team-name-label">TEAM</div>
                                <div class="team-name-value">${escapeHtml(team.name)}</div>
                                <div class="stage-badge">${stageText}</div>
                            </div>
                            <div class="slot-right">
                                <div class="timer-label">TIME REMAINING</div>
                                <div class="slot-timer ${warningClass}">${timerText}</div>
                            </div>
                        `;
                    } else {
                        // 班がいない（空き）の場合
                        slot.className = "monitor-slot empty";
                        slot.innerHTML = `<div class="waiting-message">待機中の班はありません...</div>`;
                    }
                }
            }
        } catch (e) {
            console.error("モニター同期エラー:", e);
        }
    }

    function formatTime(totalSeconds) {
        const minutes = Math.floor(totalSeconds / 60);
        const seconds = totalSeconds % 60;
        return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
    }

    function escapeHtml(str) {
        return str.replace(/[&<>'"]/g, 
            tag => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[tag] || tag)
        );
    }

    // 初回実行 ＆ 2秒ごとに自動更新
    updateDualMonitor();
    setInterval(updateDualMonitor, 2000);
});