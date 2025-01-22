from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.db import transaction
from ..models import Task, AutomationLog
import json

@csrf_exempt
@require_http_methods(["POST"])
def create_task(request, business_id):
    try:
        data = json.loads(request.body)
        with transaction.atomic():
            task = Task.objects.create(
                business_id=business_id,
                task_type=data['task_type'],
                frequency=data['frequency'],
                status='PENDING',
                next_run=data.get('scheduled_time') or calculate_initial_run(data['frequency']),
                parameters=data.get('parameters', {})
            )
            AutomationLog.objects.create(
                task=task,
                status='PENDING',
                details=f"Scheduled {task.get_task_type_display()} task"
            )
            return JsonResponse({
                'status': 'success',
                'task': task_to_dict(task)
            })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@csrf_exempt
@require_http_methods(["POST"])
def update_task(request, business_id):
    try:
        data = json.loads(request.body)
        task = Task.objects.get(id=data['task_id'], business_id=business_id)
        
        with transaction.atomic():
            task.frequency = data['frequency']
            if data['frequency'] == 'CUSTOM' and data.get('scheduled_time'):
                task.next_run = data['scheduled_time']
            elif task.frequency != 'CUSTOM':
                task.next_run = task.calculate_next_run()
            
            task.save()
            AutomationLog.objects.create(
                task=task,
                status='UPDATED',
                details=f"Updated schedule to {task.frequency}"
            )
            return JsonResponse({
                'status': 'success', 
                'task': task_to_dict(task)
            })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

def calculate_initial_run(frequency):
    from django.utils import timezone
    now = timezone.now()
    
    if frequency == 'DAILY':
        return now + timezone.timedelta(days=1)
    if frequency == 'WEEKLY':
        return now + timezone.timedelta(weeks=1)
    if frequency == 'MONTHLY':
        return now + timezone.timedelta(days=30)  # Approximate month
    return now

def task_to_dict(task):
    return {
        'id': task.id,
        'task_type': task.task_type,
        'frequency': task.frequency,
        'status': task.status,
        'next_run': task.next_run.isoformat() if task.next_run else None,
        'last_run': task.last_run.isoformat() if task.last_run else None,
        'parameters': task.parameters
    }
