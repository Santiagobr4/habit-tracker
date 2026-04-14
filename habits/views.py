from datetime import datetime, timedelta
from collections import defaultdict

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView
from django.utils import timezone

from .models import Habit, HabitLog, HabitSchedule, UserProfile
from .serializers import (
    HabitLogSerializer,
    HabitLogUpsertSerializer,
    HabitSerializer,
    CaseInsensitiveTokenObtainPairSerializer,
    RegisterSerializer,
    UserProfileSerializer,
)


def _build_schedule_map(habits):
    schedules = HabitSchedule.objects.filter(habit__in=habits).order_by('effective_from')
    schedule_map = defaultdict(list)
    for schedule in schedules:
        schedule_map[schedule.habit_id].append(schedule)
    return schedule_map


def _days_for_habit_on_date(habit, target_date, schedule_map):
    entries = schedule_map.get(habit.id, [])
    days = habit.days
    for schedule in entries:
        if schedule.effective_from <= target_date:
            days = schedule.days
        else:
            break
    return days


def _metrics_baseline_date(user, habit_list):
    user_start = timezone.localdate() if not user.date_joined else user.date_joined.date()

    if not habit_list:
        return user_start

    first_habit_start = min(h.start_date for h in habit_list)
    return max(user_start, first_habit_start)


def _compute_range_metrics(user, start_date, end_date):
    habits = Habit.objects.filter(user=user)
    habit_list = list(habits)
    baseline = _metrics_baseline_date(user, habit_list)

    if not habit_list:
        return {
            "range": {
                "start_date": str(start_date),
                "end_date": str(end_date),
                "baseline_date": str(baseline),
            },
            "summary": {
                "average_daily_completion": None,
                "active_days": 0,
            },
            "daily": [],
            "weekly": [],
            "monthly": [],
        }

    effective_start = max(start_date, baseline)
    if effective_start > end_date:
        return {
            "range": {
                "start_date": str(start_date),
                "end_date": str(end_date),
                "baseline_date": str(baseline),
            },
            "summary": {
                "average_daily_completion": None,
                "active_days": 0,
            },
            "daily": [],
            "weekly": [],
            "monthly": [],
        }

    dates = []
    cursor = effective_start
    while cursor <= end_date:
        dates.append(cursor)
        cursor += timedelta(days=1)

    schedule_map = _build_schedule_map(habit_list)

    logs = HabitLog.objects.filter(
        habit__user=user,
        date__range=(effective_start, end_date),
    )
    logs_map = {(log.habit_id, log.date): log.status for log in logs}

    daily_rows = []
    weekly_agg = defaultdict(lambda: {"done": 0, "total": 0})
    monthly_agg = defaultdict(lambda: {"done": 0, "total": 0})

    for current_date in dates:
        done_count = 0
        total_count = 0
        weekday = current_date.strftime("%A").lower()

        for habit in habit_list:
            if current_date < habit.start_date:
                continue

            active_days = _days_for_habit_on_date(habit, current_date, schedule_map)
            if weekday not in active_days:
                continue

            total_count += 1
            status_value = logs_map.get((habit.id, current_date))
            if status_value == "done":
                done_count += 1

        completion = round((done_count / total_count) * 100, 0) if total_count else None
        date_key = str(current_date)
        week_start = current_date - timedelta(days=current_date.weekday())
        month_key = current_date.strftime("%Y-%m")

        daily_rows.append(
            {
                "date": date_key,
                "completion": completion,
                "done": done_count,
                "total": total_count,
            }
        )

        weekly_agg[str(week_start)]["done"] += done_count
        weekly_agg[str(week_start)]["total"] += total_count
        monthly_agg[month_key]["done"] += done_count
        monthly_agg[month_key]["total"] += total_count

    weekly_rows = []
    for week_start, stats in sorted(weekly_agg.items()):
        total = stats["total"]
        completion = round((stats["done"] / total) * 100, 0) if total else None
        weekly_rows.append(
            {
                "start_date": week_start,
                "label": f"Week of {week_start}",
                "completion": completion,
                "done": stats["done"],
                "total": total,
            }
        )

    monthly_rows = []
    for month, stats in sorted(monthly_agg.items()):
        total = stats["total"]
        completion = round((stats["done"] / total) * 100, 0) if total else None
        monthly_rows.append(
            {
                "month": month,
                "label": month,
                "completion": completion,
                "done": stats["done"],
                "total": total,
            }
        )

    summary_values = [d["completion"] for d in daily_rows if d["total"] > 0]
    summary_average = round(sum(summary_values) / len(summary_values), 0) if summary_values else None

    return {
        "range": {
            "start_date": str(start_date),
            "end_date": str(end_date),
            "baseline_date": str(baseline),
        },
        "summary": {
            "average_daily_completion": summary_average,
            "active_days": len(summary_values),
        },
        "daily": daily_rows,
        "weekly": weekly_rows,
        "monthly": monthly_rows,
    }


def _compute_habit_streaks(habit, schedule_map, logs_map, end_date):
    applicable_dates = []
    cursor = habit.start_date

    while cursor <= end_date:
        weekday = cursor.strftime("%A").lower()
        active_days = _days_for_habit_on_date(habit, cursor, schedule_map)
        if weekday in active_days:
            applicable_dates.append(cursor)
        cursor += timedelta(days=1)

    if not applicable_dates:
        return {"streak_current": 0, "streak_best": 0}

    best_streak = 0
    running = 0
    for current_date in applicable_dates:
        status_value = logs_map.get((habit.id, str(current_date)))
        if status_value == "done":
            running += 1
            best_streak = max(best_streak, running)
        else:
            running = 0

    current_streak = 0
    for current_date in reversed(applicable_dates):
        status_value = logs_map.get((habit.id, str(current_date)))
        if status_value == "done":
            current_streak += 1
        else:
            break

    return {
        "streak_current": current_streak,
        "streak_best": best_streak,
    }


class HabitViewSet(viewsets.ModelViewSet):
    serializer_class = HabitSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Habit.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=False, methods=['get'], url_path='by-date')
    def by_date(self, request):
        date_str = request.query_params.get('date')

        if not date_str:
            return Response({"error": "Date is required"}, status=400)

        try:
            date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return Response({"error": "Invalid date format"}, status=400)

        weekday = date.strftime("%A").lower()

        habits = list(self.get_queryset())
        result = []
        schedule_map = _build_schedule_map(habits)

        logs = HabitLog.objects.filter(
            habit__user=request.user,
            date=date
        )
        logs_map = {log.habit_id: log for log in logs}

        for habit in habits:
            if date < habit.start_date:
                continue

            if weekday not in _days_for_habit_on_date(habit, date, schedule_map):
                continue

            log = logs_map.get(habit.id)

            result.append({
                "habit_id": habit.id,
                "name": habit.name,
                "status": log.status if log else "pending"
            })

        return Response(result)

    @action(detail=False, methods=['get'], url_path='weekly')
    def weekly(self, request):
        start_date_str = request.query_params.get('start_date')

        if not start_date_str:
            return Response({"error": "start_date is required"}, status=400)

        try:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        except ValueError:
            return Response({"error": "Invalid date format"}, status=400)

        week_dates = [start_date + timedelta(days=i) for i in range(7)]
        habits = list(self.get_queryset())
        result = []
        schedule_map = _build_schedule_map(habits)

        logs = HabitLog.objects.filter(
            habit__user=request.user,
            date__range=(week_dates[0], week_dates[-1])
        )

        logs_map = {(log.habit_id, str(log.date)): log for log in logs}

        daily_stats = {str(date): {"done": 0, "total": 0} for date in week_dates}

        for habit in habits:
            week_data = {}

            total_applicable = 0
            total_done = 0

            for date in week_dates:
                weekday = date.strftime("%A").lower()
                date_str = str(date)

                if date < habit.start_date:
                    week_data[date_str] = "skip"
                    continue

                if weekday not in _days_for_habit_on_date(habit, date, schedule_map):
                    week_data[date_str] = "skip"
                    continue

                total_applicable += 1
                daily_stats[date_str]["total"] += 1

                log = logs_map.get((habit.id, date_str))

                if log:
                    week_data[date_str] = log.status

                    if log.status == "done":
                        total_done += 1
                        daily_stats[date_str]["done"] += 1
                else:
                    week_data[date_str] = "pending"

            completion_rate = (
                (total_done / total_applicable) * 100
                if total_applicable > 0 else 100
            )

            streaks = _compute_habit_streaks(
                habit,
                schedule_map,
                logs_map,
                timezone.localdate(),
            )

            result.append({
                "habit_id": habit.id,
                "name": habit.name,
                "days": _days_for_habit_on_date(habit, timezone.localdate(), schedule_map),
                "week": week_data,
                "completion_rate": round(completion_rate, 0),
                "streak_current": streaks["streak_current"],
                "streak_best": streaks["streak_best"],
            })

        baseline = _metrics_baseline_date(request.user, habits)
        daily_percentages = {}

        for date, stats in daily_stats.items():
            total = stats["total"]
            done = stats["done"]
            date_obj = datetime.strptime(date, "%Y-%m-%d").date()

            if date_obj < baseline:
                daily_percentages[date] = None
                continue

            if total > 0:
                daily_percentages[date] = round((done / total) * 100, 0)
            else:
                daily_percentages[date] = None

        valid_days = [
            v for d, v in daily_percentages.items()
            if daily_stats[d]["total"] > 0 and v is not None
        ]

        average_completion = round(
            sum(valid_days) / len(valid_days),
            0
        ) if valid_days else None

        return Response({
            "habits": result,
            "daily_percentages": daily_percentages,
            "average_completion": average_completion,
            "baseline_date": str(baseline),
        })

    @action(detail=False, methods=['get'], url_path='tracker-metrics')
    def tracker_metrics(self, request):
        today = timezone.localdate()
        week_start = today - timedelta(days=today.weekday())

        payload = _compute_range_metrics(request.user, week_start, today)

        today_row = next(
            (row for row in payload["daily"] if row["date"] == str(today)),
            {"date": str(today), "completion": None, "done": 0, "total": 0},
        )
        week_rows = payload.get("weekly") or []
        week_completion = week_rows[-1]["completion"] if week_rows else None

        return Response(
            {
                "today": today_row,
                "week": {
                    "start_date": str(week_start),
                    "end_date": str(today),
                    "completion": week_completion,
                },
                "daily": payload["daily"],
                "baseline_date": payload["range"]["baseline_date"],
            }
        )

    @action(detail=False, methods=['get'], url_path='history')
    def history(self, request):
        end_date_str = request.query_params.get('end_date')
        start_date_str = request.query_params.get('start_date')
        days_str = request.query_params.get('days', '90')

        try:
            end_date = (
                datetime.strptime(end_date_str, "%Y-%m-%d").date()
                if end_date_str
                else timezone.localdate()
            )
        except ValueError:
            return Response({"error": "Invalid end_date format"}, status=400)

        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            except ValueError:
                return Response({"error": "Invalid start_date format"}, status=400)
        else:
            try:
                days = max(7, min(365, int(days_str)))
            except ValueError:
                return Response({"error": "days must be a valid integer"}, status=400)
            start_date = end_date - timedelta(days=days - 1)

        if start_date > end_date:
            return Response({"error": "start_date must be before end_date"}, status=400)

        payload = _compute_range_metrics(request.user, start_date, end_date)
        return Response(payload)


class HabitLogViewSet(viewsets.ModelViewSet):
    serializer_class = HabitLogSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return HabitLog.objects.filter(habit__user=self.request.user)

    def create(self, request, *args, **kwargs):
        payload_serializer = HabitLogUpsertSerializer(
            data=request.data,
            context={"request": request},
        )
        payload_serializer.is_valid(raise_exception=True)

        habit = payload_serializer.validated_data["habit"]
        log_date = payload_serializer.validated_data["date"]
        status_value = payload_serializer.validated_data["status"]

        if status_value == "pending":
            HabitLog.objects.filter(habit=habit, date=log_date).delete()
            return Response(
                {
                    "habit": habit.id,
                    "date": str(log_date),
                    "status": "pending",
                },
                status=status.HTTP_200_OK,
            )

        log, created = HabitLog.objects.update_or_create(
            habit=habit,
            date=log_date,
            defaults={"status": status_value}
        )

        serializer = self.get_serializer(log)
        response_status = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(serializer.data, status=response_status)


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        serializer = UserProfileSerializer(profile, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request):
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        serializer = UserProfileSerializer(
            profile,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)


class CaseInsensitiveTokenObtainPairView(TokenObtainPairView):
    serializer_class = CaseInsensitiveTokenObtainPairSerializer