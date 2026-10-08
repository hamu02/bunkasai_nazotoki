import json
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
            
            # 初回ログイン時にスタート時刻を記録
            if not team.start_time:
                team.start_time = timezone.now()
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

    current_mystery = Mystery.objects.filter(stage_number=team.current_stage).first()

    if not current_mystery and team.current_stage > 1:
        return render(request, 'escape_game/game_clear.html', {'team': team})

    error_message = None
    if request.method == 'POST':
        user_answer = request.POST.get('answer', '').strip().lower()
        if current_mystery and user_answer == current_mystery.answer.strip().lower():
            team.current_stage += 1
            team.save()
            return redirect('player')
        else:
            error_message = "答えが違うようだ..."

    template_name = 'escape_game/player_normal.html' # 通常/未設定時
    if team.element == 'time':
        template_name = 'escape_game/player_time.html' # 時間属性用

    elif team.element == 'grass':
        template_name = 'escape_game/player_grass.html'

    elif team.element == 'fire':
        template_name = 'escape_game/player_fire.html'

    elif team.element == 'ice':
            template_name = 'escape_game/player_ice.html'
    # ※今後「水」「火」などが増えたらここに追加

    return render(request, template_name, {
        'team': team,
        'mystery': current_mystery,
        'error_message': error_message,
    })


def get_team_state(request, team_name):
    team = get_object_or_404(Team, name=team_name)
    total_mysteries = Mystery.objects.count()
    
    # 既存のプレイヤー画面が使っている残り秒数プロパティ
    remaining = team.remaining_seconds
    
    # モニターの巻き戻り防止用の「絶対終了時刻（ミリ秒）」を計算
    base_duration_seconds = 1800 # 30分
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
        
        # 🔻 プレイヤー画面が使っているフィールド（旧仕様をそのまま維持）
        'time_remaining': remaining,
        'remaining_seconds': remaining,
        'is_paused': team.is_paused,
        'last_event': team.last_event,
        'element': team.element,
        'is_game_over': remaining <= 0,
        'is_cleared': (team.current_stage > total_mysteries) if total_mysteries > 0 else False,
        
        # 🔻 モニター専用の絶対時刻フィールド
        'target_timestamp': target_timestamp,
    })

# 4. モニター画面用ビュー関数
def monitor_view(request, team_name):
    team = get_object_or_404(Team, name=team_name)
    return render(request, 'escape_game/monitor.html', {'team': team})

# 5. NFC：属性登録用タグにかざした時
def register_element_nfc(request, team_name, element):
    team = get_object_or_404(Team, name=team_name)
    team.element = element
    team.last_event = f"REGISTER_{element.upper()}"
    team.save()
    return render(request, 'escape_game/skill_result.html', {
        'message': f'【{team.get_element_display()}】の属性を獲得した！'
    })

# 6. NFC：スキル発動用タグにかざした時
def trigger_skill_nfc(request, team_name, element):
    team = get_object_or_404(Team, name=team_name)
    
    # 時間延長魔法（ボーナス秒数を増やす）
    if element == 'time' and not team.skill_time_used:
        team.bonus_seconds += 180  # +3分
        team.skill_time_used = True
        team.last_event = "MAGIC_TIME"
        team.save()
        msg = "【時間の魔法】発動！制限時間が3分延長された！"
        
    # 氷の魔法（タイマー停止）
    elif element == 'ice' and not team.skill_ice_used:
        team.is_paused = True
        team.paused_at = timezone.now()
        team.skill_ice_used = True
        team.last_event = "MAGIC_ICE"
        team.save()
        msg = "【氷の魔法】発動！時が凍りついた！"
        
    else:
        msg = "魔法の発動に失敗した…（属性不一致、または使用済み）"

    return render(request, 'escape_game/skill_result.html', {'message': msg})

# views.py

def game_over_view(request):
    team_name = request.session.get('team_name')
    team = get_object_or_404(Team, name=team_name) if team_name else None
    return render(request, 'escape_game/game_over.html', {'team': team})

def game_clear_view(request):
    team_name = request.session.get('team_name')
    team = get_object_or_404(Team, name=team_name) if team_name else None
    return render(request, 'escape_game/game_clear.html', {'team': team})