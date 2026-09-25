from django.db import models
from django.conf import settings


class Quiz(models.Model):
    content_item = models.OneToOneField(
        'content_hub.ContentItem', 
        on_delete=models.CASCADE, 
        related_name='quiz'
    )
    title = models.CharField(max_length=255)
    instructions = models.TextField(blank=True, default="Read each question carefully and select the best answer.")
    time_limit_minutes = models.PositiveIntegerField(default=15, help_text="Time limit in minutes (0 for no limit)")
    pass_percentage = models.PositiveIntegerField(default=60, help_text="Pass percentage threshold e.g. 60%")

    def __str__(self):
        return f"Quiz: {self.title} ({self.content_item.grade} - {self.content_item.subject.name})"

    @property
    def question_count(self):
        return self.questions.count()


class Question(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions')
    text = models.TextField()
    explanation = models.TextField(
        blank=True, 
        help_text="Detailed explanation of the correct method or formula shown after completion"
    )
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return f"Q{self.order + 1}: {self.text[:60]}..."


class Choice(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='choices')
    text = models.CharField(max_length=400)
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.text} {'(Correct)' if self.is_correct else ''}"


class QuizAttempt(models.Model):
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='quiz_attempts'
    )
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='attempts')
    total_questions = models.PositiveIntegerField(default=0)
    correct_answers = models.PositiveIntegerField(default=0)
    score_percent = models.FloatField(default=0.0)
    passed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-completed_at']

    def __str__(self):
        status = "PASSED" if self.passed else "FAILED"
        return f"{self.student.email} - {self.quiz.title}: {self.score_percent:.1f}% ({status})"
