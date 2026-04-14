from datetime import date, timedelta

from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Habit, HabitLog


class HabitApiTests(APITestCase):
	def setUp(self):
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
			start_date=date(2026, 4, 13),
		)
		self.habit_user_2 = Habit.objects.create(
			user=self.user_2,
			name='Run 5km',
			days=['monday', 'wednesday', 'friday'],
			start_date=date(2026, 4, 13),
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

		response = self.client.get('/api/habits/weekly/?start_date=2026-04-13')

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(len(response.data['habits']), 1)
		self.assertEqual(response.data['habits'][0]['habit_id'], self.habit_user_1.id)

	def test_cannot_upsert_log_for_other_user_habit(self):
		self.authenticate('alice', 'Passw0rd123')

		response = self.client.post(
			'/api/logs/',
			{
				'habit': self.habit_user_2.id,
				'date': '2026-04-14',
				'status': 'done',
			},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertFalse(
			HabitLog.objects.filter(
				habit=self.habit_user_2,
				date='2026-04-14',
			).exists()
		)

	def test_upsert_log_create_then_update(self):
		self.authenticate('alice', 'Passw0rd123')

		create_response = self.client.post(
			'/api/logs/',
			{
				'habit': self.habit_user_1.id,
				'date': '2026-04-14',
				'status': 'done',
			},
			format='json',
		)
		self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)

		update_response = self.client.post(
			'/api/logs/',
			{
				'habit': self.habit_user_1.id,
				'date': '2026-04-14',
				'status': 'missed',
			},
			format='json',
		)
		self.assertEqual(update_response.status_code, status.HTTP_200_OK)

		log = HabitLog.objects.get(habit=self.habit_user_1, date='2026-04-14')
		self.assertEqual(log.status, 'missed')

	def test_pending_status_removes_existing_log(self):
		self.authenticate('alice', 'Passw0rd123')

		HabitLog.objects.create(
			habit=self.habit_user_1,
			date='2026-04-14',
			status='done',
		)

		response = self.client.post(
			'/api/logs/',
			{
				'habit': self.habit_user_1.id,
				'date': '2026-04-14',
				'status': 'pending',
			},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertFalse(
			HabitLog.objects.filter(
				habit=self.habit_user_1,
				date='2026-04-14',
			).exists()
		)

	def test_done_status_is_rejected_for_future_date(self):
		self.authenticate('alice', 'Passw0rd123')

		future_date = timezone.localdate().replace(year=timezone.localdate().year + 1)
		response = self.client.post(
			'/api/logs/',
			{
				'habit': self.habit_user_1.id,
				'date': str(future_date),
				'status': 'done',
			},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertIn('status', response.data)

	def test_editing_days_preserves_past_history(self):
		self.authenticate('alice', 'Passw0rd123')

		HabitLog.objects.create(
			habit=self.habit_user_1,
			date='2026-04-14',
			status='done',
		)

		patch_response = self.client.patch(
			f'/api/habits/{self.habit_user_1.id}/',
			{'days': ['tuesday', 'wednesday', 'thursday', 'friday']},
			format='json',
		)
		self.assertEqual(patch_response.status_code, status.HTTP_200_OK)

		weekly_response = self.client.get('/api/habits/weekly/?start_date=2026-04-14')
		self.assertEqual(weekly_response.status_code, status.HTTP_200_OK)

		habit_row = weekly_response.data['habits'][0]
		self.assertEqual(habit_row['week']['2026-04-14'], 'done')

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
			'avatar_url': 'https://example.com/avatar.png',
		}
		response = self.client.patch('/api/profile/', payload, format='json')
		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data['first_name'], 'Alice')
		self.assertEqual(response.data['gender'], 'female')

	def test_weekly_includes_streak_metrics(self):
		self.authenticate('alice', 'Passw0rd123')

		HabitLog.objects.create(
			habit=self.habit_user_1,
			date='2026-04-14',
			status='done',
		)
		HabitLog.objects.create(
			habit=self.habit_user_1,
			date='2026-04-15',
			status='done',
		)

		response = self.client.get('/api/habits/weekly/?start_date=2026-04-14')
		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertIn('streak_current', response.data['habits'][0])
		self.assertIn('streak_best', response.data['habits'][0])

	def test_tracker_metrics_endpoint(self):
		self.authenticate('alice', 'Passw0rd123')

		response = self.client.get('/api/habits/tracker-metrics/')
		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertIn('today', response.data)
		self.assertIn('week', response.data)
		self.assertIn('daily', response.data)

	def test_weekly_metrics_contains_average_and_daily_percentages(self):
		self.authenticate('alice', 'Passw0rd123')

		HabitLog.objects.create(
			habit=self.habit_user_1,
			date='2026-04-13',
			status='done',
		)

		response = self.client.get('/api/habits/weekly/?start_date=2026-04-13')

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertIn('average_completion', response.data)
		self.assertIn('daily_percentages', response.data)
		self.assertIn('2026-04-13', response.data['daily_percentages'])
