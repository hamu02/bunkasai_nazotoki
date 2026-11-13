from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [('escape_game', '0011_mystery_is_published')]
    operations = [
        migrations.AddField(model_name='team', name='run_number', field=models.PositiveIntegerField(default=1, verbose_name='プレイ回数')),
        migrations.AddField(model_name='team', name='outcome', field=models.CharField(max_length=20, blank=True, default='', choices=[('', '進行中・準備中'), ('cleared', 'クリア'), ('timeout', '時間切れ'), ('interrupted', '管理者による中断'), ('abandoned', '参加者不在')], verbose_name='終了結果')),
        migrations.AddField(model_name='team', name='ended_at', field=models.DateTimeField(null=True, blank=True, verbose_name='終了日時')),
        migrations.AddField(model_name='team', name='final_solved_at', field=models.DateTimeField(null=True, blank=True)),
        migrations.AlterField(model_name='gameslot', name='set_code', field=models.CharField(max_length=1, blank=True, null=True, choices=[('A', 'Aセット'), ('B', 'Bセット'), ('C', 'Cセット')], unique=False)),
        migrations.CreateModel(name='FestivalSettings', fields=[('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')), ('allow_extra_teams', models.BooleanField(default=False, verbose_name='2班制限を解除')), ('allow_duplicate_sets', models.BooleanField(default=False, verbose_name='同時に同じ問題セットを許可'))]),
        migrations.CreateModel(name='GameRecord', fields=[('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')), ('team_pk', models.PositiveIntegerField()), ('team_name', models.CharField(max_length=100)), ('run_number', models.PositiveIntegerField()), ('outcome', models.CharField(max_length=20, choices=[('', '進行中・準備中'), ('cleared', 'クリア'), ('timeout', '時間切れ'), ('interrupted', '管理者による中断'), ('abandoned', '参加者不在')])), ('assigned_set', models.CharField(max_length=1, blank=True)), ('player_ids', models.JSONField(default=list)), ('player_count', models.PositiveIntegerField(default=0)), ('player_details', models.JSONField(default=list)), ('started_at', models.DateTimeField(null=True, blank=True)), ('ended_at', models.DateTimeField(default=django.utils.timezone.now)), ('elapsed_seconds', models.PositiveIntegerField(default=0)), ('reached_stage', models.PositiveIntegerField(default=1))], options={'ordering': ['-ended_at']}),
        migrations.AddConstraint(model_name='gamerecord', constraint=models.UniqueConstraint(fields=('team_pk', 'run_number'), name='unique_team_play_record')),
        migrations.CreateModel(name='Player', fields=[('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')), ('run_number', models.PositiveIntegerField(default=1)), ('element', models.CharField(max_length=20, default='none', choices=[('none','未設定'),('time','時間'),('water','水'),('grass','草'),('fire','炎'),('ice','氷')])), ('last_seen', models.DateTimeField(default=django.utils.timezone.now)), ('final_answer_submitted', models.BooleanField(default=False)), ('team', models.ForeignKey(null=True, blank=True, on_delete=django.db.models.deletion.SET_NULL, related_name='players', to='escape_game.team'))]),
    ]
