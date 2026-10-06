from django.db import models
from django.utils import timezone

class Team(models.Model):
    name = models.CharField(max_length=100, unique=True)
    element = models.CharField(max_length=20, default='none') # 属性・役職
    current_stage = models.IntegerField(default=1)
    
    # 時間管理用（30分 ＝ 1800秒）
    time_limit_seconds = models.IntegerField(default=1800)
    start_time = models.DateTimeField(null=True, blank=True) # ログイン（開始）した時刻
    bonus_seconds = models.IntegerField(default=0)          # スキル等で追加された秒数
    is_paused = models.BooleanField(default=False)
    paused_at = models.DateTimeField(null=True, blank=True)   # 停止した時刻
    
    # スキル使用済みフラグ
    skill_time_used = models.BooleanField(default=False)
    skill_ice_used = models.BooleanField(default=False)
    last_event = models.CharField(max_length=100, default='')

    @property
    def remaining_seconds(self):
        """サーバー側で正確な残り秒数をリアルタイム計算するプロパティ"""
        if not self.start_time:
            return self.time_limit_seconds
            
        if self.is_paused:
            # ポーズ中の場合、ポーズした時点での経過時間で固定
            elapsed = int((self.paused_at - self.start_time).total_seconds())
        else:
            # 稼働中の場合、現在時刻との差分から計算
            elapsed = int((timezone.now() - self.start_time).total_seconds())

        total_limit = self.time_limit_seconds + self.bonus_seconds
        return max(0, total_limit - elapsed)


class Mystery(models.Model):
    """謎・問題データを管理するモデル（画像アップロード対応）"""
    stage_number = models.IntegerField(unique=True, verbose_name="ステージ番号 (1, 2, 3...)")
    title = models.CharField(max_length=100, verbose_name="謎のタイトル")
    statement = models.TextField(verbose_name="問題文（HTMLタグ可）")
    image = models.ImageField(upload_to='mysteries/', blank=True, null=True, verbose_name="謎の画像")
    answer = models.CharField(max_length=100, verbose_name="正解")
    
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['stage_number']

    def __str__(self):
        return f"Stage {self.stage_number}: {self.title}"