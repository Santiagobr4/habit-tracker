from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import Habit, HabitLog, HabitSchedule, UserProfile


VALID_DAYS = {
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
}

class HabitSerializer(serializers.ModelSerializer):
    days = serializers.ListField(child=serializers.CharField())

    class Meta:
        model = Habit
        fields = '__all__'
        read_only_fields = ['user', 'is_archived', 'archived_at']

    def validate_name(self, value):
        normalized = value.strip()
        if not normalized:
            raise serializers.ValidationError("Name cannot be empty")
        return normalized

    def validate_days(self, value):
        if not isinstance(value, list) or not value:
            raise serializers.ValidationError("Days must be a non-empty list")

        normalized = []
        for day in value:
            if not isinstance(day, str):
                raise serializers.ValidationError("Each day must be a string")

            normalized_day = day.strip().lower()
            if normalized_day not in VALID_DAYS:
                raise serializers.ValidationError(
                    f"Invalid day '{day}'. Allowed days: {sorted(VALID_DAYS)}"
                )

            if normalized_day not in normalized:
                normalized.append(normalized_day)

        return normalized

    def create(self, validated_data):
        habit = Habit.objects.create(**validated_data)
        HabitSchedule.objects.create(
            habit=habit,
            effective_from=habit.start_date,
            days=habit.days,
        )
        return habit

    def update(self, instance, validated_data):
        days_was_updated = "days" in validated_data
        previous_days = list(instance.days)

        updated_instance = super().update(instance, validated_data)

        if days_was_updated and previous_days != updated_instance.days:
            effective_from = timezone.localdate()
            if effective_from < updated_instance.start_date:
                effective_from = updated_instance.start_date

            HabitSchedule.objects.update_or_create(
                habit=updated_instance,
                effective_from=effective_from,
                defaults={"days": updated_instance.days},
            )

        return updated_instance

class HabitLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = HabitLog
        fields = '__all__'
        read_only_fields = ['habit']


class HabitLogUpsertSerializer(serializers.Serializer):
    habit = serializers.PrimaryKeyRelatedField(queryset=Habit.objects.all())
    date = serializers.DateField()
    status = serializers.ChoiceField(
        choices=[*HabitLog.STATUS_CHOICES, ("pending", "Pending")]
    )

    def validate_habit(self, habit):
        request = self.context.get("request")
        if not request or habit.user_id != request.user.id:
            raise serializers.ValidationError("You cannot update logs for this habit")
        if habit.is_archived:
            raise serializers.ValidationError("You cannot update logs for archived habits")
        return habit

    def validate(self, attrs):
        today = timezone.localdate()
        if attrs["date"] != today:
            raise serializers.ValidationError(
                {"date": "You can only update logs for today."}
            )

        if attrs["status"] == "done" and attrs["date"] > today:
            raise serializers.ValidationError(
                {"status": "You cannot mark a habit as done before its date."}
            )
        return attrs


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password']

    def validate(self, attrs):
        username = attrs["username"].strip()
        email = attrs["email"].strip().lower()

        errors = {}
        if User.objects.filter(username__iexact=username).exists():
            errors["username"] = ["This username is already in use."]
        if User.objects.filter(email__iexact=email).exists():
            errors["email"] = ["This email is already in use."]

        if errors:
            raise serializers.ValidationError(errors)

        attrs["username"] = username
        attrs["email"] = email
        return attrs

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class UserProfileSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(source='user.first_name', allow_blank=True, required=False)
    last_name = serializers.CharField(source='user.last_name', allow_blank=True, required=False)
    email = serializers.EmailField(source='user.email', required=False)
    username = serializers.CharField(source='user.username', read_only=True)
    avatar = serializers.ImageField(required=False, allow_null=True)
    remove_avatar = serializers.BooleanField(write_only=True, required=False, default=False)
    avatar_file_url = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = UserProfile
        fields = [
            'username',
            'email',
            'first_name',
            'last_name',
            'avatar',
            'remove_avatar',
            'avatar_file_url',
            'avatar_url',
            'birth_date',
            'weight_kg',
            'gender',
        ]

    def get_avatar_file_url(self, obj):
        if not obj.avatar:
            return None

        request = self.context.get('request')
        url = obj.avatar.url
        return request.build_absolute_uri(url) if request else url

    def validate_avatar(self, image):
        if image is None:
            return image

        allowed_types = {'image/jpeg', 'image/png', 'image/webp'}
        max_size_bytes = 2 * 1024 * 1024

        if image.content_type not in allowed_types:
            raise serializers.ValidationError('Avatar must be a JPG, PNG, or WEBP image.')

        if image.size > max_size_bytes:
            raise serializers.ValidationError('Avatar image must be 2MB or smaller.')

        return image

    def update(self, instance, validated_data):
        remove_avatar = validated_data.pop('remove_avatar', False)
        user_data = validated_data.pop('user', {})

        if remove_avatar:
            if instance.avatar:
                instance.avatar.delete(save=False)
            instance.avatar = None
            instance.avatar_url = ''

        for field, value in validated_data.items():
            setattr(instance, field, value)

        for field, value in user_data.items():
            setattr(instance.user, field, value)

        instance.user.save(update_fields=list(user_data.keys()) if user_data else None)
        instance.save()
        return instance


class CaseInsensitiveTokenObtainPairSerializer(TokenObtainPairSerializer):
    default_error_messages = {
        "no_active_account": "No active account found with the given credentials."
    }

    def validate(self, attrs):
        username = attrs.get(self.username_field)
        password = attrs.get("password")

        if not username or not password:
            raise AuthenticationFailed(self.error_messages["no_active_account"])

        user = User.objects.filter(username__iexact=username.strip()).first()
        if not user or not user.check_password(password):
            raise AuthenticationFailed(self.error_messages["no_active_account"])

        attrs[self.username_field] = user.get_username()
        return super().validate(attrs)