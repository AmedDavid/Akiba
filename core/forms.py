from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Submit
from .models import UserProfile, Goal, DailySaving, MpesaStatement, Tribe, TribePost


class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    phone = forms.CharField(max_length=15, required=False)

    class Meta:
        model = User
        fields = ('username', 'email', 'phone', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'username',
            'email',
            'phone',
            'password1',
            'password2',
            Submit('submit', 'Register', css_class='btn btn-primary')
        )


class CustomAuthenticationForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'username',
            'password',
            Submit('submit', 'Login', css_class='btn btn-primary')
        )


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['avatar', 'phone']
        widgets = {
            'avatar': forms.FileInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
        }


class GoalForm(forms.ModelForm):
    class Meta:
        model = Goal
        fields = ['title', 'target_amount', 'deadline', 'category']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'target_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'deadline': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'category': forms.Select(attrs={'class': 'form-control'}),
        }


class DailySavingForm(forms.ModelForm):
    class Meta:
        model = DailySaving
        fields = ['amount', 'note']
        widgets = {
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01'}),
            'note': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class MpesaStatementForm(forms.ModelForm):
    class Meta:
        model = MpesaStatement
        fields = ['pdf_file']
        widgets = {
            'pdf_file': forms.FileInput(attrs={'class': 'form-control', 'accept': '.pdf'}),
        }


class TribeForm(forms.ModelForm):
    class Meta:
        model = Tribe
        fields = ['name', 'description', 'is_private']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'is_private': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class TribePostForm(forms.ModelForm):
    class Meta:
        model = TribePost
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Share your savings journey...'}),
        }

