import json
import random
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.utils import timezone
from .models import Team, Mystery

# 1. ログイン（合言葉でスタート）
def login_view(request):
    if request.method == 'POST':
        passcode = request.POST.get('passcode', '').strip()
        if passcode:
            team, created = Team.objects.get_or_create(name=passcode)
            
            # 初回ログイン時にスタート時刻と「ランダム3問の割り当て」を行う
            if not team.start_time:
                team.start_time = timezone.now()
                
                # 全問題のIDを取得してランダムに3問選ぶ
                all_ids = list(Mystery.objects.values_list('id', flat=True))
                selected_ids = random.sample(all_ids, min(3, len(all_ids)))
                team.assigned_mystery_ids = json.dumps(selected_ids)
                team.save()
                
            request.session['team_name'] = team.name
            return redirect('player')
            
    return render(request, 'escape_game/login.html')

# 2. プレイヤー画面
def player_view(request):
    team_name = request.session.get('team_name')
    if not team_name:
        return redirect('login')
        
    team = get_object_or_404(Team, name=team_name)
    
    # タイムアップ判定
    if team.remaining_seconds <= 0:
        return render(request, 'escape_game/game_over.html', {'team': team})

    # 🌟 ここで先に assigned_mysteries を定義する！
    assigned_mysteries = team.get_assigned_mysteries()

    if team.current_stage > len(assigned_mysteries) and len(assigned_mysteries) > 0:
        return render(request, 'escape_game/game_clear.html', {'team': team})

    current_mystery = None
    if 1 <= team.current_stage <= len(assigned_mysteries):
        current_mystery = assigned_mysteries[team.current_stage - 1]

    error_message = None
    if request.method == 'POST':
        user_answer = request.POST.get('answer', '').strip().lower()
        if current_mystery and user_answer == current_mystery.answer.strip().lower():
            team.current_stage += 1
            team.save()
            return redirect('player')
        else:
            error_message = "答えが違うようだ..."

    template_name = 'escape_game/player_normal.html'
    if team.element == 'time':
        template_name = 'escape_game/player_time.html'
    elif team.element == 'grass':
        template_name = 'escape_game/player_grass.html'
    elif team.element == 'fire':
        template_name = 'escape_game/player_fire.html'
    elif team.element == 'ice':
        template_name = 'escape_game/player_ice.html'
    elif team.element == 'water':
        template_name = 'escape_game/player_water.html'

    return render(request, template_name, {
        'team': team,
        'mystery': current_mystery,
        'error_message': error_message,
        'total_stages': len(assigned_mysteries),
    })


def get_team_state(request, team_name):
    team = get_object_or_404(Team, name=team_name)
    assigned_mysteries = team.get_assigned_mysteries()
    total_mysteries = len(assigned_mysteries)
    
    remaining = team.remaining_seconds

    base_duration_seconds = 600 # 基本10分（600秒）
    total_allowed_seconds = base_duration_seconds + team.bonus_seconds
    target_timestamp = None
    
    if team.start_time:
        start_ts = team.start_time.timestamp()
        if team.is_paused and team.paused_at:
            elapsed_before_pause = (team.paused_at - team.start_time).total_seconds()
            rem = max(0, total_allowed_seconds - elapsed_before_pause)
            target_timestamp = (timezone.now().timestamp() + rem) * 1000
        else:
            end_ts = start_ts + total_allowed_seconds
            target_timestamp = end_ts * 1000
            
    return JsonResponse({
        'stage': team.current_stage,
        'time_remaining': remaining,
        'remaining_seconds': remaining,
        'is_paused': team.is_paused,
        'last_event': team.last_event,
        'element': team.element,
        'is_game_over': remaining <= 0,
        'is_cleared': (team.current_stage > total_mysteries) if total_mysteries > 0 else False,
        'target_timestamp': target_timestamp,
    })

def monitor_view(request, team_name):
    team = get_object_or_404(Team, name=team_name)
    return render(request, 'escape_game/monitor.html', {'team': team})

def register_element_nfc(request, element):
    team_name = request.session.get('team_name')
    if not team_name:
        return redirect('login')
        
    team = get_object_or_404(Team, name=team_name)
    team.element = element
    team.last_event = f"REGISTER_{element.upper()}"
    team.save()
    return redirect('player')

def trigger_skill_nfc(request, element):
    team_name = request.session.get('team_name')
    if not team_name:
        return redirect('login')
        
    team = get_object_or_404(Team, name=team_name)
    msg = ""
    active_element = team.element

    assigned_mysteries = team.get_assigned_mysteries()
    current_mystery = assigned_mysteries[team.current_stage - 1] if 0 <= team.current_stage - 1 < len(assigned_mysteries) else None

    if active_element == 'time' and not team.skill_time_used:
        team.bonus_seconds += 120  
        team.skill_time_used = True
        team.last_event = "MAGIC_TIME"
        team.save()
        msg = "【時間の魔法】発動！制限時間が2分延長された！"

    elif active_element == 'ice' and not team.skill_ice_used:
        team.skill_ice_used = True
        team.last_event = "MAGIC_ICE"
        team.save()
        hint = current_mystery.hint_ice if current_mystery and current_mystery.hint_ice else "（この問題の氷のヒントは登録されていません）"
        msg = f"【氷の魔法】発動！単純なヒント：<br><strong>{hint}</strong>"

    elif active_element == 'grass' and not getattr(team, 'skill_grass_used', False):
        team.skill_grass_used = True
        team.last_event = "MAGIC_GRASS"
        team.save()
        hint = current_mystery.hint_grass if current_mystery and current_mystery.hint_grass else "（この問題の草のヒントは登録されていません）"
        msg = f"【草の魔法】発動！アナグラムのヒント：<br><strong>{hint}</strong>"

    elif active_element == 'fire' and not getattr(team, 'skill_fire_used', False):
        team.skill_fire_used = True
        team.last_event = "MAGIC_FIRE"
        team.save()
        hint = current_mystery.hint_fire if current_mystery and current_mystery.hint_fire else "（この問題の炎のヒントは登録されていません）"
        msg = f"【炎の魔法】発動！燃えた紙に隠されたヒント：<br><strong>{hint}</strong>"

    elif active_element == 'water':
        used_count = sum([team.skill_time_used, team.skill_ice_used, team.skill_grass_used, team.skill_fire_used])
        if used_count > 0:
            team.skill_time_used = False
            team.skill_ice_used = False
            team.skill_grass_used = False
            team.skill_fire_used = False
            team.last_event = "MAGIC_WATER"
            team.save()
            msg = "【水の魔法】発動！清らかな水がすべてのスキルの回数を回復させた！"
        else:
            msg = "回復できる使用済みスキルがまだありません…"

    else:
        msg = "魔法の発動に失敗した…（属性が一致していない、またはすでに使用済みです）"

    return render(request, 'escape_game/skill_result.html', {
        'message': msg,
        'team': team
    })

def game_over_view(request):
    team_name = request.session.get('team_name')
    team = get_object_or_404(Team, name=team_name) if team_name else None
    return render(request, 'escape_game/game_over.html', {'team': team})

def game_clear_view(request):
    team_name = request.session.get('team_name')
    team = get_object_or_404(Team, name=team_name) if team_name else None
    return render(request, 'escape_game/game_clear.html', {'team': team})