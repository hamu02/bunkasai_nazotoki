import json
from django.contrib import admin, messages
from django.db import transaction
from django.http import HttpResponseRedirect
from django.urls import path, reverse
from django.utils.html import format_html

from .models import GameSlot, Mystery, Team, Player, GameRecord, FestivalSettings
from .views import finish_team, PROBLEM_SETS

from django import forms
from django.utils import timezone



@admin.action(description='選択した班を強制終了して問題セットを解放')
def force_release_teams(modeladmin, request, queryset):
    for team in queryset.filter(is_active=True):
        finish_team(team, 'interrupted')
    messages.success(request, '選択した班を中断として記録し、プレイ枠を解放しました。')


@admin.action(description='問題セットをAに変更')
def change_to_set_a(modeladmin, request, queryset):
    change_problem_set(request, queryset, 'A')


@admin.action(description='問題セットをBに変更')
def change_to_set_b(modeladmin, request, queryset):
    change_problem_set(request, queryset, 'B')


@admin.action(description='問題セットをCに変更')
def change_to_set_c(modeladmin, request, queryset):
    change_problem_set(request, queryset, 'C')


def change_problem_set(request, queryset, set_code):
    stage_numbers = {
        'A': [1, 2, 3],
        'B': [4, 5, 6],
        'C': [7, 8, 9],
    }

    changed = 0

    with transaction.atomic():
        for team in queryset.select_for_update():
            mysteries = list(
                Mystery.objects.filter(
                    stage_number__in=stage_numbers[set_code], is_published=True
                ).order_by('stage_number')
            )

            if len(mysteries) != 3:
                messages.error(
                    request,
                    f'{set_code}セットの問題が3問そろっていません。'
                )
                continue

            slot = GameSlot.objects.select_for_update().filter(team=team).first()

            if not slot:
                messages.error(
                    request,
                    f'{team.name}にはプレイ枠がありません。'
                )
                continue

            if not FestivalSettings.current().allow_duplicate_sets and GameSlot.objects.filter(
                set_code=set_code, team__isnull=False
            ).exclude(pk=slot.pk).exists():
                messages.error(
                    request,
                    f'{set_code}セットは別の班が使用中です。'
                )
                continue

            import json

            slot.set_code = set_code
            slot.save(update_fields=['set_code'])

            team.assigned_set = set_code
            team.assigned_mystery_ids = json.dumps(
                [m.id for m in mysteries]
            )
            team.current_stage = 1
            team.save(update_fields=[
                'assigned_set',
                'assigned_mystery_ids',
                'current_stage',
            ])

            changed += 1

    if changed:
        messages.success(
            request,
            f'{changed}班の問題セットを{set_code}に変更しました。'
        )




class TeamAdminForm(forms.ModelForm):
    skill_time_used = forms.BooleanField(
        label='⏳ 時間：使用済み',
        required=False,
    )
    skill_grass_used = forms.BooleanField(
        label='🌿 草：使用済み',
        required=False,
    )
    skill_fire_used = forms.BooleanField(
        label='🔥 炎：使用済み',
        required=False,
    )
    skill_water_used = forms.BooleanField(
        label='💧 水：使用済み',
        required=False,
    )
    skill_ice_used = forms.BooleanField(
        label='❄️ 氷：使用済み',
        required=False,
    )
    assigned_set = forms.ChoiceField(
        label='Assigned set',
        required=False,
        choices=[
            ('A', 'Aセット'),
            ('B', 'Bセット'),
            ('C', 'Cセット'),
        ],
    )

    current_stage = forms.TypedChoiceField(
        label='Current stage',
        choices=[
            ('1', '第1問'),
            ('2', '第2問'),
            ('3', '第3問'),
        ],
        coerce=int,
    )

    remaining_minutes = forms.IntegerField(
        label='残り時間（分）',
        min_value=0,
        max_value=120,
        required=False,
        help_text='空欄なら変更しません。'
    )
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.instance._loaded_assigned_set = self.instance.assigned_set
        self.instance._loaded_current_stage = self.instance.current_stage

    class Meta:
        model = Team
        fields = '__all__'

    def clean(self):
        cleaned_data = super().clean()

        set_code = cleaned_data.get('assigned_set')
        team = self.instance

        if not set_code:
            return cleaned_data

        stage_numbers = {
            'A': [1, 2, 3],
            'B': [4, 5, 6],
            'C': [7, 8, 9],
        }

        if (set_code != team._loaded_assigned_set and Mystery.objects.filter(
            stage_number__in=stage_numbers[set_code], is_published=True
        ).count() != 3):
            raise forms.ValidationError(
                f'{set_code}セットの問題が3問そろっていません。'
            )

        # 他の班が使用中のセットには変更できない
        slot = GameSlot.objects.filter(team=team).first()

        if slot and set_code != team._loaded_assigned_set:
            if not FestivalSettings.current().allow_duplicate_sets and GameSlot.objects.filter(
                set_code=set_code, team__isnull=False
            ).exclude(pk=slot.pk).exists():
                raise forms.ValidationError(
                    f'{set_code}セットは別の班が使用中です。'
                )

        return cleaned_data

    def save(self, commit=True):
        team = super().save(commit=False)

        set_code = self.cleaned_data['assigned_set']
        stage = self.cleaned_data['current_stage']
        minutes = self.cleaned_data.get('remaining_minutes')

        stage_numbers = {
            'A': [1, 2, 3],
            'B': [4, 5, 6],
            'C': [7, 8, 9],
        }

        mysteries = list(
            Mystery.objects.filter(
                stage_number__in=stage_numbers[set_code], is_published=True
            ).order_by('stage_number')
        ) if set_code else []

        # 変更前の問題セット・問題番号
        old_set = self.instance._loaded_assigned_set
        old_stage = self.instance._loaded_current_stage

        team.assigned_set = set_code
        if set_code and (set_code != old_set or team.assigned_mystery_ids in ('', '[]')):
            team.assigned_mystery_ids = json.dumps([m.id for m in mysteries])
        team.current_stage = stage

        # 問題セットか問題番号が変更されたらヒントを消す
        if old_set != set_code or old_stage != stage:
            team.active_hint_stage = 0
            team.active_hint_elements = []

        if minutes is not None:
            team.start_time = timezone.now()
            team.time_limit_seconds = minutes * 60
            team.bonus_seconds = 0
            team.is_paused = False
            team.paused_at = None

        if commit:
            with transaction.atomic():
                team.save()

                slot = GameSlot.objects.filter(team=team).first()
                if slot:
                    slot.set_code = set_code
                    slot.save(update_fields=['set_code'])

            self.save_m2m()

        return team



# 管理画面から選択した班に属性スキルの再使用権を付与する。
# 既存の「使用済み」フラグを戻すだけなのでDB構造は変更しない。
@admin.action(description='⏳ 時間の能力を再付与（再使用可能にする）')
def grant_time_skill(modeladmin, request, queryset):
    count = queryset.update(skill_time_used=False)
    messages.success(request, f'{count}班の時間の能力を再使用可能にしました。')


@admin.action(description='🌿 草の能力を再付与（再使用可能にする）')
def grant_grass_skill(modeladmin, request, queryset):
    count = queryset.update(skill_grass_used=False)
    messages.success(request, f'{count}班の草の能力を再使用可能にしました。')


@admin.action(description='🔥 炎の能力を再付与（再使用可能にする）')
def grant_fire_skill(modeladmin, request, queryset):
    count = queryset.update(skill_fire_used=False)
    messages.success(request, f'{count}班の炎の能力を再使用可能にしました。')


@admin.action(description='💧 水の能力を再付与（再使用可能にする）')
def grant_water_skill(modeladmin, request, queryset):
    count = queryset.update(skill_water_used=False)
    messages.success(request, f'{count}班の水の能力を再使用可能にしました。')


@admin.action(description='❄️ 氷の能力を再付与（再使用可能にする）')
def grant_ice_skill(modeladmin, request, queryset):
    count = queryset.update(skill_ice_used=False)
    messages.success(request, f'{count}班の氷の能力を再使用可能にしました。')


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    form = TeamAdminForm

    fieldsets = (
        ('班・問題の設定', {
            'fields': (
                'name',
                'element',
                'assigned_set',
                'current_stage',
                'is_active',
                'run_number',
                'outcome',
            ),
        }),

        ('⏳ 制限時間の設定', {
            'fields': (
                'remaining_minutes',
                'time_limit_seconds',
                'bonus_seconds',
                'is_paused',
            ),
        }),

        ('✨ 能力の再付与（チェックを外すと再使用可能）', {
            'fields': (
                'skill_time_used',
                'skill_grass_used',
                'skill_fire_used',
                'skill_water_used',
                'skill_ice_used',
            ),
            'description': (
                'チェックを外して保存すると、'
                'その属性のスキルをもう一度使用できます。'
            ),
        }),

        ('その他', {
            'fields': ('last_event',),
            'classes': ('collapse',),
        }),
    )
    list_display = (
        'name',
        'is_active',
        'assigned_set',
        'current_stage',
        'get_remaining_minutes',
        'participant_count',
        'outcome',
        'skill_status_summary',
        'last_accessed',
        'is_paused',
    )
    readonly_fields = ('remaining_seconds', 'visitor_count', 'start_time', 'last_accessed', 'is_active', 'run_number', 'outcome')
    change_list_template = 'admin/escape_game/team/change_list.html'

    def has_delete_permission(self, request, obj=None):
        return False
    search_fields = ('name',)
    list_filter = ('is_active', 'assigned_set', 'is_paused')
    actions = (
    force_release_teams,
    change_to_set_a,
    change_to_set_b,
    change_to_set_c,
    grant_time_skill,
    grant_grass_skill,
    grant_fire_skill,
    grant_water_skill,
    grant_ice_skill,
    )

    def get_queryset(self, request):
        return super().get_queryset(request).filter(is_active=True)

    def get_urls(self):
        custom = [path('settings/', self.admin_site.admin_view(self.settings_view), name='escape_game_team_settings')]
        return custom + super().get_urls()

    def settings_view(self, request):
        if not self.has_change_permission(request):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        if request.method == 'POST':
            config = FestivalSettings.current()
            config.allow_extra_teams = request.POST.get('allow_extra_teams') == 'on'
            config.allow_duplicate_sets = request.POST.get('allow_duplicate_sets') == 'on'
            config.save()
            messages.warning(request, '運営スイッチを更新しました。重複許可中は同じ問題を別の班に出す可能性があります。')
        return HttpResponseRedirect(reverse('admin:escape_game_team_changelist'))

    def changelist_view(self, request, extra_context=None):
        context = dict(extra_context or {})
        context['festival_settings'] = FestivalSettings.current()
        return super().changelist_view(request, extra_context=context)

    @admin.display(description='現在の参加人数')
    def participant_count(self, obj):
        return obj.players.filter(run_number=obj.run_number).count()

    @admin.display(description='残り時間')
    def get_remaining_minutes(self, obj):
        secs = obj.remaining_seconds
        return f'{secs // 60}分 {secs % 60:02d}秒'

    @admin.display(description='スキル使用状況')
    def skill_status_summary(self, obj):
        t = '⏱️' if obj.skill_time_used else '・'
        i = '❄️' if obj.skill_ice_used else '・'
        g = '🌿' if obj.skill_grass_used else '・'
        f = '🔥' if obj.skill_fire_used else '・'
        w = '💧' if obj.skill_water_used else '・'

        return f'時:{t} 氷:{i} 草:{g} 炎:{f} 水:{w}'

    class Media:
        js = ('escape_game/js/admin_auto_refresh.js',)


@admin.register(GameSlot)
class GameSlotAdmin(admin.ModelAdmin):
    list_display = ('slot_number', 'team', 'set_code')
    readonly_fields = ('slot_number', 'team', 'set_code')



@admin.register(Mystery)
class MysteryAdmin(admin.ModelAdmin):
    list_display = (
        'stage_number',
        'title',
        'answer',
        'is_published',
        'hint_status',
    )

    list_filter = ('stage_number', 'is_published')
    list_editable = ('is_published',)
    ordering = ('stage_number',)

    fieldsets = (
        ('問題の基本設定', {
            'fields': (
                'stage_number',
                'title',
                'statement',
                'image',
                'answer',
                'is_published',
            )
        }),
        ('❄️ 氷の魔法：単純なヒント', {
            'fields': ('hint_ice',),
            'description': '問題を解くための普通のヒントを入力します。',
        }),
        ('🌿 草の魔法：アナグラム', {
            'fields': ('hint_grass',),
            'description': '文字を並べ替えるヒントなどを入力します。',
        }),
        ('🔥 炎の魔法：燃えた紙の断片', {
            'fields': ('hint_fire',),
            'description': '燃え残った紙に書かれている文字などを入力します。',
        }),
    )

    @admin.display(description='ヒント登録状況')
    def hint_status(self, obj):
        ice = '❄️' if obj.hint_ice else '－'
        grass = '🌿' if obj.hint_grass else '－'
        fire = '🔥' if obj.hint_fire else '－'
        return f'{ice} {grass} {fire}'



@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ('id', 'team', 'run_number', 'element', 'last_seen', 'final_answer_submitted')
    list_display_links = ('id',)
    list_editable = ('team', 'element')
    list_filter = ('team', 'element')
    search_fields = ('=id', 'team__name')
    readonly_fields = ('run_number', 'last_seen', 'final_answer_submitted')

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return False

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'team':
            kwargs['queryset'] = Team.objects.filter(is_active=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        if obj.team_id:
            obj.run_number = obj.team.run_number
            obj.final_answer_submitted = False
        obj.last_seen = timezone.now()
        super().save_model(request, obj, form, change)

    def save_formset(self, request, form, formset, change):
        super().save_formset(request, form, formset, change)



@admin.register(GameRecord)
class GameRecordAdmin(admin.ModelAdmin):
    list_display = ('team_name', 'run_number', 'outcome', 'player_count', 'assigned_set', 'started_at', 'ended_at', 'elapsed_seconds')
    list_filter = ('outcome', 'assigned_set', 'ended_at')
    search_fields = ('team_name', '=team_pk')
    readonly_fields = ('team_pk', 'team_name', 'run_number', 'outcome', 'assigned_set', 'player_ids', 'player_count', 'player_details', 'started_at', 'ended_at', 'elapsed_seconds', 'reached_stage')
    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False
    def has_view_permission(self, request, obj=None):
        return request.user.is_staff
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(FestivalSettings)
class FestivalSettingsAdmin(admin.ModelAdmin):
    list_display = ('allow_extra_teams', 'allow_duplicate_sets')
    def has_add_permission(self, request):
        return not FestivalSettings.objects.exists()
