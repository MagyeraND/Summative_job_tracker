import os
import sqlite3
from datetime import datetime
from urllib.parse import urlencode

import requests
from flask import Flask, g, redirect, render_template, request, url_for


app = Flask(__name__)


@app.after_request
def add_served_by_header(response):
    served_by = os.environ.get("SERVER_NAME") or os.environ.get("HOSTNAME")
    if served_by:
        response.headers["X-Served-By"] = served_by
    return response


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect("saved_jobs.db")
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect("saved_jobs.db")
    try:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS saved_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                company TEXT,
                location TEXT,
                url TEXT,
                created_utc TEXT NOT NULL
            )
            """
        )
        db.commit()
    finally:
        db.close()


init_db()


def env_config_error():
    missing = []
    if not os.environ.get("ADZUNA_APP_ID"):
        missing.append("ADZUNA_APP_ID")
    if not os.environ.get("ADZUNA_APP_KEY"):
        missing.append("ADZUNA_APP_KEY")

    if not missing:
        return None

    return "Missing environment variables: " + ", ".join(missing)


def fetch_countries():
    url = "https://restcountries.com/v3.1/all"
    params = {"fields": "name,cca2"}
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        countries = []
        for item in data:
            cca2 = (item.get("cca2") or "").strip()
            name = ((item.get("name") or {}).get("common") or "").strip()
            if not cca2 or not name:
                continue
            countries.append({"code": cca2.lower(), "name": name})
        countries.sort(key=lambda c: c["name"].lower())
        return countries, None
    except requests.RequestException as e:
        return [], f"Could not load country list: {e}"


def adzuna_search(*, what, where, country, page, results_per_page, sort_by, salary_min, full_time, contract_type):
    app_id = os.environ.get("ADZUNA_APP_ID")
    app_key = os.environ.get("ADZUNA_APP_KEY")

    if not app_id or not app_key:
        return None, env_config_error()

    base_url = f"https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"
    params = {
        "app_id": app_id,
        "app_key": app_key,
        "results_per_page": results_per_page,
        "what": what or None,
        "where": where or None,
        "sort_by": sort_by or None,
        "salary_min": salary_min or None,
        "full_time": 1 if full_time else None,
        "contract_type": contract_type or None,
        "content-type": "application/json",
    }

    params = {k: v for k, v in params.items() if v is not None and v != ""}

    try:
        resp = requests.get(base_url, params=params, timeout=12)
        if resp.status_code == 401 or resp.status_code == 403:
            return None, "Adzuna rejected the API credentials. Check ADZUNA_APP_ID / ADZUNA_APP_KEY."
        resp.raise_for_status()
        return resp.json(), None
    except requests.Timeout:
        return None, "The job API timed out. Try again in a moment."
    except requests.RequestException as e:
        return None, f"Could not reach the job API: {e}"


def normalize_job(job):
    salary_min = job.get("salary_min")
    salary_max = job.get("salary_max")

    def fmt_salary(v):
        if v is None:
            return None
        try:
            return int(round(float(v)))
        except (TypeError, ValueError):
            return None

    created = job.get("created")
    created_dt = None
    if created:
        try:
            created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
        except ValueError:
            created_dt = None

    company = (job.get("company") or {}).get("display_name")
    location = (job.get("location") or {}).get("display_name")

    return {
        "job_id": job.get("id"),
        "title": job.get("title"),
        "company": company,
        "location": location,
        "created": created_dt,
        "created_raw": created,
        "salary_min": fmt_salary(salary_min),
        "salary_max": fmt_salary(salary_max),
        "url": job.get("redirect_url") or job.get("adref"),
        "contract_type": job.get("contract_type"),
        "contract_time": job.get("contract_time"),
        "category": (job.get("category") or {}).get("label"),
    }


def get_saved_job_ids():
    db = get_db()
    rows = db.execute("SELECT job_id FROM saved_jobs").fetchall()
    return {r["job_id"] for r in rows}


@app.get("/health")
def health():
    return {"status": "ok"}, 200


@app.get("/")
def index():
    countries, countries_error = fetch_countries()

    form = {
        "what": request.args.get("what", ""),
        "where": request.args.get("where", ""),
        "country": request.args.get("country", "gb"),
        "sort_by": request.args.get("sort_by", "date"),
        "salary_min": request.args.get("salary_min", ""),
        "full_time": request.args.get("full_time") == "1",
        "contract_type": request.args.get("contract_type", ""),
        "page": request.args.get("page", "1"),
    }

    try:
        page = max(1, int(form["page"]))
    except ValueError:
        page = 1

    results = []
    meta = None
    api_error = None

    if any([form["what"], form["where"]]):
        data, api_error = adzuna_search(
            what=form["what"],
            where=form["where"],
            country=form["country"],
            page=page,
            results_per_page=20,
            sort_by=form["sort_by"],
            salary_min=form["salary_min"],
            full_time=form["full_time"],
            contract_type=form["contract_type"],
        )
        if data:
            meta = {
                "count": data.get("count"),
                "mean": data.get("mean"),
            }
            results = [normalize_job(j) for j in (data.get("results") or [])]

    saved_ids = get_saved_job_ids()

    def build_page_url(new_page):
        q = dict(request.args)
        q["page"] = str(new_page)
        return url_for("index") + "?" + urlencode(q)

    prev_url = build_page_url(page - 1) if page > 1 else None
    next_url = build_page_url(page + 1) if results else None

    return render_template(
        "index.html",
        countries=countries,
        countries_error=countries_error,
        form=form,
        results=results,
        meta=meta,
        api_error=api_error,
        saved_ids=saved_ids,
        prev_url=prev_url,
        next_url=next_url,
    )


@app.post("/save")
def save_job():
    job_id = request.form.get("job_id")
    title = request.form.get("title")
    company = request.form.get("company")
    location = request.form.get("location")
    url = request.form.get("url")

    if not job_id or not title:
        return redirect(url_for("index"))

    db = get_db()
    try:
        db.execute(
            """
            INSERT OR IGNORE INTO saved_jobs (job_id, title, company, location, url, created_utc)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (job_id, title, company, location, url, datetime.utcnow().isoformat()),
        )
        db.commit()
    except sqlite3.DatabaseError:
        pass

    next_url = request.form.get("next")
    return redirect(next_url or url_for("index"))


@app.post("/unsave")
def unsave_job():
    job_id = request.form.get("job_id")
    if not job_id:
        return redirect(url_for("saved"))

    db = get_db()
    try:
        db.execute("DELETE FROM saved_jobs WHERE job_id = ?", (job_id,))
        db.commit()
    except sqlite3.DatabaseError:
        pass

    next_url = request.form.get("next")
    return redirect(next_url or url_for("saved"))


@app.get("/saved")
def saved():
    db = get_db()
    rows = db.execute(
        "SELECT job_id, title, company, location, url, created_utc FROM saved_jobs ORDER BY created_utc DESC"
    ).fetchall()
    return render_template("saved.html", saved_jobs=rows)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=True)
