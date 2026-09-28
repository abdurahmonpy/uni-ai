"""
Views for multi-step intelligent onboarding wizard, certificate qualification,
diagnostic testing, AI university matching, and dual-track study plan activation.
"""
import logging
from datetime import datetime
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone

from apps.accounts.models import Student
from apps.onboarding.models import TestCertificate, DiagnosticResult
from apps.programs.models import Program, StudentTargetSelection
from .forms import OnboardingStep1Form, CertificateStepForm, TimelineStepForm

from apps.services import certificate_service
from apps.services import matching_service
from apps.services import study_plan_service
from apps.services import task_service
from apps.services.diagnostic_service import (
    get_default_diagnostic_test,
    process_diagnostic_submission,
    SKILL_NAMES
)
from apps.services.score_service import calculate_overall_ready_score

logger = logging.getLogger(__name__)


@login_required
def step_1_view(request):
    """
    Step 1: Student academic intake, demographics, region, interests, and target programs.
    """
    student, _ = Student.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        form = OnboardingStep1Form(request.POST)
        if form.is_valid():
            form.save(student)
            request.session.pop('onboarding_step_1_step', None)
            messages.success(request, "Profil ma'lumotlaringiz muvaffaqiyatli saqlandi.")
            return redirect('onboarding:step_2_certificate')
    else:
        initial_data = {}
        if request.user.first_name:
            initial_data['first_name'] = request.user.first_name
        if student.grade:
            initial_data['grade'] = student.grade
        if student.target_countries:
            initial_data['target_countries'] = student.target_countries
        if student.target_program_type:
            initial_data['target_program_type'] = student.target_program_type
        if student.english_level:
            initial_data['english_level'] = student.english_level
        if student.birth_date:
            initial_data['birth_date'] = student.birth_date
        elif student.birth_year:
            from datetime import date
            initial_data['birth_date'] = date(student.birth_year, 1, 1)
        if student.region:
            initial_data['region'] = student.region
        if student.city:
            initial_data['city'] = student.city
        if student.interests:
            initial_data['interests'] = student.interests
        if student.target_field_of_study:
            initial_data['target_field_of_study'] = student.target_field_of_study
        if student.target_career:
            initial_data['target_career'] = student.target_career
        if student.budget_preference:
            initial_data['budget_preference'] = student.budget_preference

        form = OnboardingStep1Form(initial=initial_data)

    saved_step = request.session.get('onboarding_step_1_step', 1)

    return render(request, 'onboarding/step_1.html', {
        'form': form,
        'student': student,
        'step_number': 1,
        'total_steps': 3,
        'saved_step': saved_step,
    })


@login_required
def save_step1_draft_view(request):
    """
    Auto-save endpoint for Onboarding Step 1.
    Saves in-progress answers into database and session so that
    refreshing the page never loses user's filled data or current question.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': "Faqat POST so'rovi qabul qilinadi."}, status=405)

    student, _ = Student.objects.get_or_create(user=request.user)

    step = request.POST.get('step')
    if step:
        try:
            request.session['onboarding_step_1_step'] = int(step)
        except (ValueError, TypeError):
            pass

    first_name = request.POST.get('first_name', '').strip()
    if first_name:
        request.user.first_name = first_name
        request.user.save(update_fields=['first_name'])

    grade = request.POST.get('grade')
    if grade:
        try:
            student.grade = int(grade)
        except (ValueError, TypeError):
            pass

    region = request.POST.get('region', '').strip()
    if region:
        student.region = region

    city = request.POST.get('city', '').strip()
    if city:
        student.city = city

    birth_date_str = request.POST.get('birth_date', '').strip()
    if birth_date_str:
        try:
            student.birth_date = datetime.strptime(birth_date_str, '%Y-%m-%d').date()
            student.birth_year = student.birth_date.year
        except ValueError:
            pass

    target_career = request.POST.get('target_career', '').strip()
    if target_career:
        student.target_career = target_career

    target_field_of_study = request.POST.get('target_field_of_study', '').strip()
    if target_field_of_study:
        student.target_field_of_study = target_field_of_study

    target_countries = request.POST.getlist('target_countries')
    if target_countries:
        student.target_countries = target_countries

    interests = request.POST.getlist('interests')
    if interests:
        student.interests = interests

    budget_preference = request.POST.get('budget_preference', '').strip()
    if budget_preference:
        student.budget_preference = budget_preference

    target_program_type = request.POST.get('target_program_type', '').strip()
    if target_program_type:
        student.target_program_type = target_program_type

    student.save()
    return JsonResponse({'status': 'ok'})


@login_required
def step_2_certificate_view(request):
    """
    Step 2: Certificate intake, 3-year validity evaluation, and diagnostic routing.
    - Valid certificate (<= 1095 days): Bypasses diagnostic test, populates SkillScores, redirects to Step 3.
    - Expired (> 1095 days) or No certificate: Redirects to Diagnostic test.
    """
    student, _ = Student.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        form = CertificateStepForm(request.POST)
        if form.is_valid():
            has_cert = form.cleaned_data.get('has_certificate')

            if has_cert in ['yes', True, 'True']:
                cert_type = form.cleaned_data['certificate_type']
                test_date = form.cleaned_data['test_date']
                overall_score = form.cleaned_data['overall_score']
                section_scores = form.get_section_scores()

                try:
                    is_valid, age_in_days = certificate_service.check_certificate_validity(test_date)
                    cert, is_valid_saved = certificate_service.process_and_save_certificate(
                        student=student,
                        cert_type=cert_type,
                        test_date=test_date,
                        overall_score=overall_score,
                        section_scores=section_scores
                    )
                except Exception as e:
                    logger.error(f"Certificate processing error: {e}", exc_info=True)
                    messages.error(request, f"Xatolik: {e}")
                    return render(request, 'onboarding/step_2_certificate.html', {
                        'form': form,
                        'student': student,
                        'step_number': 2,
                        'total_steps': 3,
                    })

                # Update user candidate name if provided
                candidate_name = request.POST.get('candidate_name_display', '').strip()
                if candidate_name:
                    parts = candidate_name.split(' ', 1)
                    request.user.first_name = parts[0]
                    if len(parts) > 1:
                        request.user.last_name = parts[1]
                    request.user.save(update_fields=['first_name', 'last_name'])

                # Update student metadata fields if available
                updated_fields = []
                if hasattr(student, 'has_certificate'):
                    student.has_certificate = True
                    updated_fields.append('has_certificate')
                if hasattr(student, 'certificate_type'):
                    student.certificate_type = cert_type
                    updated_fields.append('certificate_type')
                if hasattr(student, 'certificate_test_date'):
                    student.certificate_test_date = test_date
                    updated_fields.append('certificate_test_date')
                if hasattr(student, 'certificate_is_valid'):
                    student.certificate_is_valid = is_valid
                    updated_fields.append('certificate_is_valid')
                if hasattr(student, 'certificate_data'):
                    student.certificate_data = section_scores
                    updated_fields.append('certificate_data')
                if updated_fields:
                    student.save(update_fields=updated_fields)

                if is_valid:
                    messages.success(
                        request,
                        f"Sertifikatingiz ({cert.get_certificate_type_display()}) qabul qilindi va ballaringiz tasdiqlandi! Diagnostika testi o'tkazib yuborildi."
                    )
                    return redirect('onboarding:step_3_matching')
                else:
                    messages.warning(
                        request,
                        "Sertifikatingiz muddati (3 yil) o'tgan. Hozirgi bilim darajangizni aniqlash uchun qisqa diagnostika testini topshiring."
                    )
                    return redirect('onboarding:diagnostic')
            else:
                # No certificate
                if hasattr(student, 'has_certificate'):
                    student.has_certificate = False
                    student.save(update_fields=['has_certificate'])
                messages.info(
                    request,
                    "Bilim darajangizni aniqlash va shaxsiy o'quv rejasini shakllantirish uchun qisqa diagnostika testidan o'ting."
                )
                return redirect('onboarding:diagnostic')
    else:
        initial_data = {}
        latest_cert = student.test_certificates.order_by('-test_date', '-created_at').first()
        if latest_cert:
            initial_data = {
                'has_certificate': 'yes',
                'certificate_type': latest_cert.certificate_type,
                'test_date': latest_cert.test_date,
                'overall_score': latest_cert.overall_score,
            }
            if latest_cert.section_scores and isinstance(latest_cert.section_scores, dict):
                initial_data.update(latest_cert.section_scores)
        form = CertificateStepForm(initial=initial_data)

    return render(request, 'onboarding/step_2_certificate.html', {
        'form': form,
        'student': student,
        'step_number': 2,
        'total_steps': 3,
    })


@login_required
def parse_certificate_api_view(request):
    """
    API endpoint to parse uploaded certificate file (PDF/Image)
    and return extracted data (type, score, date, validity).
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': "Faqat POST so'rovi qabul qilinadi."}, status=405)

    if 'certificate_file' not in request.FILES:
        return JsonResponse({'success': False, 'message': "Sertifikat fayli yuklanmadi."}, status=400)

    uploaded_file = request.FILES['certificate_file']
    try:
        from apps.services.certificate_parser import parse_certificate_file
        result = parse_certificate_file(uploaded_file, uploaded_file.name, student_name=request.user.first_name)
        return JsonResponse(result)
    except Exception as e:
        logger.error(f"Error parsing certificate file: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': f"Faylni tahlil qilishda xatolik yuz berdi: {str(e)}"
        }, status=400)


@login_required
def diagnostic_view(request):
    """
    Step 2 Fallback: Interactive Diagnostic test page (Grammar and Reading only).
    Creates 5 DiagnosticResults and 5 SkillScores, then routes to Step 3 Matching.
    """
    student, _ = Student.objects.get_or_create(user=request.user)
    test_data = get_default_diagnostic_test()

    if request.method == 'POST':
        # Extract reading answers
        reading_answers = {
            q['id']: request.POST.get(q['id'], '').strip()
            for q in test_data['reading']['questions']
            if request.POST.get(q['id'])
        }

        # Extract grammar answers
        grammar_answers = {
            q['id']: request.POST.get(q['id'], '').strip()
            for q in test_data['grammar']['questions']
            if request.POST.get(q['id'])
        }

        answers_payload = {
            'reading_answers': reading_answers,
            'grammar_answers': grammar_answers,
        }
        for k, v in request.POST.items():
            if k not in answers_payload:
                answers_payload[k] = v

        # Process diagnostic grading and save 5 SkillScores & 5 DiagnosticResults
        result_data = process_diagnostic_submission(student, answers_payload)

        messages.success(request, f"Diagnostika testi muvaffaqiyatli topshirildi! Natijangiz: {result_data['overall_ready_score']} ball.")
        return redirect('onboarding:step_3_matching')

    return render(request, 'onboarding/diagnostic.html', {
        'student': student,
        'test_data': test_data,
        'reading': test_data['reading'],
        'grammar': test_data['grammar'],
        'step_number': 2,
        'total_steps': 3,
    })


@login_required
def step_3_matching_view(request):
    """
    Step 3: AI-Driven University & Grant Matching.
    Presents curated real recommendations with match %, details, and admission criteria.
    Captures multi-selection of target universities and grants.
    Final step of onboarding: completes onboarding and redirects directly to dashboard.
    """
    student, _ = Student.objects.get_or_create(user=request.user)

    # Get all curated recommendations from 600+ university catalog sorted by best match
    recommendations = matching_service.get_curated_recommendations(student, limit=None)

    if request.method == 'POST':
        # Accept multiple selected program IDs
        selected_ids_raw = request.POST.getlist('selected_program_ids')
        if not selected_ids_raw:
            primary = request.POST.get('primary_program_id') or request.POST.get('primary_program')
            backups = request.POST.getlist('backup_program_ids') or request.POST.getlist('backup_programs')
            selected_ids_raw = ([primary] if primary else []) + [b for b in backups if b]

        notes = request.POST.get('notes', '').strip()

        # Parse and sanitize unique integer program IDs
        selected_ids = []
        for sid in selected_ids_raw:
            if str(sid).isdigit():
                val = int(sid)
                if val not in selected_ids:
                    selected_ids.append(val)

        # Fallback if empty but recommendations exist
        if not selected_ids and recommendations:
            selected_ids = [recommendations[0]['program_id']]

        if selected_ids:
            try:
                primary_id_int = selected_ids[0]
                backup_ids = selected_ids[1:]

                # Save target selection and register all selected programs into StudentProgram tracking
                matching_service.save_student_target_selection(
                    student=student,
                    primary_program_id=primary_id_int,
                    backup_program_ids=backup_ids,
                    notes=notes
                )

                # Automatically prepare default study plan and daily tasks in background
                try:
                    active_plan = study_plan_service.get_active_study_plan(student)
                    if not active_plan:
                        plan_payload = study_plan_service.generate_dual_track_study_plan(
                            student=student,
                            timeline_months=getattr(student, 'plan_timeline_months', 6) or 6,
                            planned_test_date=getattr(student, 'planned_test_date', None)
                        )
                        study_plan_service.activate_dual_track_study_plan(student, plan_payload)
                    task_service.generate_daily_tasks_for_dual_track(student)
                except Exception as ex:
                    logger.warning(f"Background study plan/tasks provisioning error: {ex}")

                # Mark student onboarding as fully completed
                student.onboarding_completed = True
                student.save(update_fields=['onboarding_completed'])

                messages.success(request, "Tabriklaymiz! Maqsadli oliygohlaringiz muvaffaqiyatli tanlandi.")
                return redirect('dashboard:index')
            except Exception as e:
                logger.error(f"Error saving target selection: {e}")
                messages.error(request, f"Tanlovni saqlashda xatolik: {e}")
        else:
            messages.error(request, "Iltimos, kamida bitta universitet yoki grant dasturini tanlang.")

    target_selection = getattr(student, 'target_selection', None)

    return render(request, 'onboarding/step_3_matching.html', {
        'student': student,
        'recommendations': recommendations,
        'target_selection': target_selection,
        'step_number': 3,
        'total_steps': 3,
        'hide_header': True,
    })


@login_required
def step_4_timeline_view(request):
    """
    Step 4 is deprecated (no study plan questionnaire).
    Redirects directly to dashboard if onboarding completed, otherwise to step 3.
    """
    student, _ = Student.objects.get_or_create(user=request.user)
    if student.onboarding_completed:
        return redirect('dashboard:index')
    return redirect('onboarding:step_3_matching')


@login_required
def results_view(request):
    """
    Step 5 / Final: Comprehensive summary of student readiness, target university,
    and Dual-Track Study Plan (Track A & Track B) with direct CTA to dashboard.
    """
    student, _ = Student.objects.get_or_create(user=request.user)

    skill_scores = list(student.skill_scores.all())
    active_plan = study_plan_service.get_active_study_plan(student)
    target_selection = getattr(student, 'target_selection', None)
    latest_log = student.progress_logs.order_by('-date', '-created_at').first()

    ready_score = student.overall_ready_score
    if not ready_score and latest_log:
        ready_score = latest_log.overall_ready_score

    weakest_skill = None
    if skill_scores:
        weakest_skill = min(skill_scores, key=lambda s: s.current_score)

    plan_data = active_plan.generated_by_ai if active_plan else {}
    track_a = plan_data.get('track_a', {})
    track_b = plan_data.get('track_b', {})
    milestones_a = track_a.get('milestones', [])
    milestones_b = track_b.get('milestones', [])

    return render(request, 'onboarding/results.html', {
        'student': student,
        'skill_scores': skill_scores,
        'active_plan': active_plan,
        'target_selection': target_selection,
        'ready_score': ready_score,
        'weakest_skill': weakest_skill,
        'plan_data': plan_data,
        'track_a': track_a,
        'track_b': track_b,
        'milestones_a': milestones_a,
        'milestones_b': milestones_b,
    })
