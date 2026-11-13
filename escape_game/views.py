import json
import random

from django.db import IntegrityError, transaction
from django.db.models import F
from datetime import timedelta
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .models import GameSlot, Mystery, Team, Player, GameRecord, FestivalSettings


# A/B/Cそれぞれ3問。管理画面のMystery.stage_numberをこの番号で登録する。
PROBLEM_SETS = {
    'A': [1, 2, 3],
    'B': [4, 5, 6],
    'C': [7, 8, 9],
}
MAX_SIMULTANEOUS_TEAMS = 2


VALID_ELEMENTS = {'time', 'grass', 'fire', 'water', 'ice'}


def get_session_player(request):
    player_id = request.session.get('player_id')
    if not player_id:
        return None
    return Player.objects.select_related('team').filter(pk=player_id).first()


def session_team(request):
    player = get_session_player(request)
    if player and player.team_id and player.run_number == player.team.run_number:
        return player.team
    return None


def touch_player(request):
    player = get_session_player(request)
    if player:
        Player.objects.filter(pk=player.pk).update(last_seen=timezone.now())
    return player


def team_is_cleared(team):
    if team.outcome == 'cleared':
        return True
    return bool(team.get_assigned_mysteries()) and team.current_stage > len(team.get_assigned_mysteries())


def snapshot_players(team):
    players = list(Player.objects.filter(team=team, run_number=team.run_number).order_by('pk'))
    return [dict(id=p.pk, element=p.element, final_answer_submitted=p.final_answer_submitted) for p in players]


def update_record_players(team):
    details = snapshot_players(team)
    GameRecord.objects.filter(team_pk=team.pk, run_number=team.run_number).update(
        player_ids=[p['id'] for p in details], player_count=len(details), player_details=details
    )


def finish_team(team, outcome):
    """終了判定をDBに一度だけ保存し、枠を解放して履歴を作成する。"""
    if outcome not in {'cleared', 'timeout', 'interrupted', 'abandoned'}:
        raise ValueError('invalid outcome')
    with transaction.atomic():
        team = Team.objects.select_for_update().get(pk=team.pk)
        if team.outcome:
            return team
        now = timezone.now()
        team.outcome = outcome
        team.ended_at = now
        team.is_active = False
        if outcome == 'cleared':
            team.final_solved_at = now
        team.save(update_fields=['outcome', 'ended_at', 'is_active', 'final_solved_at', 'last_accessed'])
        details = snapshot_players(team)
        elapsed = max(0, int((now - team.start_time).total_seconds())) if team.start_time else 0
        GameRecord.objects.update_or_create(team_pk=team.pk, run_number=team.run_number, defaults={
            'team_name': team.name, 'outcome': outcome, 'assigned_set': team.assigned_set,
            'player_ids': [p['id'] for p in details], 'player_count': len(details),
            'player_details': details, 'started_at': team.start_time,
            'ended_at': now, 'elapsed_seconds': elapsed, 'reached_stage': team.current_stage,
        })
        GameSlot.objects.filter(team=team).update(team=None, set_code=None)
    return team


def cleanup_finished_slots():
    """終了判定を統一し、放置班は安全な猶予後にアーカイブする。"""
    now = timezone.now()
    # 古い終了済み班に残った枠も解放（既存データとの互換性）。
    GameSlot.objects.filter(team__is_active=False).update(team=None, set_code=None)
    GameSlot.objects.filter(team__isnull=True).exclude(set_code__isnull=True).update(set_code=None)
    for team in Team.objects.filter(is_active=True):
        if team_is_cleared(team):
            finish_team(team, 'cleared')
        elif team.start_time and team.remaining_seconds <= 0:
            finish_team(team, 'timeout')
        else:
            # 準備中15分、開始後5分、全員からアクセスがなければ枠を解放。
            threshold = now - timedelta(minutes=5 if team.start_time else 15)
            latest = Player.objects.filter(team=team, run_number=team.run_number).order_by('-last_seen').first()
            if latest and latest.last_seen < threshold:
                finish_team(team, 'abandoned')
            elif not latest and team.last_accessed < threshold:
                finish_team(team, 'abandoned')


def reset_team_for_new_game(team):
    """履歴を残して同じ合言葉を次のプレイに再利用する。"""
    if team.outcome:
        team.run_number += 1
    team.current_stage = 1
    team.assigned_set = ''
    team.assigned_mystery_ids = '[]'
    team.is_active = False
    team.outcome = ''
    team.ended_at = None
    team.final_solved_at = None
    team.time_limit_seconds = 600
    team.start_time = None
    team.bonus_seconds = 0
    team.is_paused = False
    team.paused_at = None
    team.skill_time_used = False
    team.skill_ice_used = False
    team.skill_grass_used = False
    team.skill_fire_used = False
    team.skill_water_used = False
    team.last_event = ''
    team.active_hint_stage = 0
    team.active_hint_elements = []
    team.save()


def start_or_resume_team(team):
    """参加枠とセットを割り当て。運営スイッチで上限・重複を制御。"""
    for number in range(1, MAX_SIMULTANEOUS_TEAMS + 1):
        GameSlot.objects.get_or_create(slot_number=number)

    with transaction.atomic():
        team = Team.objects.select_for_update().get(pk=team.pk)
        if team.is_active and not team.outcome and GameSlot.objects.filter(team=team).exists():
            return True
        if team.outcome or team.assigned_set or team.start_time:
            reset_team_for_new_game(team)

        config = FestivalSettings.current()
        if not config.allow_extra_teams and GameSlot.objects.filter(team__isnull=False).count() >= MAX_SIMULTANEOUS_TEAMS:
            return False
        slots = list(GameSlot.objects.select_for_update().order_by('slot_number'))
        free_slot = next((slot for slot in slots if slot.team_id is None), None)
        if not free_slot:
            if not config.allow_extra_teams:
                return False
            next_number = max((slot.slot_number for slot in slots), default=0) + 1
            free_slot = GameSlot.objects.create(slot_number=next_number)

        used_sets = set(Team.objects.filter(is_active=True).exclude(pk=team.pk).values_list('assigned_set', flat=True))
        valid_sets = []
        for code, stage_numbers in PROBLEM_SETS.items():
            if not config.allow_duplicate_sets and code in used_sets:
                continue
            ids = list(Mystery.objects.filter(stage_number__in=stage_numbers, is_published=True)
                       .order_by('stage_number').values_list('id', flat=True))
            if len(ids) == 3:
                valid_sets.append((code, ids))
        if not valid_sets:
            return False
        code, ids = random.choice(valid_sets)
        free_slot.team = team
        free_slot.set_code = code
        free_slot.save(update_fields=['team', 'set_code'])
        team.assigned_set = code
        team.assigned_mystery_ids = json.dumps(ids)
        team.is_active = True
        team.start_time = None
        team.save()
        return True


def login_view(request):
    error_message = None
    if request.method == 'POST':
        passcode = request.POST.get('passcode', '').strip()
        if passcode:
            cleanup_finished_slots()
            with transaction.atomic():
                team, created = Team.objects.get_or_create(name=passcode)
                if start_or_resume_team(team):
                    team.refresh_from_db()
                    player = get_session_player(request)
                    if not player:
                        player = Player.objects.create(team=team, run_number=team.run_number)
                    else:
                        # ブラウザIDを引き継ぎ、参加する回の属性は未設定に戻す。
                        player.team = team
                        player.run_number = team.run_number
                        player.element = 'none'
                        player.final_answer_submitted = False
                        player.last_seen = timezone.now()
                        player.save()
                    request.session['player_id'] = player.pk
                    request.session['team_name'] = team.name
                    request.session['player_element'] = 'normal'
                    Team.objects.filter(pk=team.pk).update(visitor_count=F('visitor_count') + 1 if not created else 1)
                    return redirect('player')
                if created:
                    team.delete()
                config = FestivalSettings.current()
                if not config.allow_extra_teams and GameSlot.objects.filter(team__isnull=False).count() >= MAX_SIMULTANEOUS_TEAMS:
                    error_message = '現在2班がプレイ中です。管理画面から上限を解除できます。'
                else:
                    error_message = '使用可能な問題セットがありません。問題の公開設定または問題重複の許可を確認してください。'
        else:
            error_message = '合言葉を入力してください。'
    return render(request, 'escape_game/login.html', {'error_message': error_message})


def ready_view(request):
    return redirect('player')


@require_POST
def start_game_view(request):
    player = get_session_player(request)
    team = session_team(request)
    if not player or not team:
        return redirect('login')
    with transaction.atomic():
        team = Team.objects.select_for_update().get(pk=team.pk)
        player.refresh_from_db()
        if (team.is_active and not team.outcome and team.start_time is None
                and player.element in VALID_ELEMENTS and team.get_assigned_mysteries()):
            team.start_time = timezone.now()
            team.save(update_fields=['start_time', 'last_accessed'])
    return redirect('player')


def player_view(request):
    team = session_team(request)
    player = touch_player(request)
    if not team or not player:
        return redirect('login')
    cleanup_finished_slots()
    team.refresh_from_db()
    player.refresh_from_db()

    assigned_mysteries = team.get_assigned_mysteries()
    total = len(assigned_mysteries)
    error_message = None
    awaiting_personal_finish = team.outcome == 'cleared' and not player.final_answer_submitted

    if team.outcome == 'cleared' and not awaiting_personal_finish:
        return redirect('game_clear')
    if team.outcome and team.outcome != 'cleared':
        return redirect('game_over')

    if team.start_time and not team.outcome and team.remaining_seconds <= 0:
        finish_team(team, 'timeout')
        return redirect('game_over')

    if request.method == 'POST' and team.start_time and player.element in VALID_ELEMENTS:
        answer = request.POST.get('answer', '').strip().casefold()
        with transaction.atomic():
            team = Team.objects.select_for_update().get(pk=team.pk)
            player = Player.objects.select_for_update().get(pk=player.pk)
            assigned_mysteries = team.get_assigned_mysteries()
            total = len(assigned_mysteries)
            if team.outcome == 'cleared' and not player.final_answer_submitted and total:
                if answer == assigned_mysteries[-1].answer.strip().casefold():
                    player.final_answer_submitted = True
                    player.save(update_fields=['final_answer_submitted', 'last_seen'])
                    update_record_players(team)
                    return redirect('game_clear')
                error_message = '答えが違うようだ...'
            elif not team.outcome and team.remaining_seconds <= 0:
                finish_team(team, 'timeout')
                return redirect('game_over')
            elif not team.outcome and 1 <= team.current_stage <= total:
                current = assigned_mysteries[team.current_stage - 1]
                if answer == current.answer.strip().casefold():
                    solved_stage = team.current_stage
                    team.current_stage += 1
                    team.save(update_fields=['current_stage', 'last_accessed'])
                    if team.current_stage > total:
                        player.final_answer_submitted = True
                        player.save(update_fields=['final_answer_submitted'])
                        finish_team(team, 'cleared')
                        return redirect('game_clear')
                    request.session['correct_stage'] = solved_stage
                    request.session['correct_set'] = team.assigned_set
                    request.session['correct_team'] = team.name
                    return redirect('correct')
                error_message = '答えが違うようだ...'

    # 開始前は問題を隠し、元の未設定画面・属性別画面で開始を待つ。
    if not team.start_time:
        current_mystery = None
    elif team.outcome == 'cleared' and awaiting_personal_finish:
        current_mystery = assigned_mysteries[-1] if assigned_mysteries else None
    else:
        current_mystery = assigned_mysteries[team.current_stage - 1] if 1 <= team.current_stage <= total else None

    template_names = {
        'time': 'escape_game/player_time.html', 'grass': 'escape_game/player_grass.html',
        'fire': 'escape_game/player_fire.html', 'ice': 'escape_game/player_ice.html',
        'water': 'escape_game/player_water.html',
    }
    active_hints = []
    if current_mystery and team.active_hint_stage == team.current_stage:
        for element, title, content in [
            ('ice', '❄️ 氷のヒント', current_mystery.hint_ice),
            ('grass', '🌿 草のヒント', current_mystery.hint_grass),
            ('fire', '🔥 炎のヒント', current_mystery.hint_fire),
        ]:
            if element in team.active_hint_elements:
                active_hints.append({'title': title, 'content': content or 'ヒントはまだ登録されていません。'})
    return render(request, template_names.get(player.element, 'escape_game/player_normal.html'), {
        'team': team, 'mystery': current_mystery, 'error_message': error_message,
        'total_stages': total, 'active_hints': active_hints,
        'player': player, 'is_preparing': team.start_time is None,
        'awaiting_personal_finish': awaiting_personal_finish,
        'display_stage': min(team.current_stage, total),
    })


def correct_view(request):
    team = session_team(request)
    if not team:
        return redirect('login')

    if not team.is_active or team.remaining_seconds <= 0:
        return redirect('player')

    stage = request.session.get('correct_stage')
    set_code = request.session.get('correct_set')
    correct_team = request.session.get('correct_team')

    if not stage or set_code != team.assigned_set or correct_team != team.name:
        return redirect('player')

    # ステージがさらに進んでいたら古い正解画面を表示しない
    if team.current_stage != stage + 1:
        request.session.pop('correct_stage', None)
        return redirect('player')

    
    messages = {
        'A': {
            1: {
                'title': '使役動物の証言',
                'message': '嘘つきが隠していた魔法瓶を手に入れ、棚の奥にある文字を調べよう。',
            },
            2: {
                'title': '秘薬の調合',
                'message': '最後の試練だ。黒い布がかけられた椅子を探そう。',
            },
        },
        'B': {
            1: {
                'title': '二つの時の交点',
                'message': '文字のないグリッドが置かれた机へ向かおう。',
            },
            2: {
                'title': '無のグリッドと灯火',
                'message': '最後の試練だ。大量に並んだジャム瓶を調べよう。',
            },
        },
        'C': {
            1: {
                'title': '鹿の角の指針',
                'message': '次の試練だ。部屋にある貝殻を探し、その裏に刻まれた文字を調べよう。',
            },
            2: {
                'title': '海鳴りの暗号',
                'message': '最後の試練だ。棚にある三つの灯火と魔法陣を探そう。',
            },
        },
    }


    info = messages.get(set_code, {}).get(stage)

    if not info:
        return redirect('player')

    if request.method == 'POST':
        request.session.pop('correct_stage', None)
        request.session.pop('correct_set', None)
        request.session.pop('correct_team', None)
        return redirect('player')

    return render(request, 'escape_game/correct.html', {
        'team': team,
        'stage': stage,
        'title': info['title'],
        'message': info['message'],
    })

def get_team_state(request, team_name):
    team = get_object_or_404(Team, name=team_name)
    if team.is_active:
        cleanup_finished_slots()
        team.refresh_from_db()
    player = touch_player(request)
    player_team_mismatch = bool(player and (player.team_id != team.pk or player.run_number != team.run_number))
    if player_team_mismatch:
        player = None
    personal_pending = team.outcome == 'cleared' and player is not None and not player.final_answer_submitted
    remaining = team.remaining_seconds
    allowed = team.time_limit_seconds + team.bonus_seconds
    target = None
    if team.start_time:
        if team.is_paused and team.paused_at:
            rem = max(0, allowed - (team.paused_at - team.start_time).total_seconds())
            target = (timezone.now().timestamp() + rem) * 1000
        else:
            target = (team.start_time.timestamp() + allowed) * 1000
    return JsonResponse({
        'stage': team.current_stage, 'time_remaining': remaining, 'remaining_seconds': remaining,
        'is_paused': team.is_paused, 'has_started': team.start_time is not None,
        'last_event': team.last_event, 'element': player.element if player else 'none',
        'is_game_over': team.outcome in ('timeout', 'interrupted', 'abandoned'),
        'is_cleared': team.outcome == 'cleared' and not personal_pending,
        'team_cleared': team.outcome == 'cleared',
        'player_team_mismatch': player_team_mismatch,
        'awaiting_personal_finish': personal_pending,
        'target_timestamp': target, 'active_hint_stage': team.active_hint_stage,
        'active_hint_elements': team.active_hint_elements,
    })


def monitor_view(request, team_name):
    team = get_object_or_404(Team, name=team_name)
    return render(request, 'escape_game/monitor.html', {'team': team})


def active_teams_api(request):
    cleanup_finished_slots()
    teams_data = []
    for team in Team.objects.filter(is_active=True).order_by('pk'):
        teams_data.append({
            'name': team.name, 'stage': team.current_stage,
            'time_remaining': team.remaining_seconds, 'is_paused': team.is_paused,
            'has_started': team.start_time is not None, 'is_cleared': False,
            'is_game_over': False, 'assigned_set': team.assigned_set,
        })
    return JsonResponse({'teams': teams_data})


def dual_monitor_view(request):
    return render(request, 'escape_game/dual_monitor.html')


def register_element_nfc(request, element):
    team = session_team(request)
    player = get_session_player(request)
    if not team or not player:
        return redirect('login')
    if element not in VALID_ELEMENTS:
        return redirect('player')
    player.element = element
    player.last_seen = timezone.now()
    player.save(update_fields=['element', 'last_seen'])
    request.session['player_element'] = element
    return render(request, 'escape_game/element_acquired.html', {'element': element})


def trigger_skill_nfc(request, element):
    team = session_team(request)
    player = touch_player(request)
    if not team or not player:
        return redirect('login')

    team_name = team.name
    player_element = player.element

    def result(message, team):
        return render(request, 'escape_game/skill_result.html', {
            'message': message,
            'team': team,
        })

    valid_elements = {'time', 'water', 'grass', 'fire', 'ice'}

    if element not in valid_elements or player_element != element:
        team = get_object_or_404(Team, name=team_name)
        return result('この属性の魔法は使用できません。', team)

    # 同じ班の複数端末が同時に操作しても、
    # 使用済み判定と更新をまとめて行う
    with transaction.atomic():
        team = get_object_or_404(
            Team.objects.select_for_update(),
            name=team_name,
        )

        if not team.is_active or team.start_time is None or team.remaining_seconds <= 0:
            msg = 'ゲーム開始後に魔法を使用できます。'
            return result(msg, team)

        assigned_mysteries = team.get_assigned_mysteries()
        current_index = team.current_stage - 1

        if not (0 <= current_index < len(assigned_mysteries)):
            return result('現在、魔法を使用できません。', team)

        current_mystery = assigned_mysteries[current_index]

        if element == 'time':
            if team.skill_time_used:
                msg = '【時間の魔法】すでに使用済みです。'
            else:
                team.bonus_seconds += 120
                team.skill_time_used = True
                team.last_event = 'MAGIC_TIME'
                team.save()
                msg = '【時間の魔法】発動！制限時間が2分延長された！'

        elif element == 'water':
            if team.skill_water_used:
                msg = '【水の魔法】すでに使用済みです。'
            else:
                used_skills = {
                    'time': team.skill_time_used,
                    'grass': team.skill_grass_used,
                    'fire': team.skill_fire_used,
                    'ice': team.skill_ice_used,
                }

                if not any(used_skills.values()):
                    msg = '回復できる使用済みスキルがまだありません。'
                else:
                    # ここでは水のスキルを消費しない
                    # 選択画面で確定したときに消費する
                    return redirect('water_select')

        elif element == 'ice':
            if team.skill_ice_used:
                msg = '【氷の魔法】すでに使用済みです。'
            else:
                team.skill_ice_used = True
                team.last_event = 'MAGIC_ICE'
                if team.active_hint_stage != team.current_stage:
                    team.active_hint_stage = team.current_stage
                    team.active_hint_elements = []

                if element not in team.active_hint_elements:
                    team.active_hint_elements = [
                        *team.active_hint_elements,
                        element,
                    ]
                team.save()
                hint = current_mystery.hint_ice or 'ヒントはまだ登録されていません。'
                msg = f'【氷の魔法】発動！ヒント：{hint}'

        elif element == 'grass':
            if team.skill_grass_used:
                msg = '【草の魔法】すでに使用済みです。'
            else:
                team.skill_grass_used = True
                team.last_event = 'MAGIC_GRASS'
                if team.active_hint_stage != team.current_stage:
                    team.active_hint_stage = team.current_stage
                    team.active_hint_elements = []

                if element not in team.active_hint_elements:
                    team.active_hint_elements = [
                        *team.active_hint_elements,
                        element,
                    ]
                team.save()
                hint = current_mystery.hint_grass or 'ヒントはまだ登録されていません。'
                msg = f'【草の魔法】発動！ヒント：{hint}'

        elif element == 'fire':
            if team.skill_fire_used:
                msg = '【炎の魔法】すでに使用済みです。'
            else:
                team.skill_fire_used = True
                team.last_event = 'MAGIC_FIRE'
                if team.active_hint_stage != team.current_stage:
                    team.active_hint_stage = team.current_stage
                    team.active_hint_elements = []

                if element not in team.active_hint_elements:
                    team.active_hint_elements = [
                        *team.active_hint_elements,
                        element,
                    ]
                team.save()
                hint = current_mystery.hint_fire or 'ヒントはまだ登録されていません。'
                msg = f'【炎の魔法】発動！ヒント：{hint}'

    return result(msg, team)


def water_select_view(request):
    team = session_team(request)
    player = touch_player(request)
    if not team or not player:
        return redirect('login')

    team_name = team.name
    if player.element != 'water':
        return redirect('player')

    skill_fields = {
        'time': ('skill_time_used', '⏳ 時間'),
        'grass': ('skill_grass_used', '🌿 草'),
        'fire': ('skill_fire_used', '🔥 炎'),
        'ice': ('skill_ice_used', '❄️ 氷'),
    }

    with transaction.atomic():
        team = get_object_or_404(
            Team.objects.select_for_update(),
            name=team_name,
        )

        if not team.is_active or team.start_time is None or team.remaining_seconds <= 0:
            return redirect('player')

        if team.skill_water_used:
            return render(request, 'escape_game/skill_result.html', {
                'team': team,
                'message': '【水の魔法】すでに使用済みです。',
            })

        available_skills = [
            {'value': key, 'label': label}
            for key, (field, label) in skill_fields.items()
            if getattr(team, field)
        ]

        if request.method == 'POST':
            selected = request.POST.get('skill')

            if selected in skill_fields:
                field, label = skill_fields[selected]

                if getattr(team, field):
                    setattr(team, field, False)
                    team.skill_water_used = True
                    team.last_event = 'MAGIC_WATER'
                    team.save(update_fields=[
                        field,
                        'skill_water_used',
                        'last_event',
                    ])

                    return render(request, 'escape_game/skill_result.html', {
                        'team': team,
                        'message': f'【水の魔法】発動！{label}のスキルが回復した！',
                    })

            error_message = '回復する属性を選択してください。'
        else:
            error_message = None

    return render(request, 'escape_game/water_select.html', {
        'team': team,
        'available_skills': available_skills,
        'error_message': error_message,
    })


def game_over_view(request):
    team = session_team(request)
    if not team:
        return redirect('login')
    if team.outcome == 'cleared':
        return redirect('player')
    if not team.outcome:
        if team.start_time and team.remaining_seconds <= 0:
            team = finish_team(team, 'timeout')
        else:
            return redirect('player')
    return render(request, 'escape_game/game_over.html', {'team': team})


def game_clear_view(request):
    team = session_team(request)
    player = touch_player(request)
    if not team:
        return redirect('login')
    if team.outcome != 'cleared' or (player and not player.final_answer_submitted):
        return redirect('player')
    return render(request, 'escape_game/game_clear.html', {'team': team})


def admin_teams_status_api(request):
    if not request.user.is_staff:
        return JsonResponse({'error': 'forbidden'}, status=403)
    data = []
    for team in Team.objects.all():
        secs = team.remaining_seconds
        t = '⏱️' if team.skill_time_used else '・'
        i = '❄️' if team.skill_ice_used else '・'
        g = '🌿' if team.skill_grass_used else '・'
        f = '🔥' if team.skill_fire_used else '・'
        data.append({
            'name': team.name, 'stage': team.current_stage,
            'remaining_formatted': f'{secs // 60}分 {secs % 60:02d}秒',
            'skill_summary': f'時:{t} 氷:{i} 草:{g} 炎:{f}',
        })
    return JsonResponse({'teams': data})
