import django.forms as forms


class PasswordLoginForm(forms.Form):
    username = forms.CharField(required=True, min_length=1, strip=True, max_length=255)
    password = forms.CharField(required=True, max_length=255, min_length=1)
