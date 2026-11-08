from django.urls import path
from . import views

app_name = 'content_hub'

urlpatterns = [
    path('', views.catalog_view, name='catalog'),
    path('about/', views.about_view, name='about'),
    path('contact/', views.contact_view, name='contact'),
    path('how-to/', views.how_to_view, name='how_to'),
    path('how-it-works/', views.how_to_view, name='how_it_works'),
    path('terms/', views.terms_view, name='terms'),
    path('terms-and-conditions/', views.terms_view, name='terms_and_conditions'),
    path('admin/site-content/', views.admin_site_content_view, name='admin_site_content'),
    path('tutoring/', views.tutoring_view, name='tutoring'),
    path('courses/create/', views.tutor_course_create_view, name='tutor_course_create'),
    path('courses/admin/approvals/', views.admin_course_approvals_view, name='admin_course_approvals'),
    path('course/<slug:slug>/', views.course_detail_view, name='course_detail'),
    path('subject/<slug:slug>/', views.subject_view, name='subject_detail'),
    path('view/<slug:item_slug>/', views.view_content_view, name='view_content'),
    path('page/<slug:item_slug>/<int:page_number>/', views.render_pdf_page_view, name='render_pdf_page'),
    path('stream/<slug:item_slug>/', views.stream_pdf_view, name='stream_pdf'),
    path('download/<slug:item_slug>/', views.download_content_view, name='download_content'),
    path('upload/', views.upload_resource_view, name='upload_resource'),
]
