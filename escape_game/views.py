import json
import random

from django.db import IntegrityError, transaction
from django.db.models import F
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .models import GameSlot, Mystery, Team


# A/B/Cそれぞれ3問。管理画面のMystery.stage_numberをこの番号で登録する。
PROBLEM_SETS = {
    'A': [1, 2, 3],
    'B': [4, 5, 6],
    'C': [7, 8, 9],
}
MAX_SIMULTANEOUS_TEAMS = 2


def team_is_cleared(team):
    mysteries = team.get_assigned_mysteries()
    return bool(mysteries) and team.current_stage > len(mysteries)


def release_team_slot(team, mark_inactive=True):
    """班の問題セットと同時プレイ枠を解放する。"""
    GameSlot.objects.filter(team=team).update(team=None, set_code=None)
    if mark_inactive:
        Team.objects.filter(pk=team.pk).update(is_active=False)
        team.is_active = False


def cleanup_finished_slots():
    """時間切れ・クリア済みの班が枠を占有し続けないようにする。"""
    slots = GameSlot.objects.select_related('team').exclude(team__isnull=True)
    for slot in slots:
        team = slot.team
        if not team.is_active or team.remaining_seconds <= 0 or team_is_cleared(team):
            release_team_slot(team)


def reset_team_for_new_game(team):
    """同じ合言葉を新しい回で使う場合に、前回の進行状態を初期化する。"""
    team.current_stage = 1
    team.assigned_set = ''
    team.assigned_mystery_ids = '[]'
    team.is_active = False
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
    team.save()
    team.active_hint_stage = 0
    team.active_hint_elements = []


def start_or_resume_team(team):
    """既存班なら同じ枠で再開。新しい班なら空き枠と未使用セットを割り当てる。"""
    # 2枠を必ず用意する。slot_numberはuniqueなので重複作成されない。
    for number in range(1, MAX_SIMULTANEOUS_TEAMS + 1):
        GameSlot.objects.get_or_create(slot_number=number)

    with transaction.atomic():
        slots = list(GameSlot.objects.select_for_update().order_by('slot_number'))

        # 班がいない枠に残っている問題セットを解放
        GameSlot.objects.filter(team__isnull=True).update(set_code=None)

        # 更新した状態を取得し直す
        slots = list(GameSlot.objects.select_for_update().order_by('slot_number'))

        # 同じ班の別プレイヤー（最大5人）は、既存の割り当てを共有する。
        existing_slot = next((slot for slot in slots if slot.team_id == team.pk), None)
        if existing_slot and team.is_active:
            return True

        # 前回終了済み、または管理者が強制終了した班は新しい回として初期化。
        if existing_slot:
            GameSlot.objects.filter(pk=existing_slot.pk).update(team=None, set_code=None)
        if team.is_active or team.start_time or team.assigned_mystery_ids != '[]':
            reset_team_for_new_game(team)

        free_slots = [slot for slot in slots if slot.team_id is None]
        if not free_slots:
            return False

        used_sets = set(
            GameSlot.objects.filter(team__isnull=False)
            .exclude(set_code__isnull=True)
            .values_list("set_code", flat=True)
        )
        available_sets = [code for code in PROBLEM_SETS if code not in used_sets]

        # 3問そろっているセットだけ候補にする。不足セットへの誤割り当てを防ぐ。
        valid_sets = []
        ids_by_set = {}
        for code in available_sets:
            ids = list(
                Mystery.objects.filter(stage_number__in=PROBLEM_SETS[code])
                .order_by('stage_number')
                .values_list('id', flat=True)
            )
            if len(ids) == 3:
                valid_sets.append(code)
                ids_by_set[code] = ids

        random.shuffle(valid_sets)
        for slot in free_slots:
            for code in list(valid_sets):
                try:
                    # Unique set_codeは、同時ログイン時の二重割り当てに対する最後の防波堤。
                    with transaction.atomic():
                        updated = GameSlot.objects.filter(
                            pk=slot.pk, team__isnull=True, set_code__isnull=True
                        ).update(team=team, set_code=code)
                except IntegrityError:
                    updated = 0

                if updated:
                    team.current_stage = 1
                    team.assigned_set = code
                    team.assigned_mystery_ids = json.dumps(ids_by_set[code])
                    team.is_active = True
                    team.start_time = timezone.now()
                    team.bonus_seconds = 0
                    team.is_paused = False
                    team.paused_at = None
                    team.skill_time_used = False
                    team.skill_ice_used = False
                    team.skill_grass_used = False
                    team.skill_fire_used = False
                    team.skill_water_used = False
                    team.last_event = ''
                    team.save()
                    team.active_hint_stage = 0
                    team.active_hint_elements = []
                    return True

                valid_sets.remove(code)

        return False


def login_view(request):
    error_message = None

    if request.method == 'POST':
        passcode = request.POST.get('passcode', '').strip()
        if passcode:
            cleanup_finished_slots()

            with transaction.atomic():
                team, created = Team.objects.get_or_create(name=passcode)
                if not created:
                    Team.objects.filter(pk=team.pk).update(visitor_count=F('visitor_count') + 1)
                    team.refresh_from_db()

                # 同じ班の5人は既存枠を共有。新しい班は空き枠が必要。
                if start_or_resume_team(team):
                    request.session['team_name'] = team.name
                    return redirect('player')

                if created:
                    team.delete()
                occupied_count = GameSlot.objects.filter(team__isnull=False).count()
                if occupied_count >= MAX_SIMULTANEOUS_TEAMS:
                    error_message = '現在2班がプレイ中です。どちらかの班が終了してから参加してください。'
                else:
                    error_message = '問題セットが不足しています。管理画面でステージ番号1〜9の問題を3問ずつ登録してください。'
        else:
            error_message = '合言葉を入力してください。'

    return render(request, 'escape_game/login.html', {'error_message': error_message})


# プレイヤー画面：スマホごとに設定された属性のテンプレートを表示する
# 属性別HTML・セッションの仕組みは今回変更しない。
def player_view(request):
    team_name = request.session.get('team_name')
    if not team_name:
        return redirect('login')

    team = get_object_or_404(Team, name=team_name)

    if not team.is_active:
        return render(request, 'escape_game/game_over.html', {'team': team})

    if team.remaining_seconds <= 0:
        release_team_slot(team)
        return render(request, 'escape_game/game_over.html', {'team': team})

    assigned_mysteries = team.get_assigned_mysteries()

    if assigned_mysteries and team.current_stage > len(assigned_mysteries):
        release_team_slot(team)
        return render(request, 'escape_game/game_clear.html', {'team': team})

    current_mystery = None
    if 1 <= team.current_stage <= len(assigned_mysteries):
        current_mystery = assigned_mysteries[team.current_stage - 1]

    
    error_message = None

    if request.method == 'POST':
        user_answer = request.POST.get('answer', '').strip().lower()

        if current_mystery and user_answer == current_mystery.answer.strip().lower():
            solved_stage = team.current_stage

            team.current_stage += 1
            team.save(update_fields=['current_stage', 'last_accessed'])

            # 最終問題ならクリア画面へ
            if team.current_stage > len(assigned_mysteries):
                return redirect('game_clear')

            # 正解メッセージ画面用の情報を保存
            request.session['correct_stage'] = solved_stage
            request.session['correct_set'] = team.assigned_set
            request.session['correct_team'] = team.name

            return redirect('correct')

        # 不正解の場合
        error_message = '答えが違うようだ...'


    player_element = request.session.get('player_element', 'normal')

    template_name = 'escape_game/player_normal.html'
    if player_element == 'time':
        template_name = 'escape_game/player_time.html'
    elif player_element == 'grass':
        template_name = 'escape_game/player_grass.html'
    elif player_element == 'fire':
        template_name = 'escape_game/player_fire.html'
    elif player_element == 'ice':
        template_name = 'escape_game/player_ice.html'
    elif player_element == 'water':
        template_name = 'escape_game/player_water.html'

    active_hints = []

    if current_mystery and team.active_hint_stage == team.current_stage:
        hint_settings = {
            'ice': ('❄️ 氷のヒント', current_mystery.hint_ice),
            'grass': ('🌿 草のヒント', current_mystery.hint_grass),
            'fire': ('🔥 炎のヒント', current_mystery.hint_fire),
        }

        for element in team.active_hint_elements:
            if element in hint_settings:
                title, content = hint_settings[element]
                active_hints.append({
                    'title': title,
                    'content': content or 'ヒントはまだ登録されていません。',
                })

    return render(request, template_name, {
        'team': team,
        'mystery': current_mystery,
        'error_message': error_message,
        'total_stages': len(assigned_mysteries),
        'active_hints': active_hints,
    })

def correct_view(request):
    team_name = request.session.get('team_name')
    if not team_name:
        return redirect('login')

    team = get_object_or_404(Team, name=team_name)

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
    assigned_mysteries = team.get_assigned_mysteries()
    total_mysteries = len(assigned_mysteries)
    remaining = team.remaining_seconds
    is_cleared = bool(total_mysteries) and team.current_stage > total_mysteries

    if team.is_active and (remaining <= 0 or is_cleared):
        release_team_slot(team)

    total_allowed_seconds = team.time_limit_seconds + team.bonus_seconds
    target_timestamp = None
    if team.start_time:
        if team.is_paused and team.paused_at:
            elapsed = (team.paused_at - team.start_time).total_seconds()
            rem = max(0, total_allowed_seconds - elapsed)
            target_timestamp = (timezone.now().timestamp() + rem) * 1000
        else:
            target_timestamp = (team.start_time.timestamp() + total_allowed_seconds) * 1000

    return JsonResponse({
        'stage': team.current_stage,
        'time_remaining': remaining,
        'remaining_seconds': remaining,
        'is_paused': team.is_paused,
        'last_event': team.last_event,
        'element': team.element,
        'is_game_over': remaining <= 0 or (not team.is_active and not is_cleared),
        'is_cleared': is_cleared,
        'target_timestamp': target_timestamp,
        'active_hint_stage': team.active_hint_stage,
        'active_hint_elements': team.active_hint_elements,
    })


def monitor_view(request, team_name):
    team = get_object_or_404(Team, name=team_name)
    return render(request, 'escape_game/monitor.html', {'team': team})


def active_teams_api(request):
    cleanup_finished_slots()
    slots = GameSlot.objects.select_related('team').exclude(team__isnull=True).order_by('slot_number')
    teams_data = []
    for slot in slots:
        team = slot.team
        if not team.is_active:
            continue
        assigned_mysteries = team.get_assigned_mysteries()
        teams_data.append({
            'name': team.name,
            'stage': team.current_stage,
            'time_remaining': team.remaining_seconds,
            'is_paused': team.is_paused,
            'is_cleared': team_is_cleared(team),
            'is_game_over': team.remaining_seconds <= 0,
            'assigned_set': team.assigned_set,
        })
    return JsonResponse({'teams': teams_data})


def dual_monitor_view(request):
    return render(request, 'escape_game/dual_monitor.html')


def register_element_nfc(request, element):
    team_name = request.session.get('team_name')
    if not team_name:
        return redirect('login')
    request.session['player_element'] = element
    return redirect('player')


def trigger_skill_nfc(request, element):
    team_name = request.session.get('team_name')
    if not team_name:
        return redirect('login')

    player_element = request.session.get('player_element', 'normal')

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

        if not team.is_active or team.remaining_seconds <= 0:
            msg = 'このゲームはすでに終了しています。'
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
    team_name = request.session.get('team_name')
    if not team_name:
        return redirect('login')

    if request.session.get('player_element') != 'water':
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

        if not team.is_active or team.remaining_seconds <= 0:
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
    team_name = request.session.get('team_name')
    team = get_object_or_404(Team, name=team_name) if team_name else None
    if team:
        release_team_slot(team)
    return render(request, 'escape_game/game_over.html', {'team': team})


def game_clear_view(request):
    team_name = request.session.get('team_name')
    team = get_object_or_404(Team, name=team_name) if team_name else None
    if team:
        release_team_slot(team)
    return render(request, 'escape_game/game_clear.html', {'team': team})


def admin_teams_status_api(request):
    teams = Team.objects.all()
    data = []
    for team in teams:
        secs = team.remaining_seconds
        mins = secs // 60
        seconds = secs % 60
        t = '⏱️' if team.skill_time_used else '・'
        i = '❄️' if team.skill_ice_used else '・'
        g = '🌿' if team.skill_grass_used else '・'
        f = '🔥' if team.skill_fire_used else '・'
        skill_summary = f'時:{t} 氷:{i} 草:{g} 炎:{f}'
        data.append({
            'name': team.name,
            'stage': team.current_stage,
            'remaining_formatted': f'{mins}分 {seconds:02d}秒',
            'skill_summary': skill_summary,
        })
    return JsonResponse({'teams': data})
