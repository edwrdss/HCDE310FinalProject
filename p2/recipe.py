# AI-written
"""RecipeAPI (recipeapi.io): the call for Step 2 of the flow, plus checks.

Docs:  https://recipeapi.io/docs/   (recipes: https://recipeapi.io/docs/resources/recipes/)
Call:  GET https://recipeapi.io/api/v1/recipes?search=<keyword>&per_page=4
Key:   needs a free API key (sk_live_...) from https://recipeapi.io/register.
       Send it as  Authorization: Bearer <key>.  This file reads it from the
       RECIPEAPI_KEY environment variable so the key never lives in your code.

    pip install requests
    export RECIPEAPI_KEY="sk_live_..."
    python recipe.py                  # runs the checks (mocked: no network, no key needed)
    python recipe.py stew chili       # live: search these keywords, print the recipes
    python recipe.py --raw stew       # live: print one trimmed raw response to paste in your write-up
"""
from __future__ import annotations

import json
import os
import sys
import time
from unittest.mock import MagicMock, patch

import requests

RECIPEAPI_URL = "https://recipeapi.io/api/v1/recipes"
DEFAULT_KEYWORD = "soup"
RECIPE_COUNT = 4


class RecipeAPIError(Exception):
    """A problem the user/developer must fix (missing/invalid key, monthly limit hit).
    Not the same as 'no results', which just moves on to the next keyword."""


# ---------------------------------------------------------------------------
# The call
# ---------------------------------------------------------------------------
def _error_code(resp) -> str | None:
    try:
        return resp.json().get("error", {}).get("code")
    except (ValueError, AttributeError):
        return None


def _request(keyword: str, per_page: int):
    """One GET to /recipes. Retries once if we hit the 10-requests-per-second limit."""
    key = os.environ.get("RECIPEAPI_KEY")
    if not key:
        raise RecipeAPIError("RECIPEAPI_KEY is not set. Get a free key at https://recipeapi.io/register")
    for attempt in range(2):
        resp = requests.get(
            RECIPEAPI_URL,
            params={"search": keyword, "per_page": per_page},   # search matches recipe names
            headers={"Authorization": f"Bearer {key}"},
            timeout=10,
        )
        if resp.status_code == 429 and _error_code(resp) == "RATE_LIMIT" and attempt == 0:
            time.sleep(1.1)
            continue
        return resp
    return resp


def _fmt_qty(q) -> str:
    if q is None:
        return ""
    if isinstance(q, float) and q.is_integer():
        q = int(q)
    return str(q)


def _normalize(recipe: dict) -> dict:
    """Keep what the UI needs. Ingredients become display strings like '2 clove Garlic'."""
    ingredients = []
    for ing in recipe.get("ingredients") or []:
        if not isinstance(ing, dict) or not ing.get("name"):
            continue
        text = " ".join(p for p in [_fmt_qty(ing.get("quantity")), ing.get("unit") or "", ing["name"]] if p)
        if ing.get("optional"):
            text += " (optional)"
        ingredients.append(text)
    return {
        "id": recipe["id"],
        "title": recipe["name"],
        "description": recipe.get("description"),
        "cuisine": recipe.get("cuisine"),
        "meal_type": recipe.get("meal_type"),
        "difficulty": recipe.get("difficulty"),
        "dietary_tags": recipe.get("dietary_tags") or [],
        "servings": recipe.get("servings"),
        "prep_time": recipe.get("prep_time"),
        "cook_time": recipe.get("cook_time"),
        "calories_per_serving": recipe.get("calories_per_serving"),
        "protein": recipe.get("protein"),
        "instructions": recipe.get("instructions") or [],   # a list of steps, not one string
        "ingredients": ingredients,
    }


def search_recipes(keyword: str, per_page: int = RECIPE_COUNT) -> list[dict]:
    """Search RecipeAPI by recipe name. Returns [] for no results or a network
    problem, so the caller can simply move on to the next keyword.
    Raises RecipeAPIError for a missing/invalid key or when the monthly limit is used up."""
    try:
        resp = _request(keyword, per_page)
    except requests.RequestException:
        return []
    if resp.status_code == 401:
        raise RecipeAPIError("RecipeAPI rejected the key (401 UNAUTHENTICATED). Check RECIPEAPI_KEY.")
    if resp.status_code == 429 and _error_code(resp) == "USAGE_LIMIT_EXCEEDED":
        raise RecipeAPIError("RecipeAPI monthly request limit used up (Free plan = 500/month).")
    if resp.status_code != 200:
        return []
    try:
        data = resp.json().get("data")
    except (ValueError, AttributeError):
        return []
    if not isinstance(data, list):
        return []
    return [_normalize(r) for r in data if isinstance(r, dict) and r.get("id") is not None and r.get("name")]


def find_recipes(keywords: list[str], count: int = RECIPE_COUNT,
                 default_keyword: str = DEFAULT_KEYWORD) -> dict:
    """Get `count` recipes using the keywords in order, with fallbacks.

    1. Try each keyword in order. A keyword with no results is skipped.
    2. Keep collecting (no duplicates) until we have `count` recipes.
    3. If we still have fewer than `count` (including zero), fall back to
       the default keyword ("soup") to fill the rest.

    Each keyword costs one API request (Free plan: 500/month), so this stops
    as soon as it has enough. Returns {"recipes", "keywords_tried",
    "keywords_used", "used_fallback"}.
    """
    recipes, seen_ids = [], set()
    tried, used = [], []

    def collect(keyword):
        tried.append(keyword)
        added = False
        for r in search_recipes(keyword, per_page=count):
            if r["id"] not in seen_ids and len(recipes) < count:
                seen_ids.add(r["id"])
                recipes.append(r)
                added = True
        if added:
            used.append(keyword)

    for kw in keywords:
        if len(recipes) >= count:
            break
        if kw and kw.strip() and kw.strip().lower() not in tried:
            collect(kw.strip().lower())

    used_fallback = False
    if len(recipes) < count and default_keyword not in tried:
        used_fallback = True
        collect(default_keyword)

    return {
        "recipes": recipes,
        "keywords_tried": tried,
        "keywords_used": used,
        "used_fallback": used_fallback,
    }


# ---------------------------------------------------------------------------
# Checks (RecipeAPI is mocked, so they run anywhere with no key)
# ---------------------------------------------------------------------------
def _recipe(n, name):
    return {"id": n, "name": name, "description": "A test recipe.", "difficulty": "easy",
            "meal_type": "soup", "cuisine": "american", "dietary_tags": [], "servings": 4,
            "prep_time": 10, "cook_time": 20, "calories_per_serving": 300, "protein": 10,
            "instructions": ["Cook it."],
            "ingredients": [{"id": 1, "name": "Water", "category": "other", "quantity": 1,
                             "unit": "cup", "optional": False}]}


def _response(status=200, body=None):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = body if body is not None else {}
    return resp


def _list_body(recipes):
    return {"data": recipes, "links": {}, "meta": {"total": len(recipes), "language": "en"}}


def _fake_api(results_by_keyword):
    """requests.get replacement: search keyword -> list of recipes (missing = empty list)."""
    def fake_get(url, params=None, headers=None, timeout=None):
        return _response(200, _list_body(results_by_keyword.get(params["search"], [])))
    return fake_get


def _report(ok, text):
    print(f"{'PASS' if ok else 'FAIL'} {text}")
    return ok


KEY = {"RECIPEAPI_KEY": "sk_live_test"}


def check_four_recipes():
    """Weather keywords -> at least four recipes returned."""
    api = {"stew": [_recipe(i, f"Stew {i}") for i in range(1, 5)]}
    with patch.dict(os.environ, KEY), patch("requests.get", side_effect=_fake_api(api)):
        out = find_recipes(["stew", "chowder", "chili"])
    ok = len(out["recipes"]) >= 4 and not out["used_fallback"] and out["keywords_tried"] == ["stew"]
    return _report(ok, f"gets at least 4 recipes: {len(out['recipes'])} from {out['keywords_used']} "
                       f"(1 request)")


def check_fills_from_several_keywords():
    """One keyword has fewer than 4 results -> keeps going to reach 4."""
    api = {"chili": [_recipe(1, "Chili")],
           "stew": [_recipe(i, f"Stew {i}") for i in range(2, 6)]}
    with patch.dict(os.environ, KEY), patch("requests.get", side_effect=_fake_api(api)):
        out = find_recipes(["chili", "stew"])
    ok = len(out["recipes"]) == 4 and out["keywords_used"] == ["chili", "stew"]
    return _report(ok, f"combines keywords to reach 4: used {out['keywords_used']}")


def check_next_keyword():
    """First keyword returns nothing -> tries the next one."""
    api = {"chowder": [], "stew": [_recipe(i, f"Stew {i}") for i in range(1, 5)]}
    with patch.dict(os.environ, KEY), patch("requests.get", side_effect=_fake_api(api)):
        out = find_recipes(["chowder", "stew"])
    ok = (out["keywords_tried"][:2] == ["chowder", "stew"]
          and len(out["recipes"]) == 4 and not out["used_fallback"])
    return _report(ok, f"skips empty first keyword: tried {out['keywords_tried']}, got {len(out['recipes'])}")


def check_default_fallback():
    """Every keyword fails -> falls back to 'soup'."""
    api = {"soup": [_recipe(i, f"Soup {i}") for i in range(1, 5)]}   # all else -> empty
    with patch.dict(os.environ, KEY), patch("requests.get", side_effect=_fake_api(api)):
        out = find_recipes(["chowder", "stew", "chili"])
    ok = out["used_fallback"] and out["keywords_tried"][-1] == "soup" and len(out["recipes"]) == 4
    return _report(ok, f"falls back to default 'soup': tried {out['keywords_tried']}, got {len(out['recipes'])}")


def check_api_error_falls_back():
    """A network error or 500 on a keyword still ends in the fallback, no crash."""
    def flaky(url, params=None, headers=None, timeout=None):
        if params["search"] == "soup":
            return _response(200, _list_body([_recipe(i, f"Soup {i}") for i in range(1, 5)]))
        if params["search"] == "stew":
            return _response(500, {})
        raise requests.ConnectionError("down")
    with patch.dict(os.environ, KEY), patch("requests.get", side_effect=flaky):
        out = find_recipes(["chili", "stew"])
    ok = out["used_fallback"] and len(out["recipes"]) == 4
    return _report(ok, f"survives network error and 500: got {len(out['recipes'])} recipes")


def check_rate_limit_retry():
    """A 429 RATE_LIMIT (10 requests/second) is retried once and then succeeds."""
    calls = []
    def limited(url, params=None, headers=None, timeout=None):
        calls.append(1)
        if len(calls) == 1:
            return _response(429, {"error": {"code": "RATE_LIMIT", "message": "Too many requests."}})
        return _response(200, _list_body([_recipe(i, f"Stew {i}") for i in range(1, 5)]))
    with patch.dict(os.environ, KEY), patch("requests.get", side_effect=limited), patch("time.sleep"):
        out = find_recipes(["stew"])
    ok = len(calls) == 2 and len(out["recipes"]) == 4
    return _report(ok, f"retries once after RATE_LIMIT: {len(calls)} calls, {len(out['recipes'])} recipes")


def check_key_problems_raise():
    """Missing key, bad key and used-up monthly limit raise a clear error (not silent 'no results')."""
    results = []
    with patch.dict(os.environ, {}, clear=True):
        try:
            find_recipes(["stew"]); results.append(False)
        except RecipeAPIError:
            results.append(True)
    bad = {"401": _response(401, {"error": {"code": "UNAUTHENTICATED", "message": "x"}}),
           "429": _response(429, {"error": {"code": "USAGE_LIMIT_EXCEEDED", "message": "x"}})}
    for resp in bad.values():
        with patch.dict(os.environ, KEY), patch("requests.get", return_value=resp):
            try:
                find_recipes(["stew"]); results.append(False)
            except RecipeAPIError:
                results.append(True)
    return _report(all(results), "missing key, 401 and monthly limit each raise RecipeAPIError")


def check_request_shape():
    """Sends the key as a Bearer header and searches by name with per_page=4."""
    with patch.dict(os.environ, KEY), patch("requests.get", return_value=_response(200, _list_body([]))) as g:
        search_recipes("stew")
    args, kwargs = g.call_args
    ok = (args[0] == RECIPEAPI_URL and kwargs["params"] == {"search": "stew", "per_page": 4}
          and kwargs["headers"] == {"Authorization": "Bearer sk_live_test"})
    return _report(ok, "request uses Bearer header, search=<keyword>, per_page=4")


def check_docs_response_shape():
    """A recipe shaped like the docs example normalizes correctly (steps stay a list,
    ingredient strings built from quantity + unit + name)."""
    docs_example = {"id": 449, "name": "Beef Tostadas", "difficulty": "easy", "meal_type": "main",
                    "cuisine": "american", "dietary_tags": ["nut_free"], "servings": 6,
                    "prep_time": 15, "cook_time": 15, "calories_per_serving": 450, "protein": 25,
                    "instructions": ["Heat the vegetable oil in a frying pan over medium heat until hot.",
                                     "Add the beef and cook, stirring occasionally."],
                    "ingredients": [
                        {"id": 58, "name": "Chili powder", "category": "spice", "quantity": 1, "unit": "tsp", "optional": False},
                        {"id": 37, "name": "Garlic", "category": "vegetable", "quantity": 2.0, "unit": "clove", "optional": False},
                        {"id": 8, "name": "Cheddar cheese", "category": "dairy", "quantity": 100, "unit": "g", "optional": True}]}
    r = _normalize(docs_example)
    ok = (r["title"] == "Beef Tostadas" and len(r["instructions"]) == 2
          and r["ingredients"] == ["1 tsp Chili powder", "2 clove Garlic", "100 g Cheddar cheese (optional)"])
    return _report(ok, "docs-shaped recipe normalizes (steps list, ingredient strings)")


def run_checks() -> bool:
    results = [check_four_recipes(), check_fills_from_several_keywords(), check_next_keyword(),
               check_default_fallback(), check_api_error_falls_back(), check_rate_limit_retry(),
               check_key_problems_raise(), check_request_shape(), check_docs_response_shape()]
    print("\nALL CHECKS PASSED" if all(results) else "\nSOME CHECKS FAILED")
    return all(results)


def print_raw(keyword: str):
    """Live: print one trimmed real response so you can paste it into your write-up."""
    body = _request(keyword, 1).json()
    if isinstance(body.get("data"), list) and body["data"]:
        r = body["data"][0]
        r["instructions"] = r.get("instructions", [])[:2] + ["..."]
        r["ingredients"] = r.get("ingredients", [])[:3] + ["..."]
    print(json.dumps(body, indent=2))


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        sys.exit(0 if run_checks() else 1)
    try:
        if args[0] == "--raw":                  # python recipe.py --raw stew
            print_raw(args[1] if len(args) > 1 else "stew")
        else:                                   # python recipe.py stew chili
            out = find_recipes(args)
            print(f"tried {out['keywords_tried']}, used {out['keywords_used']}, fallback: {out['used_fallback']}")
            for r in out["recipes"]:
                print("-", r["title"], f"({r['cuisine']}, {r['meal_type']}, {r['calories_per_serving']} cal)")
    except RecipeAPIError as e:
        sys.exit(f"Error: {e}")