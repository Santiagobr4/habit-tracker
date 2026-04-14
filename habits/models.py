from django.db import models
from datetime import date
from django.contrib.auth.models import User


class Habit(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    days = models.JSONField()  # Example: ["monday", "wednesday"]
    start_date = models.DateField(default=date.today)
    is_archived = models.BooleanField(default=False)
    archived_at = models.DateField(null=True, blank=True)

    def __str__(self):
        return self.name


class HabitSchedule(models.Model):
    habit = models.ForeignKey(
        Habit,
        on_delete=models.CASCADE,
        related_name='schedules',
    )
    effective_from = models.DateField()
    days = models.JSONField()

    class Meta:
        unique_together = ['habit', 'effective_from']
        ordering = ['effective_from']

    def __str__(self):
        return f"{self.habit.name} from {self.effective_from}"


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

    class Meta:
        unique_together = ['habit', 'date']


class UserProfile(models.Model):
    GENDER_CHOICES = [
        ('male', 'Male'),
        ('female', 'Female'),
        ('non_binary', 'Non-binary'),
        ('prefer_not_to_say', 'Prefer not to say'),
    ]

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile',
    )
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    avatar_url = models.URLField(blank=True)
    birth_date = models.DateField(null=True, blank=True)
    weight_kg = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    gender = models.CharField(
        max_length=20,
        choices=GENDER_CHOICES,
        default='prefer_not_to_say',
    )

    def __str__(self):
        return f"Profile for {self.user.username}"