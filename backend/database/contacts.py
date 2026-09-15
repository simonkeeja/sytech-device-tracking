"""Canonical account contacts, without guessing a country calling code."""
import re


def normalize_contact(value: str) -> str:
    value = value.strip().casefold()
    if re.fullmatch(r"\+?[0-9\s().-]+", value):
        value = re.sub(r"[\s().-]", "", value)
        if value.startswith("00"):
            value = "+" + value[2:]
    return value
