from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from content_hub import views as content_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', content_views.home_view, name='home'),
    path('about/', content_views.about_view, name='about'),
    path('tutoring/', content_views.tutoring_view, name='tutoring'),
    path('content/', include('content_hub.urls')),
    path('accounts/', include('accounts.urls')),
    path('wallet/', include('wallet.urls')),
    path('quizzes/', include('quizzes.urls')),
    path('media/protected_pdfs/<path:filename>', content_views.protected_pdf_guard_view, name='protected_pdf_guard'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
