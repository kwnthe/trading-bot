from django.urls import path

from . import views


urlpatterns = [
    path("", views.index, name="index"),
    path("run/", views.run_backtest, name="run_backtest"),
    path("api/run/", views.api_run_backtest, name="api_run_backtest"),
    path("api/params/", views.api_params, name="api_params"),
    path("api/strategies/", views.api_strategies, name="api_strategies"),
    path("api/live/run/", views.api_live_run, name="api_live_run"),
    path("api/live/active/", views.api_live_active, name="api_live_active"),
    path("api/live/<str:session_id>/status/", views.api_live_status, name="api_live_status"),
    path("api/live/<str:session_id>/snapshot/", views.api_live_snapshot, name="api_live_snapshot"),
    path("api/live/<str:session_id>/stop/", views.api_live_stop, name="api_live_stop"),
    path("jobs/<str:job_id>/", views.job_detail, name="job_detail"),
    path("api/jobs/<str:job_id>/status/", views.job_status, name="job_status"),
    path("api/jobs/<str:job_id>/result/", views.job_result, name="job_result"),
    path("api/presets/", views.presets_list_or_save, name="presets_list_or_save"),
    path("api/presets/<str:name>/", views.preset_get_or_delete, name="preset_get_or_delete"),
]

