from django.urls import path
from . import views
app_name = 'support'
urlpatterns = [path('',views.customer,name='customer'),path('<int:ticket_id>/messages/',views.messages_api,name='messages'),path('<int:ticket_id>/delete/',views.delete_ticket,name='delete-ticket'),path('message/<int:message_id>/delete/',views.delete_message,name='delete-message'),path('<int:ticket_id>/status/',views.ticket_status,name='status')]
