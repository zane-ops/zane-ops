import re
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from rest_framework import serializers

from ..base import ResourceConflict


# ==========================================
#                 Shared                   #
# ==========================================

def validate_new_password(value, user=None):
    # configuration of validate_password is in settings.py["AUTH_PASSWORD_VALIDATORS"]
    validate_password(value, user)

    # Check for mix of uppercase, lowercase, numbers, symbols (>= 2 types of them)
    char_types = 0
    
    types = [
        r'[a-z]',
        r'[A-Z]',
        r'[0-9]',
        r'[^a-zA-Z0-9]',
    ]

    for regex in types:
        if re.search(regex, value):
            char_types += 1
    
    if char_types < 2:
        raise ValidationError(
            "Password must contain at least 2 different types of characters "
            "(uppercase letters, lowercase letters, numbers, or symbols)."
        )

    return value


# ==========================================
#              User Creation               #
# ==========================================


class UserExistenceResponseSerializer(serializers.Serializer):
    exists = serializers.BooleanField()


class UserCreationRequestSerializer(serializers.Serializer):
    username = serializers.CharField(min_length=1, max_length=255)
    password = serializers.CharField(min_length=8)

    class Meta:
        model = AbstractUser
        fields = ['username', 'password']


    def validate_password(self, value):
        validate_new_password(value)
        return value

class UserCreatedResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()


# ==========================================
#             Change Password              #
# ==========================================

class ChangePasswordRequestSerializer(serializers.Serializer):
    current_password = serializers.CharField(min_length=8)
    new_password = serializers.CharField(min_length=8)
    confirm_password = serializers.CharField(min_length=8)

    def validate_current_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value

    def validate_new_password(self, value):
        validate_new_password(value, user=self.context['request'].user)
        return value

    def validate(self, attrs):
        new_password = attrs.get('new_password')
        confirm_password = attrs.get('confirm_password')
        
        if new_password != confirm_password:
            raise serializers.ValidationError({
                'confirm_password': 'Your passwords do not match.'
            })

        return attrs


class ChangePasswordResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()


# ==========================================
#             Update Profile               #
# ==========================================

User = get_user_model()

class UpdateProfileRequestSerializer(serializers.ModelSerializer):
    username = serializers.CharField(
        max_length=150,
        validators=[UnicodeUsernameValidator()],
    )
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name']

    def update(self, instance: AbstractUser, validated_data):
        instance.username = validated_data.get("username", instance.username)
        instance.first_name = validated_data.get("first_name", instance.first_name)
        instance.last_name = validated_data.get("last_name", instance.last_name)
        if (
            User.objects.filter(username=instance.username)
            .exclude(id=instance.pk)
            .exists()
        ):
            raise ResourceConflict(
                detail="A user with the username already exists.",
            )
        instance.save()
        return instance
