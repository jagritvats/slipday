"""Upcoming missions, who this helps, and open data (add-on router; see ADDON_impact.md).

Serves the stored board (data/addons/impact/missions.json, built by ``python -m slipday.addons.impact_build``).
It computes nothing at request time, and nothing else in the app depends on it.

    GET /api/addons/impact                     the board: missions with results, missions left out, rule, sources
    GET /api/addons/impact/mission/{id}        one mission in full
    GET /api/addons/impact/who                 who this helps, each line with the place on the page that backs it
    GET /api/addons/impact/open-data           the endpoints and downloads others can build on
    GET /api/addons/impact/missions.json       the board as a file
    GET /api/addons/impact/missions.csv        one row per mission and month: site, landing, verdict, margin, week, month
"""
from __future__ import annotations

import csv
import io
import json
import os
from functools import lru_cache

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
JSON_PATH = os.path.join(ROOT, "data", "addons", "impact", "missions.json")

router = APIRouter(prefix="/api/addons/impact", tags=["add-on: upcoming missions"])

LPSC_QUOTE = ("individual regions typically provide limited viable opportunities when all constraints are "
              "simultaneously satisfied", "more than one landing regions must be maintained")

# Each line names who is helped, how, and the place on the page that backs it ("where" is an anchor id on the page).
WHO = [
    {"who": "Mission planners deciding whether to wait or move",
     "how": "When a launch slips, the card says how many days the landing can slip and the next good dates. The board "
            "above shows, for real upcoming missions, how often a week's or a month's slip still works at the "
            "published place, and which other regions are open when it does not.",
     "evidence": "IM-1, February 2024: the card reads Yes with one day to spare, both in the January window it missed "
                 "and in the February window it flew (Real missions panel).",
     "where": [("addon-missions", "Upcoming missions"), ("h-mission", "the card"), ("real", "Real missions")]},
    {"who": "NASA, keeping several Artemis regions open",
     "how": "NASA writes that \"" + LPSC_QUOTE[0] + "\" and that \"" + LPSC_QUOTE[1] + "\" (LPSC 2026 abstract, NTRS "
            "20250011660). The region calendar measures this on the 78 published candidate sites: on the 80 m grid the "
            "best single region is open at 28 % of landing times, all nine at 44 %.",
     "evidence": "Region calendar, 2027 to 2030, and the Artemis IV row of the board.",
     "where": [("regions", "How many regions must stay open"), ("addon-missions", "Artemis IV")]},
    {"who": "Teachers and students (age 12 and up)",
     "how": "A short game: the launch slips, you pick a site, and the app gives the real answer with one plain reason. "
            "\"Not like Earth\" puts the Sun at the site beside the Sun at home.",
     "evidence": "Be the mission planner; Not like Earth.",
     "where": [("foldGame", "Be the mission planner"), ("foldContrast", "Not like Earth")]},
    {"who": "People who use screen readers",
     "how": "The 14-day landing window can be heard as sound (a high tone for the Sun, a low tone for the Earth) or "
            "read as text, and the card's answer is read out. Nobody has tested it with a real screen reader yet.",
     "evidence": "Listen to the landing window.",
     "where": [("foldListen", "Listen to the landing window")]},
    {"who": "Anyone building their own tool",
     "how": "Every answer on the page comes from an open API and can be downloaded as CSV or JSON. The code is "
            "Apache-2.0; the terrain is NASA's LOLA data.",
     "evidence": "Use the data, below.",
     "where": [("addon-missions-data", "Use the data")]},
]

OPEN_DATA = {
    "note": "All endpoints answer JSON on the running app. No key, no account. Figures are terrain-model results on "
            "NASA LOLA elevation grids, tagged with the grid used; read LIMITATIONS.md before relying on them.",
    "endpoints": [
        {"method": "POST", "path": "/api/mission", "what": "the card: verdict, slip margin in days and a verdict for every day of slip, for any site and date"},
        {"method": "POST", "path": "/api/windows", "what": "the planned landing and the next monthly windows, judged the same way"},
        {"method": "GET", "path": "/api/region-availability", "what": "NASA's nine regions on 78 published candidate sites, 2027 to 2030, every 6 hours"},
        {"method": "GET", "path": "/api/addons/atlas", "what": "which years suit a landing, 2027 to 2035"},
        {"method": "GET", "path": "/api/real-windows", "what": "IM-1 and VIPER windows with sources"},
        {"method": "GET", "path": "/api/addons/impact", "what": "this board: upcoming missions, a week's and a month's slip"},
        {"method": "GET", "path": "/api/sites", "what": "the curated sites with their sources"},
        {"method": "GET", "path": "/api/horizon", "what": "the 360-degree terrain skyline at a point"},
    ],
    "downloads": [
        {"path": "/api/addons/impact/missions.csv", "what": "this board, one row per mission and month"},
        {"path": "/api/addons/impact/missions.json", "what": "this board in full, with rule and sources"},
        {"method": "POST", "path": "/api/export/slipgrid.csv", "what": "the slip grid (sites by landing dates)"},
        {"method": "POST", "path": "/api/export/series.csv", "what": "Sun and Earth over time at a site"},
        {"path": "the card's \"Download this answer\" button", "what": "inputs, verdict, margin, every day of slip, windows and other sites (CSV or JSON)"},
    ],
    "docs": "/docs (the API's own page, made by FastAPI)",
    "licence": "Code Apache-2.0. NASA data carries no copyright. Wueller et al. 2026 sites CC BY 4.0.",
}


@lru_cache(maxsize=1)
def _load_cached(mtime: float) -> dict:
    with open(JSON_PATH, encoding="utf-8") as f:
        return json.load(f)


def load() -> dict | None:
    if not os.path.exists(JSON_PATH):
        return None
    return _load_cached(os.path.getmtime(JSON_PATH))


def _missing() -> dict:
    return {"available": False,
            "reason": "the board has not been built on this installation (python -m slipday.addons.impact_build)"}


def who() -> list:
    return [{**w, "where": [{"id": i, "label": lab} for i, lab in w["where"]]} for w in WHO]


@router.get("")
def impact_board():
    d = load()
    if d is None:
        return {**_missing(), "who": who(), "open_data": OPEN_DATA}
    return {"available": True, **d, "who": who(), "open_data": OPEN_DATA}


@router.get("/mission/{mission_id}")
def impact_mission(mission_id: str):
    d = load()
    if d is None:
        return _missing()
    for m in d["missions"]:
        if m["id"] == mission_id:
            return {"available": True, **m}
    raise HTTPException(404, "missions on the board: " + ", ".join(m["id"] for m in d["missions"]))


@router.get("/who")
def impact_who():
    return {"who": who()}


@router.get("/open-data")
def impact_open_data():
    return OPEN_DATA


@router.get("/missions.json")
def impact_json():
    if not os.path.exists(JSON_PATH):
        raise HTTPException(404, _missing()["reason"])
    return FileResponse(JSON_PATH, media_type="application/json", filename="slipday_upcoming_missions.json")


CSV_COLS = ["mission", "launch_published", "place_published", "month", "site", "region", "lat", "lon", "landing_utc",
            "verdict", "slip_margin_days", "week_later_utc", "week_later_verdict", "month_later_utc",
            "month_later_verdict", "label"]


def csv_text(d: dict) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(CSV_COLS)
    for m in d["missions"]:
        for r in m["months"]:
            w.writerow([m["name"], m["launch_text"], m["place_text"], r["month"], r["site"], r["region"], r["lat"], r["lon"],
                        r["landing_utc"], r["verdict"], r["slip_margin_days"], r["week_later"]["landing_utc"],
                        r["week_later"]["verdict"], r["month_later"]["landing_utc"], r["month_later"]["verdict"],
                        "approximate: published place and period, published candidate site, landing time spread over the period"])
    return buf.getvalue()


@router.get("/missions.csv")
def impact_csv():
    d = load()
    if d is None:
        raise HTTPException(404, _missing()["reason"])
    return Response(csv_text(d), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=slipday_upcoming_missions.csv"})
