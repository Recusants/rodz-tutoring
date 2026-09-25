from django.contrib import admin
from .models import Quiz, Question, Choice, QuizAttempt


class ChoiceInline(admin.TabularInline):
    model = Choice
    extra = 4


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('quiz', 'order', 'text')
    list_filter = ('quiz',)
    inlines = [ChoiceInline]


class QuestionInline(admin.StackedInline):
    model = Question
    extra = 1


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ('title', 'content_item', 'time_limit_minutes', 'pass_percentage', 'question_count')
    inlines = [QuestionInline]


@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = ('student', 'quiz', 'score_percent', 'passed', 'completed_at')
    list_filter = ('passed', 'completed_at')
    search_fields = ('student__email', 'quiz__title')
