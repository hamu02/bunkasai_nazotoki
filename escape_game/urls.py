from django.urls import path
from . import views

urlpatterns = [
    path('', views.login_view, name='login'),
    path('player/', views.player_view, name='player'),
    path('game_over/', views.game_over_view, name='game_over'),   
    path('game_clear/', views.game_clear_view, name='game_clear'),

    path('monitor/', views.dual_monitor_view, name='dual_monitor'),
    path('api/active_teams/', views.active_teams_api, name='active_teams_api'),


    path('api/state/<str:team_name>/', views.get_team_state, name='team_state'),
    path('nfc/register/<str:element>/', views.register_element_nfc, name='register_nfc'),
    path('nfc/skill/<str:element>/', views.trigger_skill_nfc, name='skill_nfc'),

    path('api/admin_teams_status/', views.admin_teams_status_api, name='admin_teams_status_api'),
    path('correct/', views.correct_view, name='correct'),
    path('water/select/', views.water_select_view, name='water_select'),
]