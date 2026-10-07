from django.urls import path
from . import views

urlpatterns = [
    path('', views.login_view, name='login'),
    path('player/', views.player_view, name='player'),
    path('game_over/', views.game_over_view, name='game_over'),   
    path('game_clear/', views.game_clear_view, name='game_clear'),
    path('monitor/<str:team_name>/', views.monitor_view, name='monitor'),
    path('api/state/<str:team_name>/', views.get_team_state, name='team_state'),
    path('register/<str:team_name>/<str:element>/', views.register_element_nfc, name='register_nfc'),
    path('skill/<str:team_name>/<str:element>/', views.trigger_skill_nfc, name='skill_nfc'),
]