from django.urls import path
from . import views

app_name = 'quizzes'

urlpatterns = [
    path('<int:quiz_id>/', views.take_quiz_view, name='take_quiz'),
]
