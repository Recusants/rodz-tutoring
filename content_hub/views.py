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
        import pypdfium2 as pdfium
        total_pages = 1
        if item.pdf_file and os.path.exists(item.pdf_file.path):
            try:
                pdf = pdfium.PdfDocument(item.pdf_file.path)
                total_pages = len(pdf)
                pdf.close()
            except Exception:
                total_pages = 1

        pages_list = list(range(1, total_pages + 1))
        return render(request, 'content_hub/pdf_viewer.html', {
            'item': item,
            'total_pages': total_pages,
            'pages_list': pages_list,
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
def render_pdf_page_view(request, item_slug, page_number):
    """
    Renders an individual PDF page as a high-resolution, watermarked image.
    This eliminates any raw PDF transmission to the client browser, completely
    preventing browser download prompts or download managers (IDM) from downloading PDFs.
    """
    item = get_object_or_404(ContentItem, slug=item_slug)
    user = request.user

    if not user.has_unlocked(item):
        return HttpResponseForbidden("Access Denied: You must unlock this content with coins before viewing.")

    if not item.pdf_file or not os.path.exists(item.pdf_file.path):
        raise Http404("Document page is currently unavailable.")

    import pypdfium2 as pdfium
    from PIL import Image, ImageDraw
    import io

    try:
        pdf = pdfium.PdfDocument(item.pdf_file.path)
        total_pages = len(pdf)
        if page_number < 1 or page_number > total_pages:
            pdf.close()
            raise Http404("Page not found.")

        # Render page at 2x scale for sharp retina reading
        page = pdf[page_number - 1]
        pil_image = page.render(scale=2).to_pil()
        pdf.close()
        width, height = pil_image.size

        # Burn in dynamic security watermark
        overlay = Image.new('RGBA', (width, height), (255, 255, 255, 0))
        draw = ImageDraw.Draw(overlay)
        watermark_text = f"LICENSED TO: {user.email} • RODZ TUTORING • UNAUTHORIZED SHARING PROHIBITED"
        
        # Diagonal watermarks across the page
        draw.text((width // 6, height // 4), watermark_text, fill=(30, 58, 138, 35))
        draw.text((width // 6, height // 2), watermark_text, fill=(30, 58, 138, 42))
        draw.text((width // 6, 3 * height // 4), watermark_text, fill=(30, 58, 138, 35))

        final_image = Image.alpha_composite(pil_image.convert('RGBA'), overlay).convert('RGB')

        buf = io.BytesIO()
        final_image.save(buf, format='JPEG', quality=88, optimize=True)

        response = HttpResponse(buf.getvalue(), content_type='image/jpeg')
        response['Cache-Control'] = 'private, max-age=86400'
        return response
    except Exception as e:
        raise Http404(f"Failed to render page: {e}")


@login_required
def stream_pdf_view(request, item_slug):
    item = get_object_or_404(ContentItem, slug=item_slug)
    user = request.user

    if not user.has_unlocked(item):
        return HttpResponseForbidden("Access Denied: You must unlock this content with coins before viewing.")

    if not item.pdf_file or not os.path.exists(item.pdf_file.path):
        raise Http404("PDF document is currently unavailable.")

    # Redirect to in-app viewer to prevent any accidental direct browser download
    return redirect('content_hub:view_content', item_slug=item.slug)


@login_required
def protected_pdf_guard_view(request, filename):
    """
    Prevents any direct file downloading of PDF files under media/protected_pdfs/.
    If the file belongs to a ContentItem, redirects to the in-app viewer.
    Otherwise returns 403 Forbidden.
    """
    item = ContentItem.objects.filter(pdf_file__icontains=filename).first()
    if item:
        return redirect('content_hub:view_content', item_slug=item.slug)
    return HttpResponseForbidden("Access Denied: Direct PDF downloads are disabled.")

