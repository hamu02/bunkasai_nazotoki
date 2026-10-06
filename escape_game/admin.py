from django.contrib import admin
from .models import Team, Mystery

@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    # 旧 'time_remaining_seconds' を 'remaining_seconds' に変更
    list_display = ('name', 'element', 'current_stage', 'remaining_seconds', 'is_paused')
    readonly_fields = ('remaining_seconds',)

@admin.register(Mystery)
class MysteryAdmin(admin.ModelAdmin):
    list_display = ('stage_number', 'title', 'answer')