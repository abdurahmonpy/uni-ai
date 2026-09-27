"""
Forms for multi-step onboarding wizard:
- OnboardingStep1Form: Student academic profile, region, interests, target career & countries.
- CertificateStepForm: Language & standardized test certificate validation (IELTS, TOEFL, SAT, DET, CEFR).
- TimelineStepForm: Dual-Track study plan duration (1-8 months) and target test date.
"""
from datetime import date, timedelta
from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.accounts.models import Student
from apps.onboarding.models import TestCertificate
from apps.services.certificate_service import check_certificate_validity

COUNTRY_CHOICES = [
    ('AQSh', 'AQSh (Global UGRAD, Universitet Grantlari)'),
    ('Buyuk Britaniya', 'Buyuk Britaniya (Chevening, Foundation)'),
    ('Germaniya', 'Germaniya (DAAD, Davlat Universitetlari)'),
    ('Turkiya', 'Turkiya (Türkiye Bursları)'),
    ('Janubiy Koreya', 'Janubiy Koreya (GKS / KGSP)'),
    ('Kanada', 'Kanada (Universitet Grantlari)'),
    ('Yaponiya', 'Yaponiya (MEXT)'),
    ('Boshqa', 'Boshqa davlatlar'),
]

INTERESTS_CHOICES = [
    ('coding_web', 'Dasturlash & Web-dizayn'),
    ('robotics_stem', 'Robototexnika & STEM loyihalari'),
    ('math_olympiad', 'Matematika & Mantiqiy masalalar'),
    ('debate_mun', 'Debatlar & Notiqlik san\'ati (Model UN)'),
    ('volunteering', 'Volontyorlik & Ijtimoiy tashabbuslar'),
    ('reading_research', 'Kitobxonlik & Ilmiy izlanishlar'),
    ('sports_health', 'Sport & Sog\'lom turmush tarzi'),
    ('languages', 'Xorijiy tillarni o\'rganish'),
    ('creative_arts', 'San\'at, Musiqa & Media'),
    ('eco_sustainability', 'Ekologiya & Tabiatni muhofaza qilish'),
]

TARGET_FIELD_CHOICES = [
    ('', "Yo'nalishni tanlang..."),
    ('cs_it', "Dasturlash va Axborot Texnologiyalari (CS & IT)"),
    ('ai_ds', "Sun'iy Intellekt va Data Science"),
    ('medicine', "Tibbiyot va Sog'liqni Saqlash"),
    ('business_finance', "Biznes, Moliya va Menejment"),
    ('engineering', "Muhandislik va Robototexnika"),
    ('international_law', "Xalqaro Munosabatlar va Huquq"),
    ('economics', "Iqtisodiyot va Ekonometrika"),
    ('natural_sciences', "Aniq va Tabiiy Fanlar (STEM)"),
    ('architecture_design', "Arxitektura va Dizayn"),
    ('education_humanities', "Pedagogika va Gumanitar Fanlar"),
]

CAREER_CHOICES = [
    ('', "Kelajak kasbingizni tanlang..."),
    ("Software Engineer / Dasturchi", "Software Engineer / Dasturchi"),
    ("Sun'iy intellekt (AI/ML) muhandisi", "Sun'iy intellekt (AI/ML) muhandisi"),
    ("Data Scientist / Ma'lumotlar tahlilchisi", "Data Scientist / Ma'lumotlar tahlilchisi"),
    ("Kiberxavfsizlik mutaxassisi (Cybersecurity)", "Kiberxavfsizlik mutaxassisi (Cybersecurity)"),
    ("UI/UX va Mahsulot dizayneri", "UI/UX va Mahsulot dizayneri"),
    ("Shifokor / Jarroh / Kardioxirurg", "Shifokor / Jarroh / Kardioxirurg"),
    ("Biotibbiyot va Genetik tadqiqotchi", "Biotibbiyot va Genetik tadqiqotchi"),
    ("Farmatsevtika va Tibbiy biotexnolog", "Farmatsevtika va Tibbiy biotexnolog"),
    ("Investitsion bankir / Moliya tahlilchisi", "Investitsion bankir / Moliya tahlilchisi"),
    ("Kompaniya boshqaruvchisi / Menejer (CEO)", "Kompaniya boshqaruvchisi / Menejer (CEO)"),
    ("Biznes konsultatsiya va Strateg", "Biznes konsultatsiya va Strateg"),
    ("Iqtisodchi va Ekonometrist", "Iqtisodchi va Ekonometrist"),
    ("Robototexnika va Mexatronika muhandisi", "Robototexnika va Mexatronika muhandisi"),
    ("Aerokosmik va Aviatsiya muhandisi", "Aerokosmik va Aviatsiya muhandisi"),
    ("Arxitektor va Shaharsoz (Urbanist)", "Arxitektor va Shaharsoz (Urbanist)"),
    ("Yashil energetika va Ekologiya muhandisi", "Yashil energetika va Ekologiya muhandisi"),
    ("Xalqaro diplomat va Elchixona xodimi", "Xalqaro diplomat va Elchixona xodimi"),
    ("Xalqaro huquqshunos va Korporativ advokat", "Xalqaro huquqshunos va Korporativ advokat"),
    ("Universitet professori / Tadqiqotchi", "Universitet professori / Tadqiqotchi"),
    ("Startap asoschisi / Texnologik tadbirkor", "Startap asoschisi / Texnologik tadbirkor"),
    ("Boshqa soha mutaxassisi", "Boshqa soha mutaxassisi"),
]


class OnboardingStep1Form(forms.Form):
    """
    Step 1: Student academic intake, demographics, region, interests, and target programs.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        initial_val = self.initial.get('target_career')
        if initial_val:
            existing_keys = [c[0] for c in self.fields['target_career'].choices]
            if initial_val not in existing_keys:
                self.fields['target_career'].choices = list(self.fields['target_career'].choices) + [(initial_val, initial_val)]

        today = timezone.localdate()
        try:
            earliest_date = date(today.year - 40, today.month, today.day) + timedelta(days=1)
        except ValueError:
            earliest_date = date(today.year - 40, today.month, 28) + timedelta(days=1)

        self.fields['birth_date'].widget.attrs.update({
            'min': earliest_date.isoformat(),
            'max': today.isoformat(),
        })

    first_name = forms.CharField(
        max_length=150,
        label="Ismingiz",
        required=True,
        widget=forms.TextInput(attrs={
            'placeholder': 'Masalan: Malika yoki Sardor',
            'class': 'w-full px-4 py-3 rounded-xl border border-zinc-300 focus:ring-2 focus:ring-zinc-950 focus:border-zinc-950 text-zinc-900 bg-white font-medium text-sm'
        }),
        error_messages={'required': "Iltimos, ismingizni kiriting."}
    )
    grade = forms.TypedChoiceField(
        choices=Student.GRADE_CHOICES,
        coerce=int,
        label="Hozir nechanchi sinfda o'qiysiz?",
        widget=forms.RadioSelect(attrs={'class': 'peer hidden'}),
        required=True,
        error_messages={'required': "Iltimos, o'qiydigan sinfingizni tanlang."}
    )
    target_countries = forms.MultipleChoiceField(
        choices=COUNTRY_CHOICES,
        label="Qaysi davlatlarda ta'lim olishni rejalashtiryapsiz?",
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'peer hidden'}),
        required=True,
        error_messages={'required': "Kamida bitta davlatni tanlang."}
    )
    target_program_type = forms.ChoiceField(
        choices=Student.PROGRAM_TYPE_CHOICES,
        label="Sizni qiziqtirgan dastur turi qanday?",
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-3 rounded-xl border border-slate-300 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 text-slate-800 text-xs font-semibold bg-white'
        }),
        initial='grant',
        required=False,
    )
    english_level = forms.ChoiceField(
        choices=Student.ENGLISH_LEVEL_CHOICES,
        label="Hozirgi ingliz tili darajangiz qanday?",
        widget=forms.RadioSelect(attrs={'class': 'peer hidden'}),
        initial='beginner',
        required=False,
    )
    birth_date = forms.DateField(
        label="Tug'ilgan sana",
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'w-full px-4 py-3 rounded-xl border border-zinc-300 focus:ring-2 focus:ring-orange-500 focus:border-orange-500 text-zinc-900 bg-white font-medium text-sm',
            'placeholder': 'YYYY-MM-DD',
        })
    )
    region = forms.ChoiceField(
        choices=[('', "Hududni tanlang...")] + list(Student.REGION_CHOICES),
        label="Viloyat / Hudud",
        required=False,
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-3 rounded-xl border border-slate-300 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 text-slate-800'
        })
    )
    city = forms.CharField(
        max_length=100,
        label="Shahar / Tuman",
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'Masalan: Samarqand shahri yoki Urgut tumani',
            'class': 'w-full px-4 py-3 rounded-xl border border-slate-300 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 text-slate-800'
        })
    )
    interests = forms.MultipleChoiceField(
        choices=INTERESTS_CHOICES,
        label="Qiziqishlaringiz va mashg'ulotlaringiz",
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'peer hidden'})
    )
    target_field_of_study = forms.ChoiceField(
        choices=TARGET_FIELD_CHOICES,
        label="Kelajakdagi o'qish yo'nalishingiz",
        required=False,
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-3 rounded-xl border border-slate-300 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 text-slate-800'
        })
    )
    target_career = forms.ChoiceField(
        choices=CAREER_CHOICES,
        label="Kelajak kasbingiz yoki asosiy maqsadingiz",
        required=False,
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-3 rounded-xl border border-slate-300 focus:ring-2 focus:ring-orange-500 focus:border-orange-500 text-slate-800'
        })
    )
    budget_preference = forms.ChoiceField(
        choices=Student.BUDGET_CHOICES,
        label="Byudjet imkoniyati / Afzallik",
        initial='toliq_grant',
        required=False,
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-3 rounded-xl border border-slate-300 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 text-slate-800 text-xs font-semibold bg-white'
        })
    )

    def clean_birth_date(self):
        bdate = self.cleaned_data.get('birth_date')
        if bdate:
            today = timezone.localdate()
            if bdate > today:
                raise ValidationError("Tug'ilgan sana kelajakda bo'lishi mumkin emas.")

            try:
                birthday = bdate.replace(year=today.year)
            except ValueError:
                birthday = bdate.replace(year=today.year, month=2, day=28)

            if birthday > today:
                age = today.year - bdate.year - 1
            else:
                age = today.year - bdate.year

            if age > 39:
                raise ValidationError("Kechirasiz, platformada ro'yxatdan o'tish va dasturlarda qatnashish uchun maksimal yosh 39 yoshgacha bo'lishi kerak.")
            if age < 10:
                raise ValidationError("Iltimos, haqiqiy tug'ilgan sanani kiriting (kamida 10 yosh).")
        return bdate

    def clean_grade(self):
        grade = self.cleaned_data.get('grade')
        if grade not in [9, 10, 11]:
            raise ValidationError("Sinf faqat 9, 10 yoki 11 bo'lishi kerak.")
        return grade

    def clean_target_countries(self):
        countries = self.cleaned_data.get('target_countries')
        if not countries:
            raise ValidationError("Kamida bitta davlatni tanlang.")
        return countries

    def save(self, student: Student) -> Student:
        cd = self.cleaned_data
        if 'first_name' in cd and cd['first_name']:
            student.user.first_name = cd['first_name'].strip()
            student.user.save(update_fields=['first_name'])
        if 'grade' in cd and cd['grade'] is not None:
            student.grade = int(cd['grade'])
        if 'target_countries' in cd and cd['target_countries']:
            student.target_countries = cd['target_countries']
        if 'target_program_type' in cd and cd['target_program_type']:
            student.target_program_type = cd['target_program_type']
        if 'english_level' in cd and cd['english_level']:
            student.english_level = cd['english_level']
        if 'birth_date' in cd and cd['birth_date']:
            student.birth_date = cd['birth_date']
            student.birth_year = cd['birth_date'].year
        if 'region' in cd and cd['region']:
            student.region = cd['region']
        if 'city' in cd and cd['city'] is not None:
            student.city = cd['city']
        if 'interests' in cd and cd['interests'] is not None:
            student.interests = cd['interests']
        if 'target_field_of_study' in cd and cd['target_field_of_study']:
            student.target_field_of_study = cd['target_field_of_study']
        if 'target_career' in cd and cd['target_career'] is not None:
            student.target_career = cd['target_career']
        if 'budget_preference' in cd and cd['budget_preference']:
            student.budget_preference = cd['budget_preference']

        student.save()
        return student


class CertificateStepForm(forms.Form):
    """
    Step 2: Certificate details and section breakdown validation.
    """
    HAS_CERT_CHOICES = [
        ('yes', 'Ha, xalqaro yoki milliy sertifikatim bor (IELTS, SAT, TOEFL, DET, CEFR)'),
        ('no', 'Yo\'q, menda hali til sertifikati yo\'q'),
    ]

    has_certificate = forms.ChoiceField(
        choices=HAS_CERT_CHOICES,
        label="Sizda xalqaro yoki milliy til bilish sertifikati bormi?",
        initial='yes',
        widget=forms.RadioSelect(attrs={'class': 'peer hidden'}),
        required=True
    )
    certificate_type = forms.ChoiceField(
        choices=[('', 'Sertifikat turini tanlang...')] + list(TestCertificate.CERTIFICATE_TYPE_CHOICES),
        label="Sertifikat turi",
        required=False,
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-3 rounded-xl border border-slate-300 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 text-slate-800'
        })
    )
    test_date = forms.DateField(
        label="Imtihon topshirilgan sana",
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'max': timezone.localdate().isoformat(),
            'class': 'w-full px-4 py-3 rounded-xl border border-slate-300 focus:ring-2 focus:ring-orange-500 focus:border-orange-500 text-slate-800'
        })
    )
    overall_score = forms.CharField(
        max_length=20,
        label="Umumiy ball (Overall score / Band)",
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'Masalan: 7.5 (IELTS), 1420 (SAT), 105 (TOEFL), 130 (DET), C1 (CEFR)',
            'class': 'w-full px-4 py-3 rounded-xl border border-slate-300 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 text-slate-800'
        })
    )

    # Section scores
    reading = forms.FloatField(
        required=False,
        widget=forms.NumberInput(attrs={'step': 'any', 'placeholder': 'Reading', 'class': 'w-full px-3 py-2 rounded-lg border border-slate-300 focus:ring-2 focus:ring-indigo-500 text-slate-800'})
    )
    listening = forms.FloatField(
        required=False,
        widget=forms.NumberInput(attrs={'step': 'any', 'placeholder': 'Listening', 'class': 'w-full px-3 py-2 rounded-lg border border-slate-300 focus:ring-2 focus:ring-indigo-500 text-slate-800'})
    )
    writing = forms.FloatField(
        required=False,
        widget=forms.NumberInput(attrs={'step': 'any', 'placeholder': 'Writing', 'class': 'w-full px-3 py-2 rounded-lg border border-slate-300 focus:ring-2 focus:ring-indigo-500 text-slate-800'})
    )
    speaking = forms.FloatField(
        required=False,
        widget=forms.NumberInput(attrs={'step': 'any', 'placeholder': 'Speaking', 'class': 'w-full px-3 py-2 rounded-lg border border-slate-300 focus:ring-2 focus:ring-indigo-500 text-slate-800'})
    )
    grammar = forms.FloatField(
        required=False,
        widget=forms.NumberInput(attrs={'step': 'any', 'placeholder': 'Grammar', 'class': 'w-full px-3 py-2 rounded-lg border border-slate-300 focus:ring-2 focus:ring-indigo-500 text-slate-800'})
    )
    ebrw = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={'placeholder': 'EBRW (200-800)', 'class': 'w-full px-3 py-2 rounded-lg border border-slate-300 focus:ring-2 focus:ring-indigo-500 text-slate-800'})
    )
    math = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={'placeholder': 'Math (200-800)', 'class': 'w-full px-3 py-2 rounded-lg border border-slate-300 focus:ring-2 focus:ring-indigo-500 text-slate-800'})
    )
    comprehension = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={'placeholder': 'Comprehension (10-160)', 'class': 'w-full px-3 py-2 rounded-lg border border-slate-300 focus:ring-2 focus:ring-indigo-500 text-slate-800'})
    )
    production = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={'placeholder': 'Production (10-160)', 'class': 'w-full px-3 py-2 rounded-lg border border-slate-300 focus:ring-2 focus:ring-indigo-500 text-slate-800'})
    )
    conversation = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={'placeholder': 'Conversation (10-160)', 'class': 'w-full px-3 py-2 rounded-lg border border-slate-300 focus:ring-2 focus:ring-indigo-500 text-slate-800'})
    )
    literacy = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={'placeholder': 'Literacy (10-160)', 'class': 'w-full px-3 py-2 rounded-lg border border-slate-300 focus:ring-2 focus:ring-indigo-500 text-slate-800'})
    )
    cefr_level = forms.ChoiceField(
        choices=[('', 'CEFR darajasini tanlang...'), ('C2', 'C2 (Mastery)'), ('C1', 'C1 (Advanced)'), ('B2', 'B2 (Vantage)'), ('B1', 'B1 (Threshold)'), ('A2', 'A2 (Waystage)'), ('A1', 'A1 (Breakthrough)')],
        required=False,
        widget=forms.Select(attrs={'class': 'w-full px-4 py-3 rounded-xl border border-slate-300 focus:ring-2 focus:ring-indigo-500 text-slate-800'})
    )

    def clean(self):
        cleaned_data = super().clean()
        has_cert = cleaned_data.get('has_certificate')

        if has_cert in ['yes', True, 'True']:
            cert_type = cleaned_data.get('certificate_type')
            test_date = cleaned_data.get('test_date')
            overall_raw = cleaned_data.get('overall_score')

            if not cert_type:
                self.add_error('certificate_type', "Iltimos, sertifikat turini tanlang.")
            if not test_date:
                self.add_error('test_date', "Imtihon topshirilgan sanani kiriting.")
            elif test_date > timezone.localdate():
                self.add_error('test_date', "Sertifikat sanasi kelajakda bo'lishi mumkin emas.")

            if cert_type == 'cefr':
                level = cleaned_data.get('cefr_level') or (str(overall_raw).strip().upper() if overall_raw else '')
                if level not in ['A1', 'A2', 'B1', 'B2', 'C1', 'C2']:
                    self.add_error('overall_score', "CEFR darajasi A1, A2, B1, B2, C1 yoki C2 bo'lishi kerak.")
                cleaned_data['overall_score'] = level

            elif cert_type == 'ielts':
                if not overall_raw:
                    self.add_error('overall_score', "IELTS umumiy ballini kiriting.")
                else:
                    try:
                        ov = float(overall_raw)
                        if not (0.0 <= ov <= 9.0 and (round(ov * 2) == ov * 2)):
                            self.add_error('overall_score', "IELTS bali 0.0 dan 9.0 gacha va 0.5 qadamli bo'lishi kerak.")
                    except ValueError:
                        self.add_error('overall_score', "IELTS bali to'g'ri son shaklida kiritilishi kerak.")

                for sec in ['reading', 'listening', 'writing', 'speaking']:
                    val = cleaned_data.get(sec)
                    if val is not None:
                        if not (0.0 <= val <= 9.0 and (round(val * 2) == val * 2)):
                            self.add_error(sec, f"IELTS {sec} bali 0.0 dan 9.0 gacha va 0.5 qadamli bo'lishi kerak.")

            elif cert_type == 'toefl':
                if not overall_raw:
                    self.add_error('overall_score', "TOEFL iBT umumiy ballini kiriting.")
                else:
                    try:
                        ov = int(float(overall_raw))
                        if not (0 <= ov <= 120):
                            self.add_error('overall_score', "TOEFL bali 0 dan 120 gacha bo'lishi kerak.")
                    except ValueError:
                        self.add_error('overall_score', "TOEFL bali butun son bo'lishi kerak.")

                for sec in ['reading', 'listening', 'writing', 'speaking']:
                    val = cleaned_data.get(sec)
                    if val is not None:
                        if not (0 <= val <= 30):
                            self.add_error(sec, f"TOEFL {sec} bali 0 dan 30 gacha bo'lishi kerak.")

            elif cert_type == 'sat':
                if not overall_raw:
                    self.add_error('overall_score', "SAT umumiy ballini kiriting.")
                else:
                    try:
                        ov = int(float(overall_raw))
                        if not (400 <= ov <= 1600 and ov % 10 == 0):
                            self.add_error('overall_score', "SAT bali 400 dan 1600 gacha va 10 ga karrali bo'lishi kerak.")
                    except ValueError:
                        self.add_error('overall_score', "SAT bali butun son bo'lishi kerak.")

                ebrw = cleaned_data.get('ebrw')
                if ebrw is not None and not (200 <= ebrw <= 800 and ebrw % 10 == 0):
                    self.add_error('ebrw', "SAT EBRW bali 200 dan 800 gacha va 10 ga karrali bo'lishi kerak.")
                math_val = cleaned_data.get('math')
                if math_val is not None and not (200 <= math_val <= 800 and math_val % 10 == 0):
                    self.add_error('math', "SAT Math bali 200 dan 800 gacha va 10 ga karrali bo'lishi kerak.")

            elif cert_type == 'duolingo':
                if not overall_raw:
                    self.add_error('overall_score', "Duolingo DET umumiy ballini kiriting.")
                else:
                    try:
                        ov = int(float(overall_raw))
                        if not (10 <= ov <= 160 and ov % 5 == 0):
                            self.add_error('overall_score', "Duolingo DET bali 10 dan 160 gacha va 5 ga karrali bo'lishi kerak.")
                    except ValueError:
                        self.add_error('overall_score', "Duolingo DET bali butun son bo'lishi kerak.")

        return cleaned_data

    def get_section_scores(self) -> dict:
        """Constructs section_scores dictionary from cleaned fields."""
        cd = self.cleaned_data
        ctype = cd.get('certificate_type')
        scores = {}

        if ctype == 'ielts':
            for k in ['reading', 'listening', 'writing', 'speaking']:
                if cd.get(k) is not None:
                    scores[k] = float(cd[k])
        elif ctype == 'toefl':
            for k in ['reading', 'listening', 'writing', 'speaking']:
                if cd.get(k) is not None:
                    scores[k] = int(cd[k])
        elif ctype == 'sat':
            if cd.get('ebrw') is not None:
                scores['ebrw'] = int(cd['ebrw'])
            if cd.get('math') is not None:
                scores['math'] = int(cd['math'])
        elif ctype == 'duolingo':
            for k in ['comprehension', 'production', 'conversation', 'literacy']:
                if cd.get(k) is not None:
                    scores[k] = int(cd[k])
        elif ctype == 'cefr':
            level = cd.get('cefr_level') or str(cd.get('overall_score', '')).strip().upper()
            if level:
                scores['cefr_level'] = level

        return scores


class TimelineStepForm(forms.Form):
    """
    Step 4: Duration of the Dual-Track study plan (1-8 months) and target test date.
    """
    TIMELINE_CHOICES = [
        (1, "1 oy — Tezkor va intensiv tayyorgarlik (4 hafta)"),
        (2, "2 oy — Jadallashtirilgan amaliy reja (8 hafta)"),
        (3, "3 oy — 12 haftalik maqsadli grant tayyorgarligi"),
        (4, "4 oy — Standart 16 haftalik muvozanatli reja"),
        (5, "5 oy — Kengaytirilgan chuqur tayyorgarlik (20 hafta)"),
        (6, "6 oy — To'liq 24 haftalik Dual-Track reja (Tavsiya etiladi)"),
        (7, "7 oy — Uzoq muddatli bosqichma-bosqich reja (28 hafta)"),
        (8, "8 oy — Keng qamrovli 32 haftalik strategik dastur"),
    ]

    plan_timeline_months = forms.TypedChoiceField(
        choices=TIMELINE_CHOICES,
        coerce=int,
        initial=6,
        label="Tayyorgarlik davomiyligini tanlang (1 oydan 8 oygacha)",
        widget=forms.RadioSelect(attrs={'class': 'peer hidden'}),
        required=True,
        error_messages={'required': "Iltimos, rejalashtirilgan tayyorgarlik davomiyligini tanlang."}
    )
    planned_test_date = forms.DateField(
        label="Rejalashtirilgan rasmiy imtihon sanasi (ixtiyoriy)",
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'w-full px-4 py-3 rounded-xl border border-slate-300 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 text-slate-800'
        })
    )

    def clean_plan_timeline_months(self):
        months = self.cleaned_data.get('plan_timeline_months')
        if not (1 <= months <= 8):
            raise ValidationError("Tayyorgarlik muddati 1 oydan 8 oygacha bo'lishi shart.")
        return months

    def clean_planned_test_date(self):
        p_date = self.cleaned_data.get('planned_test_date')
        if p_date and p_date <= timezone.localdate():
            raise ValidationError("Rejalashtirilgan imtihon sanasi kelajakda bo'lishi kerak.")
        return p_date
