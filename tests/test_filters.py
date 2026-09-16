from __future__ import annotations

import pytest

from notion_db.filters import F, compile_filter, dict_to_filter

SCHEMA = {
    "Status": "status",
    "Priority": "select",
    "Tags": "multi_select",
    "Estimate": "number",
    "Due Date": "date",
}


def test_simple_dict_filter_compiles_to_and_of_equals():
    result = compile_filter({"Status": "Done", "Priority": "High"}, SCHEMA)
    assert result == {
        "and": [
            {"property": "Status", "status": {"equals": "Done"}},
            {"property": "Priority", "select": {"equals": "High"}},
        ]
    }


def test_empty_dict_filter_compiles_to_none():
    assert compile_filter({}, SCHEMA) is None
    assert compile_filter(None, SCHEMA) is None


def test_f_equals_compiles():
    expr = F("Status") == "Done"
    assert expr.to_json(SCHEMA) == {"property": "Status", "status": {"equals": "Done"}}


def test_f_comparison_operators():
    assert (F("Estimate") > 3).to_json(SCHEMA) == {
        "property": "Estimate",
        "number": {"greater_than": 3},
    }
    assert (F("Estimate") <= 3).to_json(SCHEMA) == {
        "property": "Estimate",
        "number": {"less_than_or_equal_to": 3},
    }


def test_f_contains_and_is_empty():
    assert F("Tags").contains("urgent").to_json(SCHEMA) == {
        "property": "Tags",
        "multi_select": {"contains": "urgent"},
    }
    assert F("Tags").is_empty().to_json(SCHEMA) == {
        "property": "Tags",
        "multi_select": {"is_empty": True},
    }


def test_and_or_compound_and_flattening():
    expr = (F("Status") == "Done") & (F("Priority") == "High")
    assert expr.to_json(SCHEMA) == {
        "and": [
            {"property": "Status", "status": {"equals": "Done"}},
            {"property": "Priority", "select": {"equals": "High"}},
        ]
    }

    three_way = expr & (F("Estimate") > 1)
    assert three_way.to_json(SCHEMA) == {
        "and": [
            {"property": "Status", "status": {"equals": "Done"}},
            {"property": "Priority", "select": {"equals": "High"}},
            {"property": "Estimate", "number": {"greater_than": 1}},
        ]
    }

    or_expr = (F("Status") == "Done") | (F("Status") == "Archived")
    assert or_expr.to_json(SCHEMA) == {
        "or": [
            {"property": "Status", "status": {"equals": "Done"}},
            {"property": "Status", "status": {"equals": "Archived"}},
        ]
    }


def test_unknown_property_raises_key_error():
    with pytest.raises(KeyError):
        (F("Nope") == "x").to_json(SCHEMA)


def test_and_with_non_filter_expr_raises_helpful_type_error():
    with pytest.raises(TypeError):
        (F("Status") == "Done") & True


def test_filter_expr_as_bool_raises_helpful_type_error():
    with pytest.raises(TypeError):
        bool(F("Status") == "Done")


def test_dict_to_filter_matches_compile_filter():
    assert dict_to_filter({"Status": "Done"}).to_json(SCHEMA) == compile_filter(
        {"Status": "Done"}, SCHEMA
    )
