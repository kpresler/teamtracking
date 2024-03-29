"""teamtracking URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from teamtracking.teamtracking.admin import admin_site
from django.urls import include, path
from rest_framework import routers
from teamtracking.teamtracking import views

router = routers.DefaultRouter()
router.register(r"users", views.UserViewSet)
router.register(r"groups", views.GroupViewSet)
router.register(r"tcrsquestions", views.TcrsQuestionViewSet)
router.register(r"tcrsresponses", views.TcrsResponseViewSet)
router.register(r"iterations", views.IterationViewSet)
router.register(r"notes", views.NoteViewSet)
router.register(r"teams", views.TeamViewSet)

# Wire up our API using automatic URL routing.
# Additionally, we include login URLs for the browsable API.
urlpatterns = [
    path("admin/", admin_site.urls),
    path("api/", include(router.urls)),
    path("api-auth/", include("rest_framework.urls", namespace="rest_framework")),
    path("loadTCRS", views.loadTCRS, name="loadTCRS"),
    path("", views.index, name="index"),
    path("viewTeamDetails", views.teamDetails, name="viewTeamDetails"),
    path("viewSummary", views.summary, name="viewSummary"),
]
