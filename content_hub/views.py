from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseForbidden, Http404
from django.contrib import messages
from django.db.models import Q, Case, When, Value, IntegerField
from django.utils import timezone
from .models import Subject, ContentItem, Curriculum
from wallet.models import ContentUnlock, StudentWallet
import os


def home_view(request):
    subjects = Subject.objects.all()[:8]
    featured_resources = ContentItem.objects.select_related('subject')[:8]
    
    my_unlocked_items = []
    user_unlocked_ids = set()
    if request.user.is_authenticated:
        active_unlocks = ContentUnlock.objects.filter(user=request.user).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gte=timezone.now())
        ).select_related('content_item', 'content_item__subject')
        user_unlocked_ids = {u.content_item_id for u in active_unlocks}
        my_unlocked_items = [u.content_item for u in active_unlocks]

    return render(request, 'content_hub/home.html', {
        'subjects': subjects,
        'featured_resources': featured_resources,
        'my_unlocked_items': my_unlocked_items,
        'user_unlocked_ids': user_unlocked_ids,
    })


def about_view(request):
    return render(request, 'content_hub/about.html')


def tutoring_view(request):
    subjects = Subject.objects.all()
    return render(request, 'content_hub/tutoring.html', {'subjects': subjects})


def catalog_view(request):
    query = request.GET.get('q', '').strip()
    curriculum = request.GET.get('curriculum', '')
    grade = request.GET.get('grade', '')
    subject_slug = request.GET.get('subject', '')
    content_type = request.GET.get('type', '')
    pricing = request.GET.get('pricing', '')

    items = ContentItem.objects.select_related('subject', 'curriculum_ref').all()

    if query:
        items = items.filter(Q(title__icontains=query) | Q(description__icontains=query) | Q(subject__name__icontains=query))
    if curriculum:
        items = items.filter(
            Q(curriculum__icontains=curriculum) | 
            Q(curriculum_ref__code__iexact=curriculum) | 
            Q(curriculum_ref__name__icontains=curriculum)
        )
    if grade:
        items = items.filter(grade=grade)
    if subject_slug:
        items = items.filter(subject__slug=subject_slug)
    if content_type:
        items = items.filter(content_type=content_type)
    if pricing == 'free':
        items = items.filter(is_free=True)
    elif pricing == 'premium':
        items = items.filter(is_free=False)

    # Student Grade Prioritization & Unlocked Items Tracking
    user_unlocked_ids = set()
    my_unlocked_items = []
    student_grade = None

    if request.user.is_authenticated:
        active_unlocks = ContentUnlock.objects.filter(user=request.user).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gte=timezone.now())
        ).select_related('content_item', 'content_item__subject')
        user_unlocked_ids = {u.content_item_id for u in active_unlocks}
        my_unlocked_items = [u.content_item for u in active_unlocks]

        student_grade = request.user.grade

        # If student has a grade and no specific grade filter was clicked, prioritize their grade!
        if student_grade and not grade:
            items = items.annotate(
                is_student_grade=Case(
                    When(grade=student_grade, then=Value(0)),
                    default=Value(1),
                    output_field=IntegerField()
                )
            ).order_by('is_student_grade', '-id')
        else:
            items = items.order_by('-id')
    else:
        items = items.order_by('-id')

    subjects = Subject.objects.all()
    curricula = Curriculum.objects.filter(is_active=True).order_by('order', 'name')

    return render(request, 'content_hub/catalog.html', {
        'items': items,
        'subjects': subjects,
        'curricula': curricula,
        'selected_query': query,
        'selected_curriculum': curriculum,
        'selected_grade': grade,
        'selected_subject': subject_slug,
        'selected_type': content_type,
        'selected_pricing': pricing,
        'user_unlocked_ids': user_unlocked_ids,
        'my_unlocked_items': my_unlocked_items,
        'student_grade': student_grade,
    })


def subject_view(request, slug):
    subject = get_object_or_404(Subject, slug=slug)
    items = ContentItem.objects.filter(subject=subject).order_by('grade', '-created_at')

    user_unlocked_ids = set()
    if request.user.is_authenticated:
        active_unlocks = ContentUnlock.objects.filter(user=request.user).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gte=timezone.now())
        )
        user_unlocked_ids = {u.content_item_id for u in active_unlocks}

    return render(request, 'content_hub/subject_detail.html', {
        'subject': subject,
        'items': items,
        'user_unlocked_ids': user_unlocked_ids,
    })


@login_required
def view_content_view(request, item_slug):
    item = get_object_or_404(ContentItem, slug=item_slug)
    user = request.user

    # Determine access using helper method (validates active academic year retention)
    has_access = user.has_unlocked(item)

    if not has_access:
        wallet, _ = StudentWallet.objects.get_or_create(user=user)
        return render(request, 'content_hub/content_locked.html', {
            'item': item,
            'wallet': wallet,
        })

    # User has access - route to appropriate protected viewer
    if item.content_type == 'PDF':
        return render(request, 'content_hub/pdf_viewer.html', {
            'item': item,
            'watermark_text': f"LICENSED TO: {user.email} • RODZ TUTORING • STRICTLY CONFIDENTIAL",
        })
    elif item.content_type == 'VIDEO':
        return render(request, 'content_hub/video_viewer.html', {
            'item': item,
        })
    elif item.content_type == 'QUIZ':
        if hasattr(item, 'quiz'):
            return redirect('quizzes:take_quiz', quiz_id=item.quiz.id)
        else:
            messages.info(request, "This quiz is currently being finalized by the tutor.")
            return redirect('content_hub:catalog')

    return redirect('content_hub:catalog')


@login_required
def stream_pdf_view(request, item_slug):
    item = get_object_or_404(ContentItem, slug=item_slug)
    user = request.user

    if not user.has_unlocked(item):
        return HttpResponseForbidden("Access Denied: You must unlock this content with coins before viewing.")

    if not item.pdf_file or not os.path.exists(item.pdf_file.path):
        raise Http404("PDF document is currently unavailable.")

    # Read binary bytes directly and stream as protected octet-stream
    # This prevents download managers and browser download prompts from hijacking the in-app view
    with open(item.pdf_file.path, 'rb') as f:
        pdf_bytes = f.read()

    response = HttpResponse(pdf_bytes, content_type='application/octet-stream')
    response['Content-Disposition'] = 'inline'
    response['Cache-Control'] = 'private, no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    response['X-Content-Type-Options'] = 'nosniff'
    return response
