import json

from django.db import models
from django.utils import timezone


class Team(models.Model):
    ELEMENT_CHOICES = [
        ('none', '未設定'),
        ('time', '時間'),
        ('water', '水'),
        ('grass', '草'),
        ('fire', '炎'),
        ('ice', '氷'),
    ]
    SET_CHOICES = [
        ('A', 'Aセット'),
        ('B', 'Bセット'),
        ('C', 'Cセット'),
    ]

    OUTCOME_CHOICES = [
        ('', '進行中・準備中'),
        ('cleared', 'クリア'),
        ('timeout', '時間切れ'),
        ('interrupted', '管理者による中断'),
        ('abandoned', '参加者不在'),
    ]
    name = models.CharField(max_length=100, unique=True)
    run_number = models.PositiveIntegerField(default=1, verbose_name='プレイ回数')
    outcome = models.CharField(max_length=20, choices=OUTCOME_CHOICES, blank=True, default='', verbose_name='終了結果')
    ended_at = models.DateTimeField(null=True, blank=True, verbose_name='終了日時')
    final_solved_at = models.DateTimeField(null=True, blank=True)

    element = models.CharField(max_length=20, choices=ELEMENT_CHOICES, default='none')
    current_stage = models.IntegerField(default=1)

    # この班に割り当てられた問題セットと問題ID
    assigned_set = models.CharField(max_length=1, choices=SET_CHOICES, blank=True, default='')
    assigned_mystery_ids = models.TextField(default='[]', blank=True)

    # ゲーム参加状態
    is_active = models.BooleanField(default=False)
    visitor_count = models.IntegerField(default=1)
    last_accessed = models.DateTimeField(auto_now=True)

    # 時間管理用（10分 = 600秒）
    time_limit_seconds = models.IntegerField(default=600)
    start_time = models.DateTimeField(null=True, blank=True)
    bonus_seconds = models.IntegerField(default=0)
    is_paused = models.BooleanField(default=False)
    paused_at = models.DateTimeField(null=True, blank=True)

    # スキル使用済みフラグ（既存機能を維持）
    skill_time_used = models.BooleanField(default=False)
    skill_ice_used = models.BooleanField(default=False)
    skill_grass_used = models.BooleanField(default=False)
    skill_fire_used = models.BooleanField(default=False)
    skill_water_used = models.BooleanField(default=False)  

    last_event = models.CharField(max_length=100, blank=True, default='')
        # 現在の問題で表示するヒント
    active_hint_stage = models.IntegerField(default=0)
    active_hint_elements = models.JSONField(default=list, blank=True)

    @property
    def remaining_seconds(self):
        if not self.start_time:
            return self.time_limit_seconds

        if self.is_paused and self.paused_at:
            elapsed = int((self.paused_at - self.start_time).total_seconds())
        else:
            elapsed = int((timezone.now() - self.start_time).total_seconds())

        total_limit = self.time_limit_seconds + self.bonus_seconds
        return max(0, total_limit - elapsed)

    def get_assigned_mysteries(self):
        """保存されたIDの順番を保って、割り当て済みの問題を取得する。"""
        try:
            ids = json.loads(self.assigned_mystery_ids or '[]')
            if not ids:
                return []

            preserved_order = models.Case(
                *(models.When(pk=pk, then=position) for position, pk in enumerate(ids)),
                output_field=models.IntegerField(),
            )
            return list(
                Mystery.objects.filter(pk__in=ids).order_by(preserved_order)
            )
        except (TypeError, ValueError, json.JSONDecodeError):
            return []

    def __str__(self):
        return self.name


class GameSlot(models.Model):
    """同時プレイ枠。運営スイッチで3枠以上に増やせる。"""
    slot_number = models.PositiveSmallIntegerField(unique=True)
    team = models.OneToOneField(
        Team,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='game_slot',
    )
    # 重複の可否はFestivalSettingsと割り当て処理で管理する。
    set_code = models.CharField(
        max_length=1,
        choices=Team.SET_CHOICES,
        null=True,
        blank=True,
        unique=False,
    )

    class Meta:
        ordering = ['slot_number']

    def __str__(self):
        if self.team:
            return f"枠{self.slot_number}: {self.team.name} ({self.get_set_code_display()})"
        return f"枠{self.slot_number}: 空き"


class Mystery(models.Model):
    """謎・問題データ。stage_number 1〜9を3問ずつ3セットとして使用する。"""
    stage_number = models.IntegerField(default=1, verbose_name="ステージ番号 / ストック番号")
    title = models.CharField(max_length=100, verbose_name="謎のタイトル")
    statement = models.TextField(verbose_name="問題文（HTMLタグ可）")
    image = models.ImageField(upload_to='mysteries/', blank=True, null=True, verbose_name="謎の画像")
    answer = models.CharField(max_length=100, verbose_name="正解")
    is_published = models.BooleanField(default=True, verbose_name="公開する（完成済み）", help_text="未完成ならチェックを外す。新しく開始する班への出題から除外されます。")

    hint_ice = models.TextField(blank=True, null=True, verbose_name="氷のヒント（単純なヒント）")
    hint_grass = models.TextField(blank=True, null=True, verbose_name="草のヒント（アナグラム等）")
    hint_fire = models.TextField(blank=True, null=True, verbose_name="炎のヒント（燃えた紙の断片など）")

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title}"


class Player(models.Model):
    """ブラウザごとの固定ID。再参加しても同じ番号を使用する。"""
    ELEMENT_CHOICES = Team.ELEMENT_CHOICES
    team = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True, blank=True, related_name='players')
    run_number = models.PositiveIntegerField(default=1)
    element = models.CharField(max_length=20, choices=ELEMENT_CHOICES, default='none')
    last_seen = models.DateTimeField(default=timezone.now)
    final_answer_submitted = models.BooleanField(default=False)

    def __str__(self):
        return f'プレイヤー #{self.pk} ({self.team.name if self.team_id else "未所属"})'


class GameRecord(models.Model):
    """班を再利用・削除しても残る、1プレイごとの記録。"""
    team_pk = models.PositiveIntegerField()
    team_name = models.CharField(max_length=100)
    run_number = models.PositiveIntegerField()
    outcome = models.CharField(max_length=20, choices=Team.OUTCOME_CHOICES)
    assigned_set = models.CharField(max_length=1, blank=True)
    player_ids = models.JSONField(default=list)
    player_count = models.PositiveIntegerField(default=0)
    player_details = models.JSONField(default=list)
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(default=timezone.now)
    elapsed_seconds = models.PositiveIntegerField(default=0)
    reached_stage = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['team_pk', 'run_number'], name='unique_team_play_record')]
        ordering = ['-ended_at']

    def __str__(self):
        return f'{self.team_name} ({self.run_number}回目) - {self.get_outcome_display()}'


class FestivalSettings(models.Model):
    """運営用スイッチ。常にpk=1の1行だけを使用。"""
    allow_extra_teams = models.BooleanField(default=False, verbose_name='2班制限を解除')
    allow_duplicate_sets = models.BooleanField(default=False, verbose_name='同時に同じ問題セットを許可')

    @classmethod
    def current(cls):
        return cls.objects.get_or_create(pk=1)[0]

    def __str__(self):
        return '文化祭運営設定'
