from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse, Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie

from .defaults import build_initial_form_data
from .forms import BacktestForm
from .job_store import JobPaths, create_job, is_pid_running, read_status, tail_text_file, write_status
from .params import PARAM_DEFS
from .presets_store import delete_preset, load_presets, normalize_preset_name, upsert_preset
from .services import start_runner_process


def _base_dir() -> Path:
    return Path(settings.BASE_DIR)

def _as_utc_iso(dt: datetime) -> str:
    # HTML datetime-local often yields naive datetimes; treat naive as UTC.
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def _paths_for_job(job_id: str) -> JobPaths:
    job_dir = _base_dir() / "var" / "jobs" / job_id
    if not job_dir.exists():
        raise Http404("Job not found")
    return JobPaths(
        job_dir=job_dir,
        params_json=job_dir / "params.json",
        status_json=job_dir / "status.json",
        result_json=job_dir / "result.json",
        stdout_log=job_dir / "stdout.log",
        stderr_log=job_dir / "stderr.log",
    )


@ensure_csrf_cookie
def index(request: HttpRequest) -> HttpResponse:
    initial = build_initial_form_data()
    form = BacktestForm(initial=initial)
    groups: dict[str, list[dict]] = {}
    for d in PARAM_DEFS:
        # template-friendly representation
        groups.setdefault(d.group, []).append({"def": d, "field": form[d.name]})
    return render(request, "backtests/index.html", {"form": form, "param_groups": groups})


def api_params(request: HttpRequest) -> JsonResponse:
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    initial = build_initial_form_data()

    defs_payload = []
    for d in PARAM_DEFS:
        defs_payload.append(
            {
                "name": d.name,
                "label": d.label,
                "field_type": d.field_type,
                "destination": d.destination,
                "required": d.required,
                "group": d.group,
                "help_text": d.help_text,
                "choices": d.choices or [],
            }
        )

    return JsonResponse({"param_defs": defs_payload, "initial": initial})


def run_backtest(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return redirect("index")

    form = BacktestForm(request.POST)
    if not form.is_valid():
        return render(request, "backtests/index.html", {"form": form})

    data = form.cleaned_data

    backtest_args: dict[str, object] = {}
    env_overrides: dict[str, str] = {}
    meta: dict[str, object] = {}

    for d in PARAM_DEFS:
        if d.name not in data:
            continue
        v = data.get(d.name)
        if d.field_type == "datetime" and isinstance(v, datetime):
            v = _as_utc_iso(v)

        if d.destination == "backtest":
            backtest_args[d.name] = v
        elif d.destination == "env":
            if d.field_type == "bool":
                env_overrides[d.name] = "True" if v else "False"
            elif v is None or v == "":
                # skip empty optional env vars
                continue
            else:
                env_overrides[d.name] = str(v)
        else:
            meta[d.name] = v

    # Ensure required meta defaults
    env_overrides.setdefault("MODE", "backtest")
    if "MARKET_TYPE" in meta and meta["MARKET_TYPE"]:
        env_overrides.setdefault("MARKET_TYPE", str(meta["MARKET_TYPE"]))
    else:
        env_overrides.setdefault("MARKET_TYPE", "forex")

    params = {"backtest_args": backtest_args, "env_overrides": env_overrides, "meta": meta}

    job_id, paths = create_job(_base_dir(), params=params)
    start_runner_process(_base_dir(), paths)
    return redirect(reverse("job_detail", kwargs={"job_id": job_id}))


@csrf_exempt
def api_run_backtest(request: HttpRequest) -> JsonResponse:
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    if not isinstance(payload, dict):
        return JsonResponse({"error": "JSON body must be an object"}, status=400)

    form = BacktestForm(payload)
    if not form.is_valid():
        return JsonResponse({"error": "Invalid params", "errors": form.errors}, status=400)

    data = form.cleaned_data

    backtest_args: dict[str, object] = {}
    env_overrides: dict[str, str] = {}
    meta: dict[str, object] = {}

    for d in PARAM_DEFS:
        if d.name not in data:
            continue
        v = data.get(d.name)
        if d.field_type == "datetime" and isinstance(v, datetime):
            v = _as_utc_iso(v)

        if d.destination == "backtest":
            backtest_args[d.name] = v
        elif d.destination == "env":
            if d.field_type == "bool":
                env_overrides[d.name] = "True" if v else "False"
            elif v is None or v == "":
                continue
            else:
                env_overrides[d.name] = str(v)
        else:
            meta[d.name] = v

    env_overrides.setdefault("MODE", "backtest")
    if "MARKET_TYPE" in meta and meta["MARKET_TYPE"]:
        env_overrides.setdefault("MARKET_TYPE", str(meta["MARKET_TYPE"]))
    else:
        env_overrides.setdefault("MARKET_TYPE", "forex")

    params = {"backtest_args": backtest_args, "env_overrides": env_overrides, "meta": meta}

    job_id, paths = create_job(_base_dir(), params=params)
    start_runner_process(_base_dir(), paths)

    return JsonResponse(
        {
            "ok": True,
            "job_id": job_id,
            "job_url": reverse("job_detail", kwargs={"job_id": job_id}),
            "status_url": reverse("job_status", kwargs={"job_id": job_id}),
            "result_url": reverse("job_result", kwargs={"job_id": job_id}),
        }
    )


def job_detail(request: HttpRequest, job_id: str) -> HttpResponse:
    return render(request, "backtests/job_detail.html", {"job_id": job_id})


def job_status(request: HttpRequest, job_id: str) -> JsonResponse:
    paths = _paths_for_job(job_id)
    status = read_status(paths)

    pid = status.get("pid")
    if status.get("status") == "running" and pid and not is_pid_running(int(pid)):
        # Runner died without updating status.
        if not paths.result_json.exists():
            write_status(paths, {"status": "failed", "returncode": status.get("returncode"), "error": "Runner process ended"})
        status = read_status(paths)

    payload = {
        "job_id": job_id,
        "status": status.get("status"),
        "created_at": status.get("created_at"),
        "updated_at": status.get("updated_at"),
        "pid": status.get("pid"),
        "python_executable": status.get("python_executable"),
        "returncode": status.get("returncode"),
        "error": status.get("error"),
        "stdout_tail": tail_text_file(paths.stdout_log),
        "stderr_tail": tail_text_file(paths.stderr_log),
        "has_result": paths.result_json.exists(),
        "result_url": reverse("job_result", kwargs={"job_id": job_id}) if paths.result_json.exists() else None,
    }
    return JsonResponse(payload)


def job_result(request: HttpRequest, job_id: str) -> JsonResponse:
    paths = _paths_for_job(job_id)
    if not paths.result_json.exists():
        raise Http404("Result not ready")
    data = json.loads(paths.result_json.read_text(encoding="utf-8"))
    return JsonResponse(data)


@csrf_exempt
def presets_list_or_save(request: HttpRequest) -> JsonResponse:
    base = _base_dir()
    if request.method == "GET":
        presets = load_presets(base)
        return JsonResponse({"presets": sorted(presets.keys())})

    if request.method == "POST":
        try:
            payload = json.loads(request.body.decode("utf-8"))
        except Exception:
            return JsonResponse({"error": "Invalid JSON body"}, status=400)

        name = payload.get("name")
        values = payload.get("values")
        if not isinstance(values, dict):
            return JsonResponse({"error": "`values` must be an object"}, status=400)
        try:
            name = normalize_preset_name(str(name))
        except ValueError as e:
            return JsonResponse({"error": str(e)}, status=400)

        upsert_preset(base, name, values)
        return JsonResponse({"ok": True, "name": name})

    return JsonResponse({"error": "Method not allowed"}, status=405)


@csrf_exempt
def preset_get_or_delete(request: HttpRequest, name: str) -> JsonResponse:
    base = _base_dir()
    try:
        name = normalize_preset_name(name)
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)

    if request.method == "GET":
        presets = load_presets(base)
        if name not in presets:
            return JsonResponse({"error": "Preset not found"}, status=404)
        return JsonResponse({"name": name, "values": presets[name]})

    if request.method == "DELETE":
        delete_preset(base, name)
        return JsonResponse({"ok": True})

    return JsonResponse({"error": "Method not allowed"}, status=405)

