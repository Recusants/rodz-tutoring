from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, HttpResponseForbidden, Http404
from django.contrib import messages
from django.db.models import Q
from .models import Subject, ContentItem
from wallet.models import ContentUnlock, StudentWallet
import os


def home_view(request):
    subjects = Subject.objects.all()[:8]
    featured_resources = ContentItem.objects.select_related('subject')[:8]
    return render(request, 'content_hub/home.html', {
        'subjects': subjects,
        'featured_resources': featured_resources,
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

    items = ContentItem.objects.select_related('subject').all()

    if query:
        items = items.filter(Q(title__icontains=query) | Q(description__icontains=query) | Q(subject__name__icontains=query))
    if curriculum:
        items = items.filter(curriculum__icontains=curriculum)
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

    subjects = Subject.objects.all()

    return render(request, 'content_hub/catalog.html', {
        'items': items,
        'subjects': subjects,
        'selected_query': query,
        'selected_curriculum': curriculum,
        'selected_grade': grade,
        'selected_subject': subject_slug,
        'selected_type': content_type,
        'selected_pricing': pricing,
    })


def subject_view(request, slug):
    subject = get_object_or_404(Subject, slug=slug)
    items = ContentItem.objects.filter(subject=subject).order_by('grade', '-created_at')
    return render(request, 'content_hub/subject_detail.html', {
        'subject': subject,
        'items': items,
    })


@login_required
def view_content_view(request, item_slug):
    item = get_object_or_404(ContentItem, slug=item_slug)
    user = request.user

    # Determine access
    has_access = (
        item.is_free or 
        user.is_tutor or 
        user.is_admin_role or 
        user.is_staff or 
        ContentUnlock.objects.filter(user=user, content_item=item).exists()
    )

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
            'watermark_text': f"CONFIDENTIAL • LICENSED TO: {user.email} • RODZ TUTORING",
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

    has_access = (
        item.is_free or 
        user.is_tutor or 
        user.is_admin_role or 
        user.is_staff or 
        ContentUnlock.objects.filter(user=user, content_item=item).exists()
    )

    if not has_access:
        return HttpResponseForbidden("Access Denied: You must unlock this content with coins before viewing.")

    if not item.pdf_file or not os.path.exists(item.pdf_file.path):
        raise Http404("PDF document is currently unavailable.")

    # Stream the file inline with strict cache and security headers
    response = FileResponse(open(item.pdf_file.path, 'rb'), content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{item.slug}.pdf"'
    response['Cache-Control'] = 'private, no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    response['X-Content-Type-Options'] = 'nosniff'
    return response
