from django.urls import path

from . import views

app_name = 'delivery'

urlpatterns = [
    path('', views.board, name='home'),
    path('board/', views.board, name='board'),
    path('board/data/', views.board_partial, name='board_data'),
    path('board/<str:step>/', views.board_action, name='board_action'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('deliveries/', views.deliveries, name='deliveries'),
    path('delivery/<int:pk>/', views.detail, name='detail'),
    path('delivery/<int:pk>/<str:name>/', views.action, name='action'),
    path('profile/', views.profile, name='profile'),
]
