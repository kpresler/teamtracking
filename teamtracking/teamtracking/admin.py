from django.contrib import admin

from .models import Iteration, TcrsQuestion
from django.contrib.auth.models import User, Group

# Register your models here.


class MyAdminSite(admin.AdminSite):
    site_header = 'Team Tracking Administration'

admin_site = MyAdminSite(name='myadmin')

admin_site.register(Iteration);
admin_site.register(TcrsQuestion);
admin_site.register(Group)
admin_site.register(User)