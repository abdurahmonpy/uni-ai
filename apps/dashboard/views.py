"""
Views for student dashboard, Ready Score visualization, streak, and daily tasks.
Integrates Dual-Track Study Plan (Track A & Track B) and Dual Countdowns.
"""
import calendar
import logging
import re
from datetime import date, datetime, timedelta
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone

from apps.accounts.models import Student
from apps.services.score_service import calculate_overall_ready_score, get_student_streak
from apps.services.task_service import generate_daily_tasks_for_student, get_student_weakest_skill
from apps.services.study_plan_service import (
    get_active_study_plan,
    generate_study_plan,
    calculate_default_target_date
)
from apps.dashboard.models import SkillScore, ProgressLog
from apps.programs.models import Program, StudentProgram, StudentTargetSelection, University
from apps.tasks.models import DailyTask
from apps.documents.models import Document

logger = logging.getLogger(__name__)


def parse_deadline_to_date(deadline_str, reference_date=None):
    """
    Parses natural language or ISO deadline strings into the closest future/current date.
    Examples:
    - 'Har yili dekabr oyi oxiri' -> last day of December
    - 'Har yili 10-yanvardan 20-fevralgacha' -> Feb 20
    - '2026-11-01' -> Nov 1, 2026
    """
    if not deadline_str:
        return None

    ref = reference_date or timezone.localdate()
    deadline_str = str(deadline_str).strip()

    # Try explicit ISO date formats first
    for fmt in ('%Y-%m-%d', '%d.%m.%Y', '%d/%m/%Y', '%Y/%m/%d'):
        try:
            d = datetime.strptime(deadline_str, fmt).date()
            if d >= ref:
                return d
            return d
        except ValueError:
            pass

    # Month mapping in Uzbek and English
    month_map = {
        'yanvar': 1, 'january': 1, 'jan': 1,
        'fevral': 2, 'february': 2, 'feb': 2,
        'mart': 3, 'march': 3, 'mar': 3,
        'aprel': 4, 'april': 4, 'apr': 4,
        'may': 5,
        'iyun': 6, 'june': 6, 'jun': 6,
        'iyul': 7, 'july': 7, 'jul': 7,
        'avgust': 8, 'august': 8, 'aug': 8,
        'sentabr': 9, 'sentyabr': 9, 'september': 9, 'sep': 9,
        'oktabr': 10, 'oktyabr': 10, 'october': 10, 'oct': 10,
        'noyabr': 11, 'november': 11, 'nov': 11,
        'dekabr': 12, 'december': 12, 'dec': 12,
    }

    lower_text = deadline_str.lower()

    # Find all months mentioned
    found_months = []
    for m_name, m_num in month_map.items():
        if m_name in lower_text:
            found_months.append((lower_text.find(m_name), m_num))

    if not found_months:
        return None

    # Pick the last mentioned month if range (e.g. "oktyabr — noyabr" -> November deadline)
    found_months.sort(key=lambda x: x[0])
    target_month = found_months[-1][1]

    # Find day of month if specified
    day_match = re.findall(r'(\d{1,2})[\s-]*(?:gacha|dan)?[\s-]*(?:' + '|'.join(month_map.keys()) + r')', lower_text)
    if not day_match:
        num_matches = re.findall(r'\b([1-3]?[0-9])\b', lower_text)
        if num_matches:
            target_day = min(31, int(num_matches[-1]))
        elif 'oxir' in lower_text:
            target_day = calendar.monthrange(ref.year, target_month)[1]
        elif 'bosh' in lower_text:
            target_day = 1
        elif 'o\'rt' in lower_text:
            target_day = 15
        else:
            target_day = calendar.monthrange(ref.year, target_month)[1]
    else:
        target_day = min(31, int(day_match[-1]))

    max_days_in_month = calendar.monthrange(ref.year, target_month)[1]
    target_day = max(1, min(target_day, max_days_in_month))

    target_date = date(ref.year, target_month, target_day)
    if target_date < ref:
        next_max = calendar.monthrange(ref.year + 1, target_month)[1]
        target_date = date(ref.year + 1, target_month, min(target_day, next_max))

    return target_date


def get_nearest_deadline_for_student(student):
    """
    Finds the nearest scholarship deadline for the student.
    Prioritizes tracked programs; falls back to all active programs.
    """
    today = timezone.localdate()

    # 1. Check if student has tracked programs
    tracked_programs = list(
        Program.objects.filter(student_tracking__student=student)
    )

    candidates = tracked_programs if tracked_programs else list(Program.objects.all())
    has_tracked = bool(tracked_programs)

    if not candidates:
        return {
            'days_left': 0,
            'program_name': None,
            'deadline_text': "",
            'deadline': None,
            'has_tracked': False,
            'program': None,
            'display_text': "Muddatlar mavjud emas",
        }

    scored_candidates = []
    for prog in candidates:
        parsed_d = parse_deadline_to_date(prog.deadline, reference_date=today)
        if parsed_d:
            days_left = max(0, (parsed_d - today).days)
        else:
            days_left = 30 + (prog.id * 7) % 60
        scored_candidates.append((days_left, prog))

    scored_candidates.sort(key=lambda x: x[0])
    best_days_left, best_prog = scored_candidates[0]

    return {
        'days_left': best_days_left,
        'program_name': best_prog.name,
        'deadline_text': best_prog.deadline,
        'deadline': best_prog.deadline,
        'has_tracked': has_tracked,
        'program': best_prog,
        'display_text': f"{best_days_left} kun qoldi — {best_prog.name}",
    }


def get_weekly_consistency_for_student(student):
    """
    Generates 7-day Monday through Sunday consistency strip for current week.
    Marks is_completed=True if the student completed daily tasks or logged progress on that date.
    """
    today = timezone.localdate()
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)

    completed_task_dates = set(
        DailyTask.objects.filter(
            student=student,
            date__range=(start_of_week, end_of_week),
            completed=True
        ).values_list('date', flat=True)
    )

    day_labels = [
        ('Du', 'Dushanba'),
        ('Se', 'Seshanba'),
        ('Chor', 'Chorshanba'),
        ('Pay', 'Payshanba'),
        ('Ju', 'Juma'),
        ('Sha', 'Shanba'),
        ('Yak', 'Yakshanba'),
    ]

    weekly_consistency = []
    for i in range(7):
        d = start_of_week + timedelta(days=i)
        short_name, full_name = day_labels[i]
        is_completed = (d in completed_task_dates)
        weekly_consistency.append({
            'day_name': short_name,
            'day_full_name': full_name,
            'day_number': d.day,
            'date': d,
            'is_completed': is_completed,
            'is_today': (d == today),
            'is_future': (d > today),
            'is_past': (d < today),
        })

    return weekly_consistency


@login_required
def dashboard_view(request):
    """
    Main student dashboard view:
    - Checks onboarding status.
    - Displays overall Ready Score (0-100) and daily streak count.
    - Displays 5-skill breakdown (reading, writing, listening, speaking, grammar).
    - Computes and displays Dual Countdowns:
        1) exam_days_left: Days remaining until planned_test_date / target_date.
        2) admission_days_left: Days remaining until primary target program deadline.
    - Displays Dual-Track Study Plan (Track A: Exam Prep & Track B: Applications) with visual progress.
    - Displays categorized today's daily tasks (Track A & Track B).
    - Passes demographic badges and target university details.
    """
    # 1. Check if user has a student profile
    student = getattr(request.user, 'student_profile', None)
    if not student:
        student, _ = Student.objects.get_or_create(user=request.user)

    # 2. Redirect to onboarding if not completed
    if not student.onboarding_completed:
        return redirect('onboarding:step_1')

    today = timezone.localdate()

    # 3. Ensure 5 skill scores exist
    skills_map = {s.skill: s for s in student.skill_scores.all()}
    all_skill_keys = ['reading', 'writing', 'listening', 'speaking', 'grammar']
    for k in all_skill_keys:
        if k not in skills_map:
            s_obj, _ = SkillScore.objects.get_or_create(
                student=student,
                skill=k,
                defaults={'current_score': 50}
            )
            skills_map[k] = s_obj

    # 4. Calculate overall Ready Score and streak
    ready_score = calculate_overall_ready_score(student)
    streak = get_student_streak(student)
    weakest_skill = get_student_weakest_skill(student)

    # 5. Fetch or generate active study plan
    active_plan = get_active_study_plan(student)
    if not active_plan:
        try:
            active_plan = generate_study_plan(student)
        except Exception as e:
            logger.warning(f"Dashboard study plan creation failed: {e}")

    # 6. Ensure today's daily tasks exist (Dual-track: Track A + Track B)
    today_tasks = generate_daily_tasks_for_student(student, task_date=today, count=2)
    today_tasks_track_a = [t for t in today_tasks if t.track == 'track_a']
    today_tasks_track_b = [t for t in today_tasks if t.track == 'track_b']
    completed_tasks_count = sum(1 for t in today_tasks if t.completed)
    total_tasks_count = len(today_tasks)

    # 7. Compute Dual Countdowns
    # A) Exam Countdown (exam_days_left)
    exam_target_date = student.planned_test_date
    if not exam_target_date and active_plan:
        exam_target_date = active_plan.target_date
    if not exam_target_date:
        exam_target_date = calculate_default_target_date(student)

    exam_days_left = max(0, (exam_target_date - today).days) if exam_target_date else 0

    # Extract target exam details
    track_a_payload = active_plan.track_a if active_plan else {}
    exam_title = track_a_payload.get('title') or "Xalqaro Imtihon (IELTS / SAT / DET)"
    exam_target_score = track_a_payload.get('target_score') or "IELTS 7.5+ / SAT 1400+"

    # B) Admission Deadline Countdown (admission_days_left)
    target_selection = StudentTargetSelection.objects.filter(student=student).first()
    primary_program = None
    primary_university = None
    primary_deadline_text = ""
    primary_program_name = ""
    primary_country = ""
    has_primary_target = False
    match_score = None
    backup_programs = []

    if target_selection and target_selection.primary_program:
        primary_program = target_selection.primary_program
        primary_university = primary_program.university
        primary_deadline_text = primary_program.deadline
        primary_program_name = primary_program.name
        primary_country = primary_program.country
        match_score = target_selection.match_score
        has_primary_target = True
        backup_programs = list(target_selection.backup_programs.all())

        parsed_adm = parse_deadline_to_date(primary_program.deadline, reference_date=today)
        admission_days_left = max(0, (parsed_adm - today).days) if parsed_adm else 30
    else:
        # Fallback to nearest deadline from tracked or available programs
        nearest_deadline = get_nearest_deadline_for_student(student)
        admission_days_left = nearest_deadline.get('days_left', 0)
        primary_program_name = nearest_deadline.get('program_name') or "Xalqaro Grant Dasturi"
        primary_deadline_text = nearest_deadline.get('deadline_text') or ""
        primary_program = nearest_deadline.get('program')
        if primary_program:
            primary_university = primary_program.university
            primary_country = primary_program.country
        has_primary_target = nearest_deadline.get('has_tracked', False)

    # 8. Dual-Track Plan Milestones and Progress Calculations
    track_a_data = active_plan.track_a if active_plan else {}
    track_b_data = active_plan.track_b if active_plan else {}
    weekly_schedule = active_plan.weekly_schedule if active_plan else []

    track_a_milestones = track_a_data.get('milestones', [])
    track_b_milestones = track_b_data.get('milestones', [])
    track_a_phases = track_a_data.get('phases', [])
    track_b_phases = track_b_data.get('phases', [])

    # Historical task counts for progress metrics
    track_a_completed_tasks = DailyTask.objects.filter(student=student, track='track_a', completed=True).count()
    track_a_total_tasks = DailyTask.objects.filter(student=student, track='track_a').count()
    if track_a_total_tasks > 0:
        track_a_progress_pct = min(100, round((track_a_completed_tasks / track_a_total_tasks) * 100))
    else:
        track_a_progress_pct = min(100, max(15, round((ready_score or 50) * 0.8)))

    track_b_completed_tasks = DailyTask.objects.filter(student=student, track='track_b', completed=True).count()
    track_b_total_tasks = DailyTask.objects.filter(student=student, track='track_b').count()
    if track_b_total_tasks > 0:
        track_b_progress_pct = min(100, round((track_b_completed_tasks / track_b_total_tasks) * 100))
    else:
        track_b_progress_pct = min(100, max(10, round((ready_score or 50) * 0.7)))

    # 9. Fetch recent progress logs (last 7 logs) & consistency strip
    recent_logs = student.progress_logs.all().order_by('-date', '-created_at')[:7]
    nearest_deadline = get_nearest_deadline_for_student(student)
    weekly_consistency = get_weekly_consistency_for_student(student)

    # Uzbek names for skills
    skill_labels = {
        'reading': "O'qish (Reading)",
        'writing': "Yozish (Writing / SOP)",
        'listening': "Tinglash (Listening)",
        'speaking': "Gapirish (Speaking)",
        'grammar': "Grammatika (Grammar)",
    }

    skills_display = []
    for k in all_skill_keys:
        s_obj = skills_map[k]
        skills_display.append({
            'key': k,
            'label': skill_labels.get(k, k.capitalize()),
            'score': s_obj.current_score,
            'is_weakest': (k == weakest_skill)
        })

    # Demographic badges dictionary
    demographics = {
        'grade_display': student.get_grade_display() if student.grade else f"{student.grade}-sinf" if student.grade else "Sinf belgilanmagan",
        'region_display': student.get_region_display() if student.region else "",
        'field_of_study_display': student.get_target_field_of_study_display() if student.target_field_of_study else "",
        'budget_display': student.get_budget_preference_display() if student.budget_preference else "",
        'target_program_type_display': student.get_target_program_type_display() if student.target_program_type else "Grant dasturlari",
        'english_level_display': student.get_english_level_display() if student.english_level else "",
        'target_countries': student.target_countries or [],
        'target_career': student.target_career or "",
    }

    context = {
        'student': student,
        'demographics': demographics,
        'overall_ready_score': ready_score,
        'streak_count': streak,
        'weakest_skill': weakest_skill,
        'skills_display': skills_display,
        'active_plan': active_plan,
        
        # Dual Countdowns
        'exam_days_left': exam_days_left,
        'exam_target_date': exam_target_date,
        'exam_title': exam_title,
        'exam_target_score': exam_target_score,
        
        'admission_days_left': admission_days_left,
        'primary_program': primary_program,
        'primary_university': primary_university,
        'primary_program_name': primary_program_name,
        'primary_deadline_text': primary_deadline_text,
        'primary_country': primary_country,
        'has_primary_target': has_primary_target,
        'match_score': match_score,
        'backup_programs': backup_programs,
        
        # Tavsiya etilgan universitetlar va dasturlar (Recommended Universities)
        'recommended_programs': list(
            Program.objects.filter(
                country__in=student.target_countries
            ).select_related('university')[:4]
            if student.target_countries and Program.objects.filter(country__in=student.target_countries).exists()
            else Program.objects.all().select_related('university')[:4]
        ),
        
        # Dual-Track Study Plan Data
        'track_a_data': track_a_data,
        'track_b_data': track_b_data,
        'track_a_milestones': track_a_milestones,
        'track_b_milestones': track_b_milestones,
        'track_a_phases': track_a_phases,
        'track_b_phases': track_b_phases,
        'track_a_progress_pct': track_a_progress_pct,
        'track_b_progress_pct': track_b_progress_pct,
        'weekly_schedule': weekly_schedule,
        
        # Daily Tasks
        'today_tasks': today_tasks,
        'today_tasks_track_a': today_tasks_track_a,
        'today_tasks_track_b': today_tasks_track_b,
        'completed_tasks_count': completed_tasks_count,
        'total_tasks_count': total_tasks_count,
        
        # Logs & Consistency
        'recent_logs': recent_logs,
        'today_date': today,
        'nearest_deadline': nearest_deadline,
        'weekly_consistency': weekly_consistency,
        
        # Active Applications & Tracked Programs
        'all_tracked_programs': list(StudentProgram.objects.filter(student=student).select_related('program__university').order_by('-created_at')),
        'applications_summary': {
            'total': StudentProgram.objects.filter(student=student).count(),
            'tracking': StudentProgram.objects.filter(student=student, status='tracking').count(),
            'preparing': StudentProgram.objects.filter(student=student, status='preparing').count(),
            'submitted': StudentProgram.objects.filter(student=student, status='submitted').count(),
            'interview': StudentProgram.objects.filter(student=student, status='interview').count(),
            'accepted': StudentProgram.objects.filter(student=student, status='accepted').count(),
            'rejected': StudentProgram.objects.filter(student=student, status='rejected').count(),
            'waitlisted': StudentProgram.objects.filter(student=student, status='waitlisted').count(),
            'items': StudentProgram.objects.filter(student=student).select_related('program')[:6],
        },
        
        # Student Documents & Essay Hub
        'user_documents': list(Document.objects.filter(student=student).select_related('linked_program').order_by('-created_at')),
        'sop_document': Document.objects.filter(student=student, doc_type='motivation_letter').first(),
        'docs_ready_count': Document.objects.filter(student=student, status='final').count(),
        'docs_total_count': Document.objects.filter(student=student).count(),
    }
    return render(request, 'dashboard/index.html', context)


@login_required
def calendar_view(request):
    """
    Calendar view aggregating program deadlines, tracking bookmarks, and upcoming milestones.
    """
    student, _ = Student.objects.get_or_create(user=request.user)
    today = timezone.localdate()

    # Get month / year from query params or current date
    try:
        current_year = int(request.GET.get('year', today.year))
        current_month = int(request.GET.get('month', today.month))
    except (ValueError, TypeError):
        current_year, current_month = today.year, today.month

    # Clamp month
    if current_month < 1:
        current_month = 12
        current_year -= 1
    elif current_month > 12:
        current_month = 1
        current_year += 1

    cal = calendar.Calendar(firstweekday=0)  # Monday first
    month_days = cal.monthdatescalendar(current_year, current_month)

    # Fetch programs
    all_programs = list(Program.objects.all())
    tracked_program_ids = set(
        Program.objects.filter(student_tracking__student=student).values_list('id', flat=True)
    )

    # Parse deadlines and map by date
    events_by_date = {}
    upcoming_deadlines = []

    for prog in all_programs:
        parsed_d = parse_deadline_to_date(prog.deadline, reference_date=today)
        is_tracked = (prog.id in tracked_program_ids)
        if parsed_d:
            if parsed_d not in events_by_date:
                events_by_date[parsed_d] = []
            event_item = {
                'program': prog,
                'is_tracked': is_tracked,
                'days_left': (parsed_d - today).days,
            }
            events_by_date[parsed_d].append(event_item)

            if parsed_d >= today:
                upcoming_deadlines.append({
                    'date': parsed_d,
                    'program': prog,
                    'is_tracked': is_tracked,
                    'days_left': (parsed_d - today).days,
                })

    upcoming_deadlines.sort(key=lambda x: x['date'])

    # Build calendar grid data
    calendar_weeks = []
    for week in month_days:
        week_days = []
        for day in week:
            is_current_month = (day.month == current_month)
            day_events = events_by_date.get(day, [])
            week_days.append({
                'date': day,
                'day_num': day.day,
                'is_today': (day == today),
                'is_current_month': is_current_month,
                'events': day_events,
                'has_tracked': any(e['is_tracked'] for e in day_events),
            })
        calendar_weeks.append(week_days)

    month_names_uz = [
        "", "Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
        "Iyul", "Avgust", "Sentabr", "Oktabr", "Noyabr", "Dekabr"
    ]

    prev_month = current_month - 1 if current_month > 1 else 12
    prev_year = current_year if current_month > 1 else current_year - 1
    next_month = current_month + 1 if current_month < 12 else 1
    next_year = current_year if current_month < 12 else current_year + 1

    return render(request, 'dashboard/calendar.html', {
        'student': student,
        'current_year': current_year,
        'current_month': current_month,
        'month_name': month_names_uz[current_month],
        'prev_month': prev_month,
        'prev_year': prev_year,
        'next_month': next_month,
        'next_year': next_year,
        'calendar_weeks': calendar_weeks,
        'upcoming_deadlines': upcoming_deadlines,
        'today': today,
    })


@login_required
def stats_view(request):
    """
    Detailed analytics, SkillScore growth charts, Ready Score timeline, and contribution heatmap.
    """
    student, _ = Student.objects.get_or_create(user=request.user)
    today = timezone.localdate()

    # 1. Skill Scores
    skills_map = {s.skill: s for s in student.skill_scores.all()}
    all_skill_keys = ['reading', 'writing', 'listening', 'speaking', 'grammar']
    skill_labels = {
        'reading': "O'qish (Reading)",
        'writing': "Yozish (Writing)",
        'listening': "Tinglash (Listening)",
        'speaking': "Gapirish (Speaking)",
        'grammar': "Grammatika (Grammar)",
    }

    skills_data = []
    for k in all_skill_keys:
        s_obj = skills_map.get(k)
        score = s_obj.current_score if s_obj else 50
        skills_data.append({
            'key': k,
            'label': skill_labels[k],
            'score': score,
        })

    # 2. Historical Progress Logs (last 30 days)
    logs = list(student.progress_logs.all().order_by('date'))[-30:]
    ready_score = calculate_overall_ready_score(student)
    streak = get_student_streak(student)

    # 3. Heatmap Matrix (Past 12 weeks = 84 days)
    start_heatmap = today - timedelta(days=83)
    completed_task_dates = set(
        DailyTask.objects.filter(
            student=student,
            date__gte=start_heatmap,
            completed=True
        ).values_list('date', flat=True)
    )

    heatmap_days = []
    total_completed_tasks = DailyTask.objects.filter(student=student, completed=True).count()

    for i in range(84):
        day_date = start_heatmap + timedelta(days=i)
        is_done = day_date in completed_task_dates
        heatmap_days.append({
            'date': day_date,
            'is_done': is_done,
            'is_today': (day_date == today),
        })

    # 4. Weekly scores for the 7-day mini chart
    day_labels_uz = ['Du', 'Se', 'Chor', 'Pay', 'Ju', 'Sha', 'Yak']
    weekly_scores = []
    for i in range(7):
        day_date = today - timedelta(days=6 - i)
        log = student.progress_logs.filter(date=day_date).order_by('-created_at').first()
        score = log.overall_ready_score if log else ready_score
        weekly_scores.append({
            'label': day_labels_uz[day_date.weekday()],
            'score': score,
            'inverted': 100 - score,  # SVG y-axis: 0 is top, so invert
        })

    return render(request, 'dashboard/stats.html', {
        'student': student,
        'skills_data': skills_data,
        'overall_ready_score': ready_score,
        'streak_count': streak,
        'logs': logs,
        'heatmap_days': heatmap_days,
        'total_completed_tasks': total_completed_tasks,
        'weekly_scores': weekly_scores,
    })

@login_required
def strategy_view(request):
    """
    AI School Counselor / Strategy Dashboard.
    Shows the generated College List (Safety, Match, Reach) and the Study Plan (Roadmap).
    """
    from apps.services.matching_service import get_curated_recommendations
    from apps.services.study_plan_service import get_active_study_plan
    
    student, _ = Student.objects.get_or_create(user=request.user)
    
    # 1. College List (Reach, Match, Safety)
    recommendations = get_curated_recommendations(student, limit=6)
    
    # Categorize them
    safety_schools = [r for r in recommendations if r['match_tier'] == 'safety']
    match_schools = [r for r in recommendations if r['match_tier'] == 'target']
    reach_schools = [r for r in recommendations if r['match_tier'] == 'reach']
    
    # 2. Roadmap / Study Plan
    active_plan = get_active_study_plan(student)
    plan_data = active_plan.generated_by_ai if active_plan else {}
    track_a = plan_data.get('track_a', {})
    track_b = plan_data.get('track_b', {})
    weekly_schedule = plan_data.get('weekly_schedule', [])
    
    return render(request, 'dashboard/strategy.html', {
        'student': student,
        'safety_schools': safety_schools,
        'match_schools': match_schools,
        'reach_schools': reach_schools,
        'active_plan': active_plan,
        'plan_data': plan_data,
        'track_a': track_a,
        'track_b': track_b,
        'weekly_schedule': weekly_schedule,
    })
