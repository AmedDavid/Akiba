from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
from .models import UserProfile, Goal, DailySaving, MpesaStatement, Tribe, TribePost


class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'your.email@example.com'
        })
    )
    phone = forms.CharField(
        max_length=15, 
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'pattern': '[0-9+\\-\\s()]+',
            'placeholder': '0712345678'
        })
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'phone', 'password1', 'password2')
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'form-control',
                'minlength': '3',
                'maxlength': '150',
                'pattern': '[a-zA-Z0-9_]+'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget.attrs.update({
            'class': 'form-control',
            'minlength': '8'
        })
        self.fields['password2'].widget.attrs.update({
            'class': 'form-control',
            'minlength': '8'
        })

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if len(username) < 3:
            raise forms.ValidationError("Username must be at least 3 characters long.")
        if not username.replace('_', '').isalnum():
            raise forms.ValidationError("Username can only contain letters, numbers, and underscores.")
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("A user with this email already exists.")
        return email

    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        if phone:
            # Remove common phone formatting characters
            cleaned_phone = ''.join(filter(str.isdigit, phone))
            if len(cleaned_phone) < 9 or len(cleaned_phone) > 15:
                raise forms.ValidationError("Please enter a valid phone number.")
        return phone


class CustomAuthenticationForm(AuthenticationForm):
    pass


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['avatar', 'phone']
        widgets = {
            'avatar': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'pattern': '[0-9+\\-\\s()]+',
                'maxlength': '15'
            }),
        }

    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        if phone:
            # Remove common phone formatting characters
            cleaned_phone = ''.join(filter(str.isdigit, phone))
            if len(cleaned_phone) < 9 or len(cleaned_phone) > 15:
                raise forms.ValidationError("Please enter a valid phone number (9-15 digits).")
        return phone

    def clean_avatar(self):
        avatar = self.cleaned_data.get('avatar')
        if avatar:
            # Check file size (max 5MB)
            if avatar.size > 5 * 1024 * 1024:
                raise forms.ValidationError("Image file too large (maximum 5MB).")
            # Check file type
            if not avatar.content_type.startswith('image/'):
                raise forms.ValidationError("File must be an image.")
        return avatar


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

