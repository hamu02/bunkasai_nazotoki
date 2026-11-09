import json
import random
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.utils import timezone
from .models import Team, Mystery

def login_view(request):
    if request.method == 'POST':
        passcode = request.POST.get('passcode', '').strip()
        if passcode:
            team, created = Team.objects.get_or_create(name=passcode)

            if not created:
                team.visitor_count += 1
                team.save()

            # 初回ログイン時に問題セットを割り振る
            if not team.start_time:
                team.start_time = timezone.now()
                
                # 🌟 チームの総数などで1組目（stage 1〜3）か2組目（stage 4〜6）のセットを決定
                total_teams_count = Team.objects.count()
                
                if total_teams_count % 2 == 0:
                    # 1組目のセット（stage_number 1, 2, 3 の問題）
                    selected_ids = list(Mystery.objects.filter(stage_number__in=[1, 2, 3]).order_by('stage_number').values_list('id', flat=True))
                else:
                    # 2組目のセット（stage_number 4, 5, 6 の問題）
                    selected_ids = list(Mystery.objects.filter(stage_number__in=[4, 5, 6]).order_by('stage_number').values_list('id', flat=True))
                
                # 万が一データが取れない場合の安全策（DB全体の最初の3問）
                if not selected_ids:
                    selected_ids = list(Mystery.objects.all().order_by('id').values_list('id', flat=True)[:3])

                team.assigned_mystery_ids = json.dumps(selected_ids)
                team.save()
                
            request.session['team_name'] = team.name
            return redirect('player')
            
    return render(request, 'escape_game/login.html')

# プレイヤー画面：スマホごとに設定された属性のテンプレートを表示する
def player_view(request):
    team_name = request.session.get('team_name')
    if not team_name:
        return redirect('login')
        
    team = get_object_or_404(Team, name=team_name)
    
    if team.remaining_seconds <= 0:
        return render(request, 'escape_game/game_over.html', {'team': team})

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

    # 🌟 このスマホ（セッション）が担当している属性を取得する（初期値はnormal）
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

# 🌟 ① 今アクティブな最大2つのチームのデータを返すAPI
def active_teams_api(request):
    # まだクリアしていなくてゲームオーバーにもなっていない、または直近で動いているチームを最大2つ取得
    # （※ テスト用に直近でアクセスがあった順や、スタートしているチームを抽出）
    active_teams = Team.objects.filter(start_time__isnull=False).order_by('-last_accessed')[:2]
    
    teams_data = []
    for team in active_teams:
        assigned_mysteries = team.get_assigned_mysteries()
        total_mysteries = len(assigned_mysteries)
        remaining = team.remaining_seconds
        
        is_cleared = (team.current_stage > total_mysteries) if total_mysteries > 0 else False
        is_game_over = remaining <= 0
        
        # すでにクリアかゲームオーバーになってから時間が経っているものは除外したい場合はここで弾けますが、
        # まずはシンプルに直近の2チームを返します
        
        teams_data.append({
            'name': team.name,
            'stage': team.current_stage,
            'time_remaining': remaining,
            'is_paused': team.is_paused,
            'is_cleared': is_cleared,
            'is_game_over': is_game_over,
        })
        
    return JsonResponse({'teams': teams_data})

# 🌟 ② 2分割モニター用のHTMLを表示するビュー
def dual_monitor_view(request):
    return render(request, 'escape_game/dual_monitor.html')

# NFCタグを読み取った時：そのスマホ（セッション）の担当属性をセットする
def register_element_nfc(request, element):
    team_name = request.session.get('team_name')
    if not team_name:
        return redirect('login')
        
    # チームモデル全体ではなく、このスマホのセッションに属性を保存する
    request.session['player_element'] = element
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

def admin_teams_status_api(request):
    teams = Team.objects.all()
    data = []
    for team in teams:
        secs = team.remaining_seconds
        mins = secs // 60
        s = secs % 60
        
        t = "⏱️" if team.skill_time_used else "・"
        i = "❄️" if team.skill_ice_used else "・"
        g = "🌿" if team.skill_grass_used else "・"
        f = "🔥" if team.skill_fire_used else "・"
        skill_summary = f"時:{t} 氷:{i} 草:{g} 炎:{f}"
        
        data.append({
            'name': team.name,
            'stage': team.current_stage,
            'remaining_formatted': f"{mins}分 {s:02d}秒",
            'skill_summary': skill_summary,
        })
    return JsonResponse({'teams': data})