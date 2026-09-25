from django.urls import path
from . import views

app_name = 'content_hub'

urlpatterns = [
    path('', views.catalog_view, name='catalog'),
    path('about/', views.about_view, name='about'),
    path('tutoring/', views.tutoring_view, name='tutoring'),
    path('subject/<slug:slug>/', views.subject_view, name='subject_detail'),
    path('view/<slug:item_slug>/', views.view_content_view, name='view_content'),
    path('stream/<slug:item_slug>/', views.stream_pdf_view, name='stream_pdf'),
]
