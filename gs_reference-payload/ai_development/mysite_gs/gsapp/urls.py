from django.urls import path

from . import views

app_name = "gsapp"

urlpatterns = [
    path("", views.home, name="home"),
    path("what-we-do/", views.what_we_do, name="what_we_do"),
    path("insights/", views.insights_list, name="insights_list"),
    path("insights/article/", views.insights_article, name="insights_article"),
    path("insights/podcast/", views.insights_podcast, name="insights_podcast"),
    path("careers/", views.careers, name="careers"),
    path("careers/life/", views.careers_life, name="careers_life"),
    path("our-firm/purpose-and-values/", views.purpose, name="purpose"),
]
