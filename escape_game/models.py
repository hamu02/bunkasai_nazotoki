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
    name = models.CharField(max_length=100, unique=True)
    element = models.CharField(max_length=20, choices=ELEMENT_CHOICES, default='none')
    current_stage = models.IntegerField(default=1)

    assigned_mystery_ids = models.TextField(default='[]', blank=True)
    
    # 時間管理用（10分 ＝ 600秒）
    time_limit_seconds = models.IntegerField(default=600)
    start_time = models.DateTimeField(null=True, blank=True) # ログイン（開始）した時刻
    bonus_seconds = models.IntegerField(default=0)          # スキル等で追加された秒数
    is_paused = models.BooleanField(default=False)
    paused_at = models.DateTimeField(null=True, blank=True)   # 停止した時刻
    
    # スキル使用済みフラグ
    skill_time_used = models.BooleanField(default=False)
    skill_ice_used = models.BooleanField(default=False)
    skill_grass_used = models.BooleanField(default=False)
    skill_fire_used = models.BooleanField(default=False)
    
    last_event = models.CharField(max_length=100, default='')

    @property
    def remaining_seconds(self):
        if not self.start_time:
            return self.time_limit_seconds
        if self.is_paused:
            elapsed = int((self.paused_at - self.start_time).total_seconds())
        else:
            elapsed = int((timezone.now() - self.start_time).total_seconds())
        total_limit = self.time_limit_seconds + self.bonus_seconds
        return max(0, total_limit - elapsed)

    def get_assigned_mysteries(self):
        """割り当てられた問題のIDリストからMysteryオブジェクトのリストを順番に取得"""
        try:
            ids = json.loads(self.assigned_mystery_ids)
            # 順序を保持して取得
            preserved = models.Case(*(models.When(pk=pk, then=pos) for pos, pk in enumerate(ids)))
            return list(Mystery.objects.filter(pk__in=ids).order_by(preserved))
        except:
            return []


class Mystery(models.Model):
    """謎・問題データを管理するモデル（20問ストック・各ヒント対応）"""
    stage_number = models.IntegerField(default=1, verbose_name="ステージ番号 / ストック番号")
    title = models.CharField(max_length=100, verbose_name="謎のタイトル")
    statement = models.TextField(verbose_name="問題文（HTMLタグ可）")
    image = models.ImageField(upload_to='mysteries/', blank=True, null=True, verbose_name="謎の画像")
    answer = models.CharField(max_length=100, verbose_name="正解")
    
    # 🌟 各属性のヒント用フィールド
    hint_ice = models.TextField(blank=True, null=True, verbose_name="氷のヒント（単純なヒント）")
    hint_grass = models.TextField(blank=True, null=True, verbose_name="草のヒント（アナグラム等）")
    hint_fire = models.TextField(blank=True, null=True, verbose_name="炎のヒント（燃えた紙の断片など）")
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title}"