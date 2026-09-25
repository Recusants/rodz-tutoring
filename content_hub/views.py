from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseForbidden, Http404, JsonResponse
from django.contrib import messages
from django.db.models import Q, Case, When, Value, IntegerField
from django.utils import timezone
from .models import (
    Subject, ContentItem, Curriculum, Course, 
    AboutContent, ContactInfo, HowToGuide, HowToStep
)
from .forms import (
    TutorCourseCreateForm, AboutContentForm, ContactInfoForm, HowToStepForm
)
from wallet.models import ContentUnlock, StudentWallet, CourseUnlock
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
    about = AboutContent.get_solo()
    raw_pillars = [p.strip() for p in about.pillars_content.splitlines() if p.strip()]
    parsed_pillars = []
    for line in raw_pillars:
        if ':' in line:
            title, desc = line.split(':', 1)
            parsed_pillars.append({'title': title.strip(), 'desc': desc.strip()})
        else:
            parsed_pillars.append({'title': '', 'desc': line.strip()})

    return render(request, 'content_hub/about.html', {
        'about': about,
        'pillars': parsed_pillars,
    })


def contact_view(request):
    contact = ContactInfo.get_solo()
    submitted = False

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        subject = request.POST.get('subject', '').strip()
        message = request.POST.get('message', '').strip()

        # Handle AJAX submissions with SweetAlert2 response
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            if not name or not email or not message:
                return JsonResponse({'status': 'error', 'message': 'Please provide your name, email, and message.'}, status=400)
            return JsonResponse({
                'status': 'success',
                'message': f'Thank you {name}! Your message has been received. Our advisory team will respond to {email} shortly.'
            })

        if name and email and message:
            messages.success(request, f"Thank you {name}! Your inquiry has been sent successfully.")
            submitted = True
        else:
            messages.error(request, "Please fill in all required fields.")

    return render(request, 'content_hub/contact.html', {
        'contact': contact,
        'submitted': submitted,
    })


def how_to_view(request):
    guides = HowToGuide.objects.filter(is_active=True).prefetch_related('steps').order_by('order', 'title')
    primary_guide = guides.first()
    return render(request, 'content_hub/how_to.html', {
        'guides': guides,
        'primary_guide': primary_guide,
    })


@login_required
def admin_site_content_view(request):
    user = request.user
    if not (user.is_admin_role or user.is_staff or user.is_superuser):
        return HttpResponseForbidden("Access Denied: Admin authorization required.")

    about_obj = AboutContent.get_solo()
    contact_obj = ContactInfo.get_solo()
    guide_obj, _ = HowToGuide.objects.get_or_create(slug='how-it-works', defaults={'title': 'How Rodz Tutoring Works'})
    steps = guide_obj.steps.all().order_by('order', 'step_number')

    is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST.get('is_ajax') == '1'

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'save_about':
            form = AboutContentForm(request.POST, instance=about_obj)
            if form.is_valid():
                form.save()
                if is_ajax:
                    return JsonResponse({'status': 'success', 'message': 'About Us content updated successfully in database!'})
                messages.success(request, 'About Us content updated successfully!')
                return redirect('content_hub:admin_site_content')
            else:
                if is_ajax:
                    return JsonResponse({'status': 'error', 'message': 'Please correct the form errors.', 'errors': form.errors}, status=400)
                messages.error(request, 'Please correct the errors in the About form.')

        elif action == 'save_contact':
            form = ContactInfoForm(request.POST, instance=contact_obj)
            if form.is_valid():
                form.save()
                if is_ajax:
                    return JsonResponse({'status': 'success', 'message': 'Contact information and operating hours updated!'})
                messages.success(request, 'Contact details updated successfully!')
                return redirect('content_hub:admin_site_content')
            else:
                if is_ajax:
                    return JsonResponse({'status': 'error', 'message': 'Please correct the form errors.', 'errors': form.errors}, status=400)
                messages.error(request, 'Please correct the errors in the Contact form.')

        elif action == 'save_step':
            step_id = request.POST.get('step_id')
            step_instance = get_object_or_404(HowToStep, id=step_id) if step_id else None
            form = HowToStepForm(request.POST, instance=step_instance)
            if form.is_valid():
                saved_step = form.save(commit=False)
                saved_step.guide = guide_obj
                saved_step.save()
                if is_ajax:
                    return JsonResponse({
                        'status': 'success', 
                        'message': f"Step '{saved_step.title}' saved successfully!",
                        'step': {
                            'id': saved_step.id,
                            'step_number': saved_step.step_number,
                            'badge': saved_step.badge,
                            'title': saved_step.title,
                            'icon_class': saved_step.icon_class,
                            'description': saved_step.description,
                            'order': saved_step.order,
                            'call_to_action_text': saved_step.call_to_action_text,
                            'call_to_action_url': saved_step.call_to_action_url,
                        }
                    })
                messages.success(request, f"Step '{saved_step.title}' saved!")
                return redirect('content_hub:admin_site_content')
            else:
                if is_ajax:
                    return JsonResponse({'status': 'error', 'message': 'Step form errors.', 'errors': form.errors}, status=400)
                messages.error(request, 'Error saving step.')

        elif action == 'delete_step':
            step_id = request.POST.get('step_id')
            step = get_object_or_404(HowToStep, id=step_id)
            step_title = step.title
            step.delete()
            if is_ajax:
                return JsonResponse({'status': 'success', 'message': f"Step '{step_title}' removed successfully."})
            messages.info(request, f"Step '{step_title}' deleted.")
            return redirect('content_hub:admin_site_content')

        elif action == 'save_guide':
            guide_title = request.POST.get('title', '').strip()
            subtitle = request.POST.get('subtitle', '').strip()
            badge_text = request.POST.get('badge_text', '').strip()
            if guide_title:
                guide_obj.title = guide_title
                guide_obj.subtitle = subtitle
                guide_obj.badge_text = badge_text
                guide_obj.save()
                if is_ajax:
                    return JsonResponse({'status': 'success', 'message': 'Guide header details saved successfully!'})
                messages.success(request, 'Guide details updated.')
                return redirect('content_hub:admin_site_content')

    about_form = AboutContentForm(instance=about_obj)
    contact_form = ContactInfoForm(instance=contact_obj)
    step_form = HowToStepForm(initial={'guide': guide_obj, 'step_number': steps.count() + 1, 'order': steps.count() + 1})

    return render(request, 'accounts/admin_site_content.html', {
        'about_obj': about_obj,
        'contact_obj': contact_obj,
        'guide_obj': guide_obj,
        'steps': steps,
        'about_form': about_form,
        'contact_form': contact_form,
        'step_form': step_form,
    })


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

    # Also load approved courses for bundle shopping
    courses = Course.objects.filter(status='APPROVED').select_related('creator', 'subject').prefetch_related('items')
    if query:
        courses = courses.filter(Q(title__icontains=query) | Q(description__icontains=query) | Q(subject__name__icontains=query))
    if curriculum:
        courses = courses.filter(Q(curriculum__icontains=curriculum) | Q(curriculum_ref__code__iexact=curriculum))
    if grade:
        courses = courses.filter(grade=grade)
    if subject_slug:
        courses = courses.filter(subject__slug=subject_slug)

    subjects = Subject.objects.all()
    curricula = Curriculum.objects.filter(is_active=True).order_by('order', 'name')

    return render(request, 'content_hub/catalog.html', {
        'items': items,
        'courses': courses,
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


def course_detail_view(request, slug):
    course = get_object_or_404(Course.objects.select_related('creator', 'subject').prefetch_related('items'), slug=slug)
    
    # Check permissions if not approved yet
    if course.status != 'APPROVED':
        is_creator = request.user.is_authenticated and course.creator == request.user
        is_admin = request.user.is_authenticated and (request.user.is_admin_role or request.user.is_staff or request.user.is_superuser)
        if not (is_creator or is_admin):
            raise Http404("This course is currently pending admin review.")

    pricing = course.get_pricing_for_user(request.user)
    is_manager = request.user.is_authenticated and (course.creator == request.user or request.user.is_admin_role or request.user.is_staff)

    return render(request, 'content_hub/course_detail.html', {
        'course': course,
        'pricing': pricing,
        'is_manager': is_manager,
    })


@login_required
def tutor_course_create_view(request):
    user = request.user
    if not (user.is_tutor or user.is_admin_role or user.is_staff or user.is_superuser):
        messages.error(request, "Only registered Tutors can create and publish course bundles.")
        return redirect('accounts:dashboard')

    wallet, _ = StudentWallet.objects.get_or_create(user=user)
    tutor_coins = wallet.coins

    if request.method == 'POST':
        form = TutorCourseCreateForm(request.POST)
        if form.is_valid():
            if not wallet.can_afford(50):
                messages.error(request, f"Insufficient coins! You need 50 coins to publish a course for admin review, but only have {wallet.coins} coins.")
                return redirect('wallet:buy_coins')

            course = form.save(commit=False)
            course.creator = user
            course.status = 'PENDING'
            course.creation_fee_coins = 50
            course.save()
            form.save_m2m()

            # Debit publishing fee
            wallet.debit_coins(50, description=f"Course Publishing Submission: {course.title}")

            messages.success(
                request,
                f"🎉 Course '{course.title}' submitted successfully! 50 coins have been deposited. "
                f"Our admin team will review your bundled materials before publishing live."
            )
            return redirect('accounts:dashboard')
        else:
            messages.error(request, "Please review the errors in the course form below.")
    else:
        form = TutorCourseCreateForm()

    return render(request, 'content_hub/tutor_course_create.html', {
        'form': form,
        'tutor_coins': tutor_coins,
    })


@login_required
def admin_course_approvals_view(request):
    user = request.user
    if not (user.is_admin_role or user.is_staff or user.is_superuser):
        return HttpResponseForbidden("Access Denied: Admin authorization required.")

    status_filter = request.GET.get('status', 'PENDING')
    courses_qs = Course.objects.select_related('creator', 'subject', 'reviewed_by').prefetch_related('items')

    if status_filter != 'ALL':
        courses_qs = courses_qs.filter(status=status_filter)

    pending_count = Course.objects.filter(status='PENDING').count()

    if request.method == 'POST':
        action = request.POST.get('action')
        course_id = request.POST.get('course_id')
        notes = request.POST.get('admin_notes', '').strip()

        course = get_object_or_404(Course, id=course_id)

        if action == 'approve':
            course.status = 'APPROVED'
            course.reviewed_by = user
            course.reviewed_at = timezone.now()
            if notes:
                course.admin_notes = notes
            course.save()
            messages.success(request, f"✅ Course '{course.title}' approved and published live in the Resource Hub!")
            return redirect(f"{request.path}?status={status_filter}")

        elif action == 'reject':
            course.status = 'REJECTED'
            course.reviewed_by = user
            course.reviewed_at = timezone.now()
            course.admin_notes = notes or "Does not meet course bundle guidelines."
            course.save()

            # Refund tutor deposit fee
            creator_wallet, _ = StudentWallet.objects.get_or_create(user=course.creator)
            creator_wallet.credit_coins(
                course.creation_fee_coins,
                description=f"Course Submission Refund: {course.title}",
                admin_user=user
            )

            messages.warning(
                request,
                f"❌ Course '{course.title}' rejected. {course.creation_fee_coins} coins refunded to tutor {course.creator.email}."
            )
            return redirect(f"{request.path}?status={status_filter}")

    return render(request, 'content_hub/admin_course_approvals.html', {
        'courses': courses_qs,
        'status_filter': status_filter,
        'pending_count': pending_count,
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

