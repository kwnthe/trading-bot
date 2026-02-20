from django.urls import re_path
from backtests.consumers import LiveChartConsumer

websocket_urlpatterns = [
    re_path(r'ws/live/(?P<session_id>[\w-]+)/$', LiveChartConsumer.as_asgi()),
]
