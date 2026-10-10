from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('login/', views.login_user, name='login'),
    path('work/', views.work_login, name='work_login'),
    path('logout/', views.logout_user, name='logout'),
    path('workspace/', views.choose_workspace, name='choose_workspace'),
    path('register/', views.register_user, name='register'),
    path('products/<int:pk>/', views.products_detail, name='product_detail'),
    path('category/<str:catname>/', views.category, name='category'),
    path('category/<str:catname>/add/', views.add_product, name='add_product'),
    path('search/', views.search, name='search'),
    path('search/suggest/', views.search_suggest, name='search_suggest'),
    path('profile/', views.profile, name='profile'),
    path('admin-stock/', views.stock, name='stock'),
    path('employees/', views.employees, name='employees'),
    path('employees/add/', views.add_employee, name='add_employee'),
    path('set-language/<str:lang_code>/', views.set_language, name='set_language'),
    path('delete-search-history/', views.delete_search_history, name='delete_search_history'),
    path('clear-search-history/', views.clear_search_history, name='clear_search_history'),
]
