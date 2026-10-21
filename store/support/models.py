from django.conf import settings
from django.db import models
from django.utils import timezone

class Ticket(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='support_tickets')
    title = models.CharField(max_length=160, default='گفتگو با پشتیبانی')
    status = models.CharField(max_length=12, choices=[('open','باز'),('closed','بسته')], default='open')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(default=timezone.now, db_index=True)
    class Meta:
        ordering = ['-updated_at', '-pk']
        constraints = [models.UniqueConstraint(fields=['user'], condition=models.Q(status='open'), name='one_open_support_ticket_per_user')]

class SupportMessage(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    is_staff = models.BooleanField(default=False)
    sender_name = models.CharField(max_length=160)
    text = models.TextField(max_length=4000)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ['pk']
