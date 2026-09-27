"""
Registration and Login forms with Uzbek phone number normalization and validation.
"""
from django import forms
from django.contrib.auth import authenticate, get_user_model
from django.core.exceptions import ValidationError
from .utils import normalize_uzbek_phone

User = get_user_model()

class UserRegistrationForm(forms.ModelForm):
    phone_number = forms.CharField(
        max_length=25,
        label="Telefon raqami",
        widget=forms.TextInput(attrs={
            'placeholder': '+998 90 123 45 67',
            'type': 'tel',
            'class': 'w-full px-3.5 py-2.5 sm:py-3 border border-slate-300 rounded-xl focus:ring-2 focus:ring-zinc-950 focus:border-zinc-950 outline-none transition text-slate-800 text-sm'
        }),
        error_messages={'required': "Telefon raqami kiritilishi shart."}
    )
    password = forms.CharField(
        label="Parol",
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Kamida 6 ta belgi',
            'class': 'w-full px-3.5 py-2.5 sm:py-3 border border-slate-300 rounded-xl focus:ring-2 focus:ring-zinc-950 focus:border-zinc-950 outline-none transition text-slate-800 text-sm'
        }),
        error_messages={'required': "Parol kiritilishi shart."}
    )
    password_confirm = forms.CharField(
        label="Parolni tasdiqlash",
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Parolni qayta kiriting',
            'class': 'w-full px-3.5 py-2.5 sm:py-3 border border-slate-300 rounded-xl focus:ring-2 focus:ring-zinc-950 focus:border-zinc-950 outline-none transition text-slate-800 text-sm'
        }),
        error_messages={'required': "Parolni tasdiqlash shart."}
    )

    class Meta:
        model = User
        fields = ['phone_number', 'password']

    def clean_phone_number(self):
        raw_phone = self.cleaned_data.get('phone_number')
        try:
            normalized_phone = normalize_uzbek_phone(raw_phone)
        except ValidationError:
            raise forms.ValidationError("Telefon raqami noto'g'ri kiritildi (+998XXXXXXXXX formatida bo'lishi kerak).")
        
        if User.objects.filter(phone_number=normalized_phone).exists():
            raise forms.ValidationError("Ushbu telefon raqami allaqachon ro'yxatdan o'tgan.")
        
        return normalized_phone

    def clean_password(self):
        password = self.cleaned_data.get('password')
        if password and len(password) < 6:
            raise forms.ValidationError("Parol kamida 6 ta belgidan iborat bo'lishi kerak.")
        return password

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        password_confirm = cleaned_data.get('password_confirm')

        if password and password_confirm and password != password_confirm:
            self.add_error('password_confirm', "Parollar bir-biriga mos kelmadi.")

        return cleaned_data

    def save(self, commit=True):
        user = User.objects.create_user(
            phone_number=self.cleaned_data['phone_number'],
            password=self.cleaned_data['password'],
            first_name=''
        )
        return user


class UserLoginForm(forms.Form):
    phone_number = forms.CharField(
        label="Telefon raqami",
        widget=forms.TextInput(attrs={
            'placeholder': '+998 90 123 45 67',
            'type': 'tel',
            'class': 'w-full px-3.5 py-2.5 sm:py-3 border border-slate-300 rounded-xl focus:ring-2 focus:ring-zinc-950 focus:border-zinc-950 outline-none transition text-slate-800 text-sm'
        }),
        error_messages={'required': "Telefon raqami kiritilishi shart."}
    )
    password = forms.CharField(
        label="Parol",
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Parolingizni kiriting',
            'class': 'w-full px-3.5 py-2.5 sm:py-3 border border-slate-300 rounded-xl focus:ring-2 focus:ring-zinc-950 focus:border-zinc-950 outline-none transition text-slate-800 text-sm'
        }),
        error_messages={'required': "Parol kiritilishi shart."}
    )

    def __init__(self, *args, request=None, **kwargs):
        self.request = request
        self.user = None
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        raw_phone = cleaned_data.get('phone_number')
        password = cleaned_data.get('password')

        if raw_phone and password:
            try:
                normalized_phone = normalize_uzbek_phone(raw_phone)
            except ValidationError:
                raise forms.ValidationError("Telefon raqami noto'g'ri kiritildi (+998XXXXXXXXX formatida bo'lishi kerak).")

            self.user = authenticate(
                self.request,
                username=normalized_phone,
                password=password
            )

            if self.user is None:
                raise forms.ValidationError("Telefon raqami yoki parol noto'g'ri.")
            
            if not self.user.is_active:
                raise forms.ValidationError("Foydalanuvchi hisobi faol emas.")

        return cleaned_data


class ProfileSettingsForm(forms.ModelForm):
    first_name = forms.CharField(
        max_length=150,
        label="Ismingiz",
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-orange-500 outline-none text-sm'
        })
    )
    email = forms.EmailField(
        required=False,
        label="Email manzili",
        widget=forms.EmailInput(attrs={
            'class': 'w-full px-4 py-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-orange-500 outline-none text-sm'
        })
    )
    birth_date = forms.DateField(
        required=False,
        label="Tug'ilgan sana",
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'w-full px-4 py-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-orange-500 outline-none text-sm'
        })
    )
    interests_text = forms.CharField(
        required=False,
        label="Qiziqishlar va xobbilar",
        widget=forms.TextInput(attrs={
            'placeholder': 'Masalan: dasturlash, musiqa, sport (vergul bilan ajrating)',
            'class': 'w-full px-4 py-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-orange-500 outline-none text-sm'
        }),
        help_text="Qiziqishlaringizni vergul bilan ajratib yozing."
    )

    class Meta:
        from .models import Student
        model = Student
        fields = [
            'grade', 'region', 'city', 'target_field_of_study',
            'target_program_type', 'english_level',
            'notification_reminder_time', 'notification_email_enabled',
            'notification_daily_reminders', 'preferred_language'
        ]
        widgets = {
            'grade': forms.Select(attrs={
                'class': 'w-full px-4 py-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-orange-500 outline-none text-sm'
            }),
            'region': forms.Select(attrs={
                'class': 'w-full px-4 py-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-orange-500 outline-none text-sm'
            }),
            'city': forms.TextInput(attrs={
                'placeholder': 'Masalan: Toshkent, Samarqand',
                'class': 'w-full px-4 py-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-orange-500 outline-none text-sm'
            }),
            'target_field_of_study': forms.Select(attrs={
                'class': 'w-full px-4 py-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-orange-500 outline-none text-sm'
            }),
            'target_program_type': forms.Select(attrs={
                'class': 'w-full px-4 py-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-orange-500 outline-none text-sm'
            }),
            'english_level': forms.Select(attrs={
                'class': 'w-full px-4 py-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-orange-500 outline-none text-sm'
            }),
            'notification_reminder_time': forms.TextInput(attrs={
                'placeholder': 'Masalan: 20:00',
                'class': 'w-full px-4 py-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-orange-500 outline-none text-sm'
            }),
            'notification_email_enabled': forms.CheckboxInput(attrs={
                'class': 'w-4 h-4 text-orange-600 rounded border-slate-300 focus:ring-orange-500'
            }),
            'notification_daily_reminders': forms.CheckboxInput(attrs={
                'class': 'w-4 h-4 text-orange-600 rounded border-slate-300 focus:ring-orange-500'
            }),
            'preferred_language': forms.Select(choices=[('uz', "O'zbekcha"), ('en', "English")], attrs={
                'class': 'w-full px-4 py-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-orange-500 outline-none text-sm'
            }),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            self.fields['first_name'].initial = user.first_name
            self.fields['email'].initial = user.email
        # Pre-fill birth_date and interests_text from instance
        instance = kwargs.get('instance')
        if instance:
            self.fields['birth_date'].initial = instance.birth_date
            if instance.interests:
                self.fields['interests_text'].initial = ', '.join(instance.interests) if isinstance(instance.interests, list) else instance.interests

    def save(self, commit=True):
        student = super().save(commit=False)
        # Save birth_date
        birth_date = self.cleaned_data.get('birth_date')
        if birth_date:
            student.birth_date = birth_date
            student.birth_year = birth_date.year
        # Save interests from comma-separated text
        interests_raw = self.cleaned_data.get('interests_text', '')
        if interests_raw:
            student.interests = [i.strip() for i in interests_raw.split(',') if i.strip()]
        if commit:
            student.save()
        return student
