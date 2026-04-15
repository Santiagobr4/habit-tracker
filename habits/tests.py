from datetime import date, timedelta

from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Habit, HabitLog


class HabitApiTests(APITestCase):
	def setUp(self):
		self.today = timezone.localdate()
		self.week_start = self.today - timedelta(days=self.today.weekday())
		self.tomorrow = self.today + timedelta(days=1)
		self.yesterday = self.today - timedelta(days=1)

		self.user_1 = User.objects.create_user(
			username='alice',
			password='Passw0rd123',
			email='alice@example.com',
		)
		self.user_2 = User.objects.create_user(
			username='bob',
			password='Passw0rd123',
			email='bob@example.com',
		)

		self.habit_user_1 = Habit.objects.create(
			user=self.user_1,
			name='Read 20 mins',
			days=['monday', 'tuesday', 'wednesday', 'thursday', 'friday'],
			start_date=self.week_start,
		)
		self.habit_user_2 = Habit.objects.create(
			user=self.user_2,
			name='Run 5km',
			days=['monday', 'wednesday', 'friday'],
			start_date=self.week_start,
		)

	def authenticate(self, username, password):
		token_response = self.client.post(
			'/api/token/',
			{'username': username, 'password': password},
			format='json',
		)
		self.assertEqual(token_response.status_code, status.HTTP_200_OK)
		access = token_response.data['access']
		self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')

	def test_register_user(self):
		payload = {
			'username': 'charlie',
			'email': 'charlie@example.com',
			'password': 'Passw0rd123',
		}
		response = self.client.post('/api/register/', payload, format='json')

		self.assertEqual(response.status_code, status.HTTP_201_CREATED)
		self.assertEqual(response.data['username'], 'charlie')
		self.assertTrue(User.objects.filter(username='charlie').exists())

	def test_register_rejects_duplicate_username_and_email(self):
		payload = {
			'username': 'ALICE',
			'email': 'Alice@Example.com',
			'password': 'Passw0rd123',
		}
		response = self.client.post('/api/register/', payload, format='json')

		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertIn('username', response.data)
		self.assertIn('email', response.data)

	def test_case_insensitive_login_with_username(self):
		response = self.client.post(
			'/api/token/',
			{'username': 'ALICE', 'password': 'Passw0rd123'},
			format='json',
		)
		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertIn('access', response.data)

	def test_weekly_returns_only_current_user_habits(self):
		self.authenticate('alice', 'Passw0rd123')

		response = self.client.get(f'/api/habits/weekly/?start_date={self.week_start}')

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(len(response.data['habits']), 1)
		self.assertEqual(response.data['habits'][0]['habit_id'], self.habit_user_1.id)

	def test_cannot_upsert_log_for_other_user_habit(self):
		self.authenticate('alice', 'Passw0rd123')

		response = self.client.post(
			'/api/logs/',
			{
				'habit': self.habit_user_2.id,
				'date': str(self.today),
				'status': 'done',
			},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertFalse(
			HabitLog.objects.filter(
				habit=self.habit_user_2,
				date=str(self.today),
			).exists()
		)

	def test_upsert_log_create_then_update(self):
		self.authenticate('alice', 'Passw0rd123')

		create_response = self.client.post(
			'/api/logs/',
			{
				'habit': self.habit_user_1.id,
				'date': str(self.today),
				'status': 'done',
			},
			format='json',
		)
		self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)

		update_response = self.client.post(
			'/api/logs/',
			{
				'habit': self.habit_user_1.id,
				'date': str(self.today),
				'status': 'missed',
			},
			format='json',
		)
		self.assertEqual(update_response.status_code, status.HTTP_200_OK)

		log = HabitLog.objects.get(habit=self.habit_user_1, date=str(self.today))
		self.assertEqual(log.status, 'missed')

	def test_pending_status_removes_existing_log(self):
		self.authenticate('alice', 'Passw0rd123')

		HabitLog.objects.create(
			habit=self.habit_user_1,
			date=str(self.today),
			status='done',
		)

		response = self.client.post(
			'/api/logs/',
			{
				'habit': self.habit_user_1.id,
				'date': str(self.today),
				'status': 'pending',
			},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertFalse(
			HabitLog.objects.filter(
				habit=self.habit_user_1,
				date=str(self.today),
			).exists()
		)

	def test_log_update_is_rejected_for_future_date(self):
		self.authenticate('alice', 'Passw0rd123')

		response = self.client.post(
			'/api/logs/',
			{
				'habit': self.habit_user_1.id,
				'date': str(self.tomorrow),
				'status': 'done',
			},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertIn('date', response.data)

	def test_log_update_is_rejected_for_past_date(self):
		self.authenticate('alice', 'Passw0rd123')

		response = self.client.post(
			'/api/logs/',
			{
				'habit': self.habit_user_1.id,
				'date': str(self.yesterday),
				'status': 'missed',
			},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertIn('date', response.data)

	def test_editing_days_preserves_past_history(self):
		self.authenticate('alice', 'Passw0rd123')

		HabitLog.objects.create(
			habit=self.habit_user_1,
			date=str(self.today),
			status='done',
		)

		patch_response = self.client.patch(
			f'/api/habits/{self.habit_user_1.id}/',
			{'days': ['tuesday', 'wednesday', 'thursday', 'friday']},
			format='json',
		)
		self.assertEqual(patch_response.status_code, status.HTTP_200_OK)

		weekly_response = self.client.get(f'/api/habits/weekly/?start_date={self.week_start}')
		self.assertEqual(weekly_response.status_code, status.HTTP_200_OK)

		habit_row = weekly_response.data['habits'][0]
		self.assertEqual(habit_row['week'][str(self.today)], 'done')

	def test_history_endpoint_returns_daily_weekly_monthly(self):
		self.authenticate('alice', 'Passw0rd123')

		response = self.client.get('/api/habits/history/?days=30')
		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertIn('daily', response.data)
		self.assertIn('weekly', response.data)
		self.assertIn('monthly', response.data)

	def test_history_returns_empty_until_baseline_when_no_applicable_data(self):
		self.authenticate('alice', 'Passw0rd123')

		future_start = timezone.localdate().replace(year=timezone.localdate().year + 1)
		self.habit_user_1.start_date = future_start
		self.habit_user_1.save(update_fields=['start_date'])

		response = self.client.get('/api/habits/history/?days=30')
		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data['daily'], [])
		self.assertIsNone(response.data['summary']['average_daily_completion'])

	def test_weekly_returns_null_percentages_before_metrics_baseline(self):
		self.authenticate('alice', 'Passw0rd123')

		future_start = timezone.localdate().replace(year=timezone.localdate().year + 1)
		self.habit_user_1.start_date = future_start
		self.habit_user_1.save(update_fields=['start_date'])

		week_start = timezone.localdate() - timedelta(days=timezone.localdate().weekday())
		response = self.client.get(f'/api/habits/weekly/?start_date={week_start}')
		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertIsNone(response.data['average_completion'])
		self.assertTrue(all(value is None for value in response.data['daily_percentages'].values()))

	def test_profile_patch_updates_extended_fields(self):
		self.authenticate('alice', 'Passw0rd123')

		payload = {
			'first_name': 'Alice',
			'last_name': 'Walker',
			'birth_date': '1995-04-12',
			'weight_kg': '62.50',
			'gender': 'female',
		}
		response = self.client.patch('/api/profile/', payload, format='json')
		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data['first_name'], 'Alice')
		self.assertEqual(response.data['gender'], 'female')

	def test_weekly_includes_streak_metrics(self):
		self.authenticate('alice', 'Passw0rd123')

		HabitLog.objects.create(
			habit=self.habit_user_1,
			date=str(self.today),
			status='done',
		)

		response = self.client.get(f'/api/habits/weekly/?start_date={self.week_start}')
		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertIn('streak_current', response.data['habits'][0])
		self.assertIn('streak_best', response.data['habits'][0])

	def test_tracker_metrics_endpoint(self):
		self.authenticate('alice', 'Passw0rd123')

		response = self.client.get(f'/api/habits/tracker-metrics/?start_date={self.week_start}')
		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertIn('focus', response.data)
		self.assertIn('focus_date', response.data)
		self.assertIn('is_current_week', response.data)
		self.assertIn('week', response.data)
		self.assertIn('daily', response.data)

	def test_tracker_metrics_rejects_future_week(self):
		self.authenticate('alice', 'Passw0rd123')

		future_week = self.week_start + timedelta(days=7)
		response = self.client.get(f'/api/habits/tracker-metrics/?start_date={future_week}')
		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

	def test_tracker_metrics_normalizes_non_monday_start_date(self):
		self.authenticate('alice', 'Passw0rd123')

		non_monday = self.week_start + timedelta(days=1)
		response = self.client.get(f'/api/habits/tracker-metrics/?start_date={non_monday}')
		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data['week']['start_date'], str(self.week_start))

	def test_weekly_metrics_contains_average_and_daily_percentages(self):
		self.authenticate('alice', 'Passw0rd123')

		HabitLog.objects.create(
			habit=self.habit_user_1,
			date=str(self.today),
			status='done',
		)

		response = self.client.get(f'/api/habits/weekly/?start_date={self.week_start}')

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertIn('average_completion', response.data)
		self.assertIn('daily_percentages', response.data)
		self.assertIn(str(self.today), response.data['daily_percentages'])

	def test_soft_delete_preserves_previous_day_metrics(self):
		self.authenticate('alice', 'Passw0rd123')

		HabitLog.objects.create(habit=self.habit_user_1, date=str(self.today), status='done')
		second_habit = Habit.objects.create(
			user=self.user_1,
			name='Study 30 mins',
			days=['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'],
			start_date=self.week_start,
		)

		response_before = self.client.get(f'/api/habits/history/?start_date={self.today}&end_date={self.today}')
		self.assertEqual(response_before.status_code, status.HTTP_200_OK)
		self.assertEqual(response_before.data['daily'][0]['completion'], 50)

		delete_response = self.client.delete(f'/api/habits/{second_habit.id}/')
		self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)

		response_after = self.client.get(f'/api/habits/history/?start_date={self.today}&end_date={self.today}')
		self.assertEqual(response_after.status_code, status.HTTP_200_OK)
		self.assertEqual(response_after.data['daily'][0]['completion'], 50)

	def test_leaderboard_endpoint_returns_users(self):
		self.authenticate('alice', 'Passw0rd123')
		HabitLog.objects.create(habit=self.habit_user_1, date=str(self.today), status='done')

		response = self.client.get('/api/habits/leaderboard/?days=30')
		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertIn('results', response.data)
		if response.data['results']:
			self.assertIn('daily_completion', response.data['results'][0])
			self.assertIn('weekly_completion', response.data['results'][0])
			self.assertIn('monthly_completion', response.data['results'][0])

	def test_profile_remove_avatar_clears_avatar_url(self):
		self.authenticate('alice', 'Passw0rd123')

		response_set = self.client.patch(
			'/api/profile/',
			{'avatar_url': 'https://example.com/avatar.png'},
			format='json',
		)
		self.assertEqual(response_set.status_code, status.HTTP_200_OK)

		response_remove = self.client.patch(
			'/api/profile/',
			{'remove_avatar': True},
			format='json',
		)
		self.assertEqual(response_remove.status_code, status.HTTP_200_OK)
		self.assertEqual(response_remove.data['avatar_url'], '')
