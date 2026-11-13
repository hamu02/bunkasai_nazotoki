from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('escape_game', '0010_team_active_hint_elements_team_active_hint_stage_and_more')]
    operations = [
        migrations.AddField(
            model_name='mystery',
            name='is_published',
            field=models.BooleanField(default=True, verbose_name='公開する（完成済み）', help_text='未完成ならチェックを外す。新しく開始する班への出題から除外されます。'),
        ),
    ]
