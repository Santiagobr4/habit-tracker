from django.db import models
from django.contrib.auth.models import User


class Habit(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    days = models.JSONField()  # ejemplo: ["monday", "wednesday"]

    def __str__(self):
        return self.name


class HabitLog(models.Model):
    STATUS_CHOICES = [
        ('done', 'Done'),
        ('missed', 'Missed'),
        ('skip', 'Skip'),
    ]

    habit = models.ForeignKey(Habit, on_delete=models.CASCADE)
    date = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)

    def __str__(self):
        return f"{self.habit.name} - {self.date}"