from django.urls import path
from . import views

urlpatterns = [
    path('ngo/profile/', views.ngo_profile_view, name='ngo_profile'),
    path('beneficiary/request/new/', views.new_help_request_view, name='new_help_request'),
    path('beneficiary/requests/', views.beneficiary_requests_view, name='beneficiary_requests'),
    path('ngo/requests/open/', views.ngo_open_requests_view, name='ngo_open_requests'),
    path('ngo/requests/accept/<int:request_id>/', views.ngo_accept_request_view, name='ngo_accept_request'),
    path('ngo/requests/accepted/', views.ngo_accepted_requests_view, name='ngo_accepted_requests'),
    path('ngo/requests/complete/<int:request_id>/', views.ngo_complete_request_view, name='ngo_complete_request'),
]
