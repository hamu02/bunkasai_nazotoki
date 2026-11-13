import json
from datetime import timedelta
from django.test import TestCase, Client
from django.utils import timezone
from .models import Mystery, Team, GameSlot, Player, GameRecord, FestivalSettings
from .views import finish_team, cleanup_finished_slots


class FestivalOperationsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        for i in range(1, 10):
            Mystery.objects.create(stage_number=i, title=f'謎{i}', statement=f'問題{i}', answer=f'答え{i}')

    def join(self, client=None, name='A班', element='time'):
        client = client or self.client
        response = client.post('/', {'passcode': name})
        self.assertRedirects(response, '/player/')
        if element:
            client.get(f'/nfc/register/{element}/')
        return Team.objects.get(name=name), client

    def start(self, client=None):
        client = client or self.client
        return client.post('/start/')

    def test_unconfigured_screen_and_start_requires_element(self):
        team, c = self.join(element=None)
        self.assertContains(c.get('/player/'), 'まだ属性が未設定')
        self.assertNotContains(c.get('/player/'), '答えを入力')
        self.start()
        team.refresh_from_db()
        self.assertIsNone(team.start_time)
        c.get('/nfc/register/time/')
        self.assertContains(c.get('/player/'), 'ゲームスタート')
        self.start()
        team.refresh_from_db()
        self.assertIsNotNone(team.start_time)
        old = team.start_time
        self.start()
        team.refresh_from_db()
        self.assertEqual(team.start_time, old)

    def test_only_published_sets(self):
        Mystery.objects.filter(stage_number__in=[2, 5]).update(is_published=False)
        team, c = self.join()
        self.assertEqual(team.assigned_set, 'C')
        self.assertEqual(len(json.loads(team.assigned_mystery_ids)), 3)
        response = Client().post('/', {'passcode': 'B班'})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Team.objects.filter(name='B班').exists())

    def test_same_team_multi_players_and_element_duplicates(self):
        team, c1 = self.join()
        c2 = Client()
        self.join(c2, 'A班', 'time')
        self.assertEqual(Player.objects.filter(team=team).count(), 2)
        self.assertEqual(Player.objects.filter(team=team, element='time').count(), 2)
        self.assertNotEqual(c1.session['player_id'], c2.session['player_id'])

    def test_end_outcome_and_archive_one_per_run(self):
        team, c = self.join()
        self.start()
        for stage in range(3):
            team.refresh_from_db()
            mystery = team.get_assigned_mysteries()[stage]
            response = c.post('/player/', {'answer': mystery.answer})
        team.refresh_from_db()
        self.assertEqual(team.outcome, 'cleared')
        self.assertFalse(team.is_active)
        self.assertEqual(GameRecord.objects.filter(team_pk=team.pk).count(), 1)
        self.assertEqual(c.get('/game_over/').url, '/player/')
        self.assertEqual(c.get('/game_clear/').status_code, 200)
        finish_team(team, 'timeout')
        self.assertEqual(GameRecord.objects.filter(team_pk=team.pk).count(), 1)
        self.assertEqual(GameRecord.objects.get(team_pk=team.pk).outcome, 'cleared')

    def test_final_answer_each_person(self):
        team, c1 = self.join()
        c2 = Client()
        self.join(c2, 'A班', 'ice')
        self.start(c1)
        for mystery in team.get_assigned_mysteries():
            c1.post('/player/', {'answer': mystery.answer})
        team.refresh_from_db()
        self.assertEqual(team.outcome, 'cleared')
        self.assertTrue(c1.get('/api/state/A班/').json()['is_cleared'])
        state = c2.get('/api/state/A班/').json()
        self.assertFalse(state['is_cleared'])
        self.assertTrue(state['awaiting_personal_finish'])
        self.assertContains(c2.get('/player/'), 'あなたも最後の答えを入力')
        self.assertRedirects(c2.post('/player/', {'answer': team.get_assigned_mysteries()[-1].answer}), '/game_clear/')
        self.assertTrue(c2.get('/api/state/A班/').json()['is_cleared'])
        self.assertEqual(GameRecord.objects.get(team_pk=team.pk).player_count, 2)

    def test_timeout_not_confused_with_clear(self):
        team, c = self.join()
        self.start()
        Team.objects.filter(pk=team.pk).update(start_time=timezone.now()-timedelta(hours=1))
        state = c.get('/api/state/A班/').json()
        self.assertTrue(state['is_game_over'])
        self.assertFalse(state['is_cleared'])
        self.assertEqual(GameRecord.objects.get(team_pk=team.pk).outcome, 'timeout')

    def test_interrupted_archived(self):
        team, c = self.join()
        finish_team(team, 'interrupted')
        self.assertEqual(GameRecord.objects.get(team_pk=team.pk).outcome, 'interrupted')
        self.assertContains(c.get('/game_over/'), '管理者によりゲームが中断')

    def test_reused_passcode_separate_archive_and_player_id(self):
        team, c = self.join()
        pid = c.session['player_id']
        finish_team(team, 'interrupted')
        self.join(c, 'A班', 'fire')
        team.refresh_from_db()
        self.assertEqual(team.run_number, 2)
        self.assertEqual(c.session['player_id'], pid)
        finish_team(team, 'timeout')
        self.assertEqual(list(GameRecord.objects.filter(team_pk=team.pk).order_by('run_number').values_list('run_number', flat=True)), [1,2])

    def test_limits_and_duplicates_switches(self):
        self.join(name='A班')
        self.join(Client(), name='B班')
        self.assertEqual(Client().post('/', {'passcode': 'C班'}).status_code, 200)
        config = FestivalSettings.current()
        config.allow_extra_teams = True
        config.allow_duplicate_sets = True
        config.save()
        self.join(Client(), name='C班')
        self.join(Client(), name='D班')
        self.assertEqual(Team.objects.filter(is_active=True).count(), 4)
        self.assertEqual(GameSlot.objects.filter(team__isnull=False).count(), 4)

    def test_player_moving_team(self):
        team1, c = self.join(name='A班')
        team2, _ = self.join(Client(), name='B班')
        player = Player.objects.get(pk=c.session['player_id'])
        player.team = team2
        player.run_number = team2.run_number
        player.save()
        self.assertContains(c.get('/player/'), 'B班')

    def test_admin_status_not_public(self):
        self.assertEqual(self.client.get('/api/admin_teams_status/').status_code, 403)

    def test_no_player_inactive_cleanup(self):
        team, c = self.join()
        Player.objects.filter(team=team).update(last_seen=timezone.now()-timedelta(minutes=20))
        cleanup_finished_slots()
        team.refresh_from_db()
        self.assertEqual(team.outcome, 'abandoned')

from django.contrib.auth import get_user_model
from django.urls import reverse

class AdminOperationsTests(TestCase):
    # Inherit fixtures and existing tests; admin tests exercise admin pages.
    def setUp(self):
        self.admin_user = get_user_model().objects.create_superuser('festival_admin', 'admin@example.test', 'temporary-test-password')
        self.client.force_login(self.admin_user)

    def test_team_changelist_switches(self):
        response = self.client.get('/admin/escape_game/team/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '2班の同時プレイ上限を解除')
        self.client.post('/admin/escape_game/team/settings/', {
            'allow_extra_teams': 'on', 'allow_duplicate_sets': 'on',
        })
        settings = FestivalSettings.current()
        self.assertTrue(settings.allow_extra_teams)
        self.assertTrue(settings.allow_duplicate_sets)

    def test_records_readonly_admin(self):
        team = Team.objects.create(name='中断班', is_active=True)
        finish_team(team, 'interrupted')
        record = GameRecord.objects.get(team_pk=team.pk)
        self.assertEqual(self.client.get('/admin/escape_game/gamerecord/').status_code, 200)
        self.assertEqual(self.client.get(f'/admin/escape_game/gamerecord/{record.pk}/change/').status_code, 200)

    def test_admin_interrupt_action_creates_record(self):
        team = Team.objects.create(name='中断班', is_active=True)
        r = self.client.post('/admin/escape_game/team/', {
            'action': 'force_release_teams', '_selected_action': str(team.pk), 'index': '0',
        })
        self.assertEqual(r.status_code, 302)
        self.assertEqual(GameRecord.objects.get(team_pk=team.pk).outcome, 'interrupted')

    def test_player_admin_move_and_element(self):
        team_a = Team.objects.create(name='A班', is_active=True)
        team_b = Team.objects.create(name='B班', is_active=True)
        player = Player.objects.create(team=team_a, element='time')
        response = self.client.post(f'/admin/escape_game/player/{player.pk}/change/', {
            'team': team_b.pk, 'element': 'fire', '_save': 'Save',
        })
        self.assertEqual(response.status_code, 302)
        player.refresh_from_db()
        self.assertEqual(player.team, team_b)
        self.assertEqual(player.element, 'fire')

    def test_admin_team_list_only_active(self):
        active = Team.objects.create(name='進行中', is_active=True)
        finished = Team.objects.create(name='終了済み', is_active=True)
        finish_team(finished, 'interrupted')
        response = self.client.get('/admin/escape_game/team/')
        self.assertContains(response, '進行中')
        self.assertNotContains(response, '終了済み')
