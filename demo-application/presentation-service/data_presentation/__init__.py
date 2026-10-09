"""Data presentation layer: the masked result shown in the formats the intent classifier recommended."""

from .views import LABELS, PRESENTATION_TYPES, build_views, choose_from_data

__all__ = ["LABELS", "PRESENTATION_TYPES", "build_views", "choose_from_data"]
