from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from datetime import datetime
from .models import Habit, HabitLog
from .serializers import HabitSerializer, HabitLogSerializer


class HabitViewSet(viewsets.ModelViewSet):
    serializer_class = HabitSerializer
    permission_classes = [IsAuthenticated]  # 🔐 solo usuarios logueados

    def get_queryset(self):
        return Habit.objects.filter(user=self.request.user)  # 👤 solo sus hábitos

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)  # 🔥 asigna el usuario automáticamente

    @action(detail=False, methods=['get'], url_path='by-date')
    def by_date(self, request):
        date_str = request.query_params.get('date')

        if not date_str:
            return Response({"error": "Date is required"}, status=400)

        try:
            date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return Response({"error": "Invalid date format"}, status=400)

        weekday = date.strftime("%A").lower()  # monday, tuesday...

        habits = Habit.objects.filter(user=request.user)

        result = []

        for habit in habits:
            # verificar si el hábito aplica ese día
            if weekday not in habit.days:
                continue

            log = HabitLog.objects.filter(
                habit=habit,
                date=date
            ).first()

            result.append({
                "habit_id": habit.id,
                "name": habit.name,
                "status": log.status if log else "pending"
            })

        return Response(result)

class HabitLogViewSet(viewsets.ModelViewSet):
    serializer_class = HabitLogSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return HabitLog.objects.filter(habit__user=self.request.user)