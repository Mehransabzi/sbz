from datetime import timedelta
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import transaction, IntegrityError
from django.db.models import Q
from django.http import JsonResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST
from .models import Ticket, SupportMessage

staff_required = user_passes_test(lambda u: u.is_authenticated and u.is_staff, login_url='accounts:login')

def owned_ticket(request, ticket_id):
    rows = Ticket.objects.all() if request.user.is_staff else Ticket.objects.filter(user=request.user)
    return get_object_or_404(rows, pk=ticket_id)

def message_data(row):
    return {'id':row.pk, 'text':row.text, 'is_staff':row.is_staff, 'sender':row.sender_name, 'time':timezone.localtime(row.created_at).strftime('%Y/%m/%d %H:%M')}

def selected_ticket(rows, value):
    try:
        return get_object_or_404(rows, pk=int(value))
    except (TypeError, ValueError):
        raise Http404

@login_required
@require_http_methods(['GET','POST'])
def customer(request):
    if request.method == 'POST':
        title = request.POST.get('title','').strip()[:160] or 'گفتگو با پشتیبانی'
        ticket, _ = Ticket.objects.get_or_create(user=request.user,status='open',defaults={'title':title})
        return redirect(reverse('support:customer')+'?ticket='+str(ticket.pk))
    tickets = Ticket.objects.filter(user=request.user)
    selected = selected_ticket(tickets, request.GET['ticket']) if request.GET.get('ticket') else tickets.first()
    return chat_page(request,tickets,selected,False)

@staff_required
def inbox(request):
    tickets = Ticket.objects.select_related('user').all()
    query = request.GET.get('q','').strip()[:100]
    if query:
        tickets = tickets.filter(Q(user__first_name__icontains=query)|Q(user__last_name__icontains=query)|Q(user__phone__icontains=query)|Q(title__icontains=query))
    selected = selected_ticket(Ticket.objects.select_related('user'), request.GET['ticket']) if request.GET.get('ticket') else tickets.first()
    return chat_page(request,tickets,selected,True)

def chat_page(request,tickets,selected,staff):
    from django.core.paginator import Paginator
    rows = list(selected.messages.select_related('sender').order_by('-pk')[:100]) if selected else []
    rows.reverse()
    return render(request,'support/chat.html',{'parent_template':'controlpanel/base.html' if staff else 'storefront/base.html','tickets':Paginator(tickets,30).get_page(request.GET.get('page')),'ticket':selected,'chat_messages':rows,'staff_support':staff,'last_id':rows[-1].pk if rows else 0,'first_id':rows[0].pk if rows else 0,'has_older':bool(rows and selected.messages.filter(pk__lt=rows[0].pk).exists()),'query':request.GET.get('q','')})

@login_required
@require_http_methods(['GET','POST'])
def messages_api(request,ticket_id):
    ticket = owned_ticket(request,ticket_id)
    if request.method == 'POST':
        text = request.POST.get('text','').strip()
        if not text or len(text)>4000:
            return JsonResponse({'error':'پیام باید بین ۱ تا ۴۰۰۰ حرف باشد.'},status=400)
        with transaction.atomic():
            # Acquire a write lock before reading on SQLite too.
            Ticket.objects.filter(pk=ticket.pk).update(updated_at=timezone.now())
            ticket = get_object_or_404(Ticket.objects.select_for_update(),pk=ticket.pk)
            # Persisted rate limit works across worker processes.
            if SupportMessage.objects.filter(sender=request.user,created_at__gte=timezone.now()-timedelta(minutes=1)).count()>=20:
                return JsonResponse({'error':'کمی صبر کنید و سپس پیام بعدی را بفرستید.'},status=429)
            if ticket.status != 'open':
                return JsonResponse({'error':'این گفتگو بسته شده است؛ یک درخواست تازه باز کنید.'},status=409)
            row = SupportMessage.objects.create(ticket=ticket,sender=request.user,is_staff=request.user.is_staff,sender_name=(request.user.get_full_name() or ('پشتیبانی فروشگاه' if request.user.is_staff else request.user.phone or request.user.username))[:160],text=text)
            ticket.updated_at = timezone.now()
            ticket.save(update_fields=['updated_at'])
        if request.headers.get('Accept') == 'application/json':
            return JsonResponse({'message':message_data(row)})
        return redirect((reverse('controlpanel:support-inbox') if request.user.is_staff else reverse('support:customer'))+'?ticket='+str(ticket.pk))
    try:
        after = min(9223372036854775807,max(0,int(request.GET.get('after',0))))
    except (TypeError,ValueError):
        after = 0
    before = request.GET.get('before')
    if before:
        try:
            before = min(9223372036854775807,max(1,int(before)))
        except (TypeError,ValueError):
            return JsonResponse({'error':'شناسه پیام نامعتبر است.'},status=400)
        rows = list(ticket.messages.filter(pk__lt=before).order_by('-pk')[:101])
        response = JsonResponse({'messages':[message_data(row) for row in reversed(rows[:100])],'has_more':len(rows)>100,'status':ticket.status})
    else:
        rows = list(ticket.messages.filter(pk__gt=after).order_by('pk')[:101])
        known = request.GET.get('known','')[:2400].split(',')[:100]
        known = [int(pk) for pk in known if pk.isdecimal() and len(pk)<19]
        existing = set(ticket.messages.filter(pk__in=known).values_list('pk',flat=True))
        response = JsonResponse({'messages':[message_data(row) for row in rows[:100]],'deleted_ids':[pk for pk in known if pk not in existing],'has_more':len(rows)>100,'status':ticket.status})
    response['Cache-Control'] = 'no-store'
    return response

@staff_required
@require_POST
def delete_ticket(request,ticket_id):
    ticket = get_object_or_404(Ticket,pk=ticket_id)
    if request.POST.get('confirmation') == 'DELETE':
        ticket.delete()
        messages.success(request,'گفتگو و همه پیام‌های آن حذف شد.')
    return redirect('controlpanel:support-inbox')

@staff_required
@require_POST
def delete_message(request,message_id):
    row = get_object_or_404(SupportMessage,pk=message_id)
    ticket_id = row.ticket_id
    if request.POST.get('confirmation') == 'DELETE':
        row.delete()
    return redirect(reverse('controlpanel:support-inbox')+'?ticket='+str(ticket_id))

@staff_required
@require_POST
def ticket_status(request,ticket_id):
    ticket = get_object_or_404(Ticket,pk=ticket_id)
    status = request.POST.get('status')
    if status in ['open','closed']:
        try:
            with transaction.atomic():
                ticket.status=status
                ticket.save(update_fields=['status'])
        except IntegrityError:
            messages.error(request,'این مشتری یک گفتگوی باز دیگر دارد؛ ابتدا آن را ببندید.')
    return redirect(reverse('controlpanel:support-inbox')+'?ticket='+str(ticket.pk))
