from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from rest_framework import serializers

from ..base import ResourceConflict

# ==========================================
#             Change Password              #
# ==========================================

class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(min_length=8)
    new_password = serializers.CharField(min_length=8)
    confirm_password = serializers.CharField(min_length=8)

    def validate_current_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value

    def validate_new_password(self, value):
        user = self.context['request'].user
        try:
            validate_password(value, user)
        except ValidationError as e:
            raise serializers.ValidationError(e.messages)
        return value

    def validate(self, attrs):
        new_password = attrs.get('new_password')
        confirm_password = attrs.get('confirm_password')
        
        if new_password != confirm_password:
            raise serializers.ValidationError({
                'confirm_password': 'New password and confirmation do not match.'
            })

        return attrs


class ChangePasswordResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()


# ==========================================
#             Update Profile               #
# ==========================================

User = get_user_model()

class UpdateProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(required=True, max_length=150)
    first_name = serializers.CharField(required=False, max_length=150, allow_blank=True)
    last_name = serializers.CharField(required=False, max_length=150, allow_blank=True)

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name']

    def validate_username(self, value):
        import re
        if not re.match(r'^[a-zA-Z0-9_-]+$', value):
            raise serializers.ValidationError(
                "Username can only contain letters, numbers, underscores, and hyphens."
            )

        return value

    def update(self, instance, validated_data):
        if User.objects.filter(username=validated_data["username"]).exclude(id=self.context["request"].user.id).exists():
            raise ResourceConflict(
                detail="A user with the username already exists.",
            )

        user = self.context["request"].user
        if "username" in validated_data:
            user.username = validated_data["username"]
        if "first_name" in validated_data:
            user.first_name = validated_data["first_name"]
        if "last_name" in validated_data:
            user.last_name = validated_data["last_name"]

        user.save()

        return user

class UpdateProfileResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()
