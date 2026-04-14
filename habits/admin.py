from django.contrib import admin
from .models import Habit, HabitLog, HabitSchedule, UserProfile

admin.site.register(Habit)
admin.site.register(HabitLog)
admin.site.register(HabitSchedule)
admin.site.register(UserProfile)