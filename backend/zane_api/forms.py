import django.forms as forms


class PasswordLoginForm(forms.Form):
    username = forms.CharField(required=True, min_length=1, strip=True, max_length=255)
    password = forms.CharField(required=True, max_length=255, min_length=1)


PASSWORD_REGEX = r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$"


class PasswordRegisterForm(forms.Form):
    username = forms.CharField(
        required=True,
        min_length=1,
        strip=True,
        max_length=255,
    )
    password = forms.RegexField(
        required=True,
        regex=PASSWORD_REGEX,
        error_messages={"invalid": "Please a valid password"},
        max_length=255,
    )
