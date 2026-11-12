
document.addEventListener('DOMContentLoaded', () => {
    const teamStates = [null, null];

    function formatTime(totalSeconds) {
        totalSeconds = Math.max(0, Math.ceil(totalSeconds));
        const minutes = Math.floor(totalSeconds / 60);
        const seconds = totalSeconds % 60;
        return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
    }

    function escapeHtml(str) {
        return String(str).replace(/[&<>'"]/g,
            tag => ({
                '&': '&amp;',
                '<': '&lt;',
                '>': '&gt;',
                "'": '&#39;',
                '"': '&quot;'
            }[tag])
        );
    }

    function renderMonitor() {
        for (let i = 0; i < 2; i++) {
            const slot = document.getElementById(`slot-${i}`);
            if (!slot) continue;

            const state = teamStates[i];

            if (!state) {
                slot.className = "monitor-slot empty";
                slot.innerHTML =
                    '<div class="waiting-message">待機中の班はありません...</div>';
                continue;
            }

            const team = state.team;

            let remaining = state.remainingSeconds;

            if (!team.is_paused && !team.is_game_over && !team.is_cleared) {
                const elapsed = (Date.now() - state.syncedAt) / 1000;
                remaining = Math.max(0, remaining - elapsed);
            }

            const warningClass = remaining <= 180 ? 'timer-warning' : '';
            const stageText = team.is_cleared
                ? 'CLEAR!'
                : team.is_game_over
                    ? 'GAME OVER'
                    : `STAGE ${team.stage}`;

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
                    <div class="slot-timer ${warningClass}">
                        ${formatTime(remaining)}
                    </div>
                </div>
            `;
        }
    }

    async function updateDualMonitor() {
        try {
            const response = await fetch('/api/active_teams/', {
                cache: 'no-store'
            });

            if (!response.ok) return;

            const data = await response.json();
            const teams = data.teams || [];
            const now = Date.now();

            for (let i = 0; i < 2; i++) {
                const team = teams[i];

                teamStates[i] = team ? {
                    team: team,
                    remainingSeconds: team.time_remaining,
                    syncedAt: now
                } : null;
            }

            renderMonitor();
        } catch (e) {
            console.error('モニター同期エラー:', e);
        }
    }

    // 表示は100ミリ秒ごとに更新
    setInterval(renderMonitor, 100);

    // サーバーとの同期は2秒ごと
    updateDualMonitor();
    setInterval(updateDualMonitor, 2000);
});
