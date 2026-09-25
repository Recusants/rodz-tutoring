from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Quiz, Question, Choice, QuizAttempt
from wallet.models import ContentUnlock


@login_required
def take_quiz_view(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id)
    user = request.user
    item = quiz.content_item

    # Check unlock status
    has_access = (
        item.is_free or 
        user.is_tutor or 
        user.is_admin_role or 
        user.is_staff or 
        ContentUnlock.objects.filter(user=user, content_item=item).exists()
    )

    if not has_access:
        messages.warning(request, f"Please unlock '{item.title}' with coins to take this quiz.")
        return redirect('content_hub:view_content', item_slug=item.slug)

    questions = quiz.questions.prefetch_related('choices').all()
    total_questions = questions.count()

    if request.method == 'POST':
        correct_count = 0
        detailed_results = []

        for q in questions:
            selected_choice_id = request.POST.get(f'question_{q.id}')
            selected_choice = None
            is_correct = False

            if selected_choice_id:
                try:
                    selected_choice = q.choices.get(id=selected_choice_id)
                    if selected_choice.is_correct:
                        correct_count += 1
                        is_correct = True
                except Choice.DoesNotExist:
                    pass

            correct_choice = q.choices.filter(is_correct=True).first()

            detailed_results.append({
                'question': q,
                'selected_choice': selected_choice,
                'correct_choice': correct_choice,
                'is_correct': is_correct,
                'explanation': q.explanation,
            })

        score_percent = (correct_count / total_questions * 100) if total_questions > 0 else 0
        passed = score_percent >= quiz.pass_percentage

        attempt = QuizAttempt.objects.create(
            student=user,
            quiz=quiz,
            total_questions=total_questions,
            correct_answers=correct_count,
            score_percent=round(score_percent, 1),
            passed=passed
        )

        return render(request, 'quizzes/quiz_result.html', {
            'quiz': quiz,
            'attempt': attempt,
            'detailed_results': detailed_results,
            'score_percent': round(score_percent, 1),
            'passed': passed,
            'total_questions': total_questions,
            'correct_count': correct_count,
        })

    return render(request, 'quizzes/take_quiz.html', {
        'quiz': quiz,
        'questions': questions,
        'total_questions': total_questions,
    })
