import json
from django.test import TestCase
from django.urls import reverse
from .models import Mystery, Team, GameSlot


class FestivalStartTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        for i in range(1, 10):
            Mystery.objects.create(stage_number=i, title=f'謎{i}', statement=f'問題{i}', answer=f'答え{i}')

    def test_wait_until_manual_start(self):
        r = self.client.post('/', {'passcode': 'テスト班'})
        self.assertRedirects(r, '/ready/')
        team = Team.objects.get(name='テスト班')
        self.assertTrue(team.is_active)
        self.assertIsNone(team.start_time)
        self.assertEqual(team.remaining_seconds, 600)
        self.assertEqual(self.client.get('/player/').url, '/ready/')
        self.client.get('/nfc/register/time/')
        self.assertContains(self.client.get('/ready/'), 'ゲームスタート')
        self.assertFalse(self.client.get('/api/state/テスト班/').json()['has_started'])
        self.assertRedirects(self.client.post('/start/'), '/player/')
        team.refresh_from_db()
        self.assertIsNotNone(team.start_time)
        old_start = team.start_time
        self.assertTrue(self.client.get('/api/state/テスト班/').json()['has_started'])
        self.assertRedirects(self.client.post('/start/'), '/player/')
        team.refresh_from_db()
        self.assertEqual(team.start_time, old_start)
        self.assertEqual(self.client.get('/player/').status_code, 200)

    def test_only_published_complete_sets_are_allocated(self):
        Mystery.objects.filter(stage_number=2).update(is_published=False)
        Mystery.objects.filter(stage_number=5).update(is_published=False)
        self.assertRedirects(self.client.post('/', {'passcode': '班1'}), '/ready/')
        team = Team.objects.get(name='班1')
        self.assertEqual(team.assigned_set, 'C')
        self.assertEqual(len(json.loads(team.assigned_mystery_ids)), 3)
        self.assertEqual(self.client.post('/', {'passcode': '班2'}).status_code, 200)
        self.assertFalse(Team.objects.filter(name='班2').exists())

    def test_second_player_does_not_restart_team(self):
        self.client.post('/', {'passcode': '班A'})
        first = Team.objects.get(name='班A')
        assigned = first.assigned_mystery_ids
        self.client.post('/', {'passcode': '班A'})
        first.refresh_from_db()
        self.assertEqual(first.assigned_mystery_ids, assigned)
        self.assertIsNone(first.start_time)
        self.assertEqual(GameSlot.objects.filter(team=first).count(), 1)

    def test_skill_cannot_be_used_before_start(self):
        self.client.post('/', {'passcode': '班A'})
        self.client.get('/nfc/register/time/')
        r = self.client.get('/nfc/skill/time/')
        self.assertContains(r, 'ゲーム開始後に魔法を使用できます')
        team = Team.objects.get(name='班A')
        self.assertFalse(team.skill_time_used)
