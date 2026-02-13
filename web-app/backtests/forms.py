from __future__ import annotations

from datetime import datetime
from django import forms

from .params import PARAM_DEFS, ParamDef


class BacktestForm(forms.Form):
    """
    Dynamic form driven by `PARAM_DEFS`.

    Add a new parameter by appending to `PARAM_DEFS` in `backtests/params.py`.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for d in PARAM_DEFS:
            self.fields[d.name] = _field_from_def(d)

    def clean_symbols(self) -> list[str]:
        raw = self.cleaned_data["symbols"]
        symbols = [s.strip() for s in raw.split(",") if s.strip()]
        if not symbols:
            raise forms.ValidationError("Provide at least one symbol.")
        return symbols


def _field_from_def(d: ParamDef) -> forms.Field:
    common = {"label": d.label, "help_text": d.help_text}

    if d.field_type == "hidden":
        return forms.CharField(**common, widget=forms.HiddenInput(), required=False)

    if d.field_type == "choice":
        return forms.ChoiceField(**common, required=d.required, choices=d.choices or [])

    if d.field_type == "datetime":
        return forms.DateTimeField(
            **common,
            required=d.required,
            input_formats=["%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f"],
            widget=forms.DateTimeInput(format="%Y-%m-%dT%H:%M", attrs={"type": "datetime-local"}),
        )

    if d.field_type == "bool":
        # Checkbox
        # Always optional in HTML semantics; if required=True, server-side validation should handle it
        return forms.BooleanField(**common, required=False)

    if d.field_type == "int":
        return forms.IntegerField(**common, required=d.required)

    if d.field_type == "float":
        return forms.FloatField(**common, required=d.required)

    # default: string
    return forms.CharField(**common, required=d.required)

