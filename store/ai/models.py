from django.conf import settings
from django.db import models
from django.utils import timezone


class ChatConversation(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ai_conversations")
    title = models.CharField(max_length=160, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [models.Index(fields=["user", "-updated_at"])]

    def __str__(self):
        return self.title or f"گفتگو {self.pk}"


class ChatMessage(models.Model):
    ROLE_CHOICES = [("user", "مشتری"), ("assistant", "ربات")]
    conversation = models.ForeignKey(ChatConversation, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=12, choices=ROLE_CHOICES)
    content = models.TextField(max_length=12000)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["created_at", "pk"]
        indexes = [models.Index(fields=["conversation", "created_at"])]

    def __str__(self):
        return f"{self.conversation_id}:{self.role}:{self.pk}"


class CustomerImageUsage(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="image_usage")
    day = models.DateField(db_index=True)
    count = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "day"], name="unique_customer_image_day")]
        ordering = ["-day"]
        verbose_name = "مصرف روزانه بررسی تصویر"
        verbose_name_plural = "مصرف بررسی تصاویر مشتریان"
