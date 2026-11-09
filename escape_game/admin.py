from django.contrib import admin
from .models import Team, Mystery

@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    # 一覧画面に表示する列（elementを削除し、チーム名・ステージ・残り時間・スキル・来場人数に絞る）
    list_display = (
        'name', 
        'current_stage', 
        'get_remaining_minutes', 
        'visitor_count', 
        'skill_status_summary', 
        'last_accessed', 
        'is_paused'
    )
    
    readonly_fields = (
        'remaining_seconds', 
        'visitor_count', 
        'start_time', 
        'last_accessed'
    )
    
    search_fields = ('name',)
    list_filter = ('is_paused',)

    def get_remaining_minutes(self, obj):
        secs = obj.remaining_seconds
        mins = secs // 60
        s = secs % 60
        return f"{mins}分 {s:02d}秒"
    get_remaining_minutes.short_description = '残り時間'

    def skill_status_summary(self, obj):
        t = "⏱️" if obj.skill_time_used else "・"
        i = "❄️" if obj.skill_ice_used else "・"
        g = "🌿" if obj.skill_grass_used else "・"
        f = "🔥" if obj.skill_fire_used else "・"
        return f"時:{t} 氷:{i} 草:{g} 炎:{f}"
    skill_status_summary.short_description = 'スキル使用状況'

    class Media:
        js = ('escape_game/js/admin_auto_refresh.js',)


@admin.register(Mystery)
class MysteryAdmin(admin.ModelAdmin):
    list_display = ('stage_number', 'title', 'answer')
    fields = ('stage_number', 'title', 'statement', 'image', 'answer', 'hint_ice', 'hint_grass', 'hint_fire')