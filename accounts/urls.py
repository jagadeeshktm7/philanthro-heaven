from django.urls import path
from . import views

urlpatterns = [
    path('', views.home_view, name='home'),
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('donor/dashboard/', views.donor_dashboard, name='donor_dashboard'),
    path('ngo/dashboard/', views.ngo_dashboard, name='ngo_dashboard'),
    path('beneficiary/dashboard/', views.beneficiary_dashboard, name='beneficiary_dashboard'),
]
