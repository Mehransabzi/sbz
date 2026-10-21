from django.urls import path
from .views import AdminAnalysisView, CustomerChatView, NewCustomerConversationView

app_name = "ai_assistant"
urlpatterns = [
    path("chat/", CustomerChatView.as_view(), name="customer-chat"),
    path("conversations/", NewCustomerConversationView.as_view(), name="customer-conversation-create"),
    path("admin-analysis/", AdminAnalysisView.as_view(), name="admin-analysis-api"),
]
