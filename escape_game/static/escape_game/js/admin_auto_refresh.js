window.addEventListener('DOMContentLoaded', () => {
    if (document.querySelector('.model-team.change-list')) {
        setInterval(async () => {
            try {
                // チーム一覧のデータを取得するAPI（後でビューに作ります）を叩く
                const response = await fetch('/api/admin_teams_status/');
                if (response.ok) {
                    const data = await response.json();
                    
                    // 各チームの行を探して数値をリアルタイムに書き換える
                    data.teams.forEach(t => {
                        // テーブルの行から該当するチーム名を探す
                        const rows = document.querySelectorAll('tr');
                        rows.forEach(row => {
                            const nameCell = row.querySelector('.field-name a');
                            if (nameCell && nameCell.textContent.trim() === t.name) {
                                // ステージ
                                const stageCell = row.querySelector('.field-current_stage');
                                if (stageCell) stageCell.textContent = t.stage;
                                
                                // 残り時間
                                const timeCell = row.querySelector('.field-get_remaining_minutes');
                                if (timeCell) timeCell.textContent = t.remaining_formatted;
                                
                                // スキル使用状況
                                const skillCell = row.querySelector('.field-skill_status_summary');
                                if (skillCell) skillCell.textContent = t.skill_summary;
                            }
                        });
                    });
                }
            } catch (e) {
                // 通信エラー時はサイレント無視
            }
        }, 2000); // 2秒ごとに更新
    }
});