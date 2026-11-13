#!/usr/bin/env python3
"""Analyze one Threads account from a known post URL.
Usage: analyze_account.py <post_url> <out_json>
Calls threads-cli: post --url -> author_id, user-profile, profile-threads(50), profile-replies(10)
Summarizes: profile, post frequency (last 7/14 days), top posts, oldest in sample, replies activity.
Raw outputs saved alongside as <out>_threads.json / <out>_replies.json / <out>_profile.json
"""
import json, subprocess, sys, time
from collections import Counter
from datetime import datetime, timedelta

ACC = "17841476258195856"
CLI = "/opt/hatch/bin/threads-cli"

def run(args):
    r = subprocess.run([CLI]+args, capture_output=True, text=True, timeout=120)
    out = r.stdout.strip()
    if not out.startswith("{"):
        raise RuntimeError(f"CLI failed {args[0]}: {out[:300]} {r.stderr[:200]}")
    return json.loads(out)

def main():
    post_url, out_path = sys.argv[1], sys.argv[2]
    post = run(["post", "--account-id", ACC, "--url", post_url])
    p0 = post["posts"][0]
    uid = p0["author_id"]; username = p0["username"]
    time.sleep(1)
    prof = run(["user-profile", "--account-id", ACC, "--user-id", uid])
    pr = (prof.get("profiles") or [{}])[0]
    time.sleep(1)
    threads = run(["profile-threads", "--account-id", ACC, "--user-id", uid, "--first", "50"])
    posts = threads.get("posts", [])
    time.sleep(1)
    try:
        replies = run(["profile-replies", "--account-id", ACC, "--user-id", uid, "--first", "10"])
        rep_posts = replies.get("posts", [])
    except Exception as e:
        rep_posts = []; rep_err = str(e)[:200]
    else:
        rep_err = None

    def parse_dt(s):
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
            try: return datetime.strptime(s[:19], fmt)
            except Exception: pass
        return None

    rows = []
    for p in posts:
        dt = parse_dt(p.get("post_creation_time") or "")
        cap = (p.get("post_caption_text") or "").strip()
        rows.append({
            "date": p.get("post_creation_time"),
            "dt": dt.isoformat() if dt else None,
            "likes": p.get("like_count") or 0,
            "first_line": cap.split("\n")[0][:80],
            "caption_head": cap[:160],
            "media_type": p.get("media_type"),
            "has_media": (p.get("media_type") not in (None, "TEXT_ONLY")),
            "url": p.get("media_permalink") or p.get("url"),
        })
    rows_sorted = sorted([r for r in rows if r["dt"]], key=lambda r: r["dt"], reverse=True)
    now = datetime(2026, 11, 2, 23, 59)
    last7 = [r for r in rows_sorted if parse_dt(r["date"]) and parse_dt(r["date"]) >= now - timedelta(days=7)]
    last1 = [r for r in rows_sorted if parse_dt(r["date"]) and parse_dt(r["date"]) >= now - timedelta(days=1)]
    per_day = Counter(r["date"][:10] for r in rows_sorted if r["date"])
    top3 = sorted(rows, key=lambda r: r["likes"], reverse=True)[:3]
    # likes trend: newest 10 vs older 10 in sample
    def avg(xs): return round(sum(x["likes"] for x in xs)/len(xs),1) if xs else None
    summary = {
        "username": username,
        "user_id": uid,
        "profile_url": f"https://www.threads.com/@{username}",
        "name": pr.get("name"),
        "bio": pr.get("bio"),
        "follower_count_profile": pr.get("follower_count"),
        "follower_count_post": p0.get("follower_count"),
        "following_count": pr.get("following_count"),
        "post_count_total": pr.get("post_count"),
        "sample_size": len(rows),
        "sample_newest": rows_sorted[0]["date"] if rows_sorted else None,
        "sample_oldest": rows_sorted[-1]["date"] if rows_sorted else None,
        "posts_last_24h": len(last1),
        "posts_last_7d_in_sample": len(last7),
        "per_day_recent": dict(list(per_day.items())[:10]),
        "avg_likes_newest10": avg(rows_sorted[:10]),
        "avg_likes_oldest10_in_sample": avg(rows_sorted[-10:]),
        "max_likes_in_sample": max([r["likes"] for r in rows], default=None),
        "posts_over_100_likes_in_sample": sum(1 for r in rows if r["likes"] >= 100),
        "top3": top3,
        "first_returned_post": rows[0] if rows else None,  # pinned often returned first / out of order
        "replies_sample_size": len(rep_posts),
        "replies_sample": [
            {"date": rp.get("post_creation_time"), "to": (rp.get("author_info") or {}).get("username"),
             "text_head": (rp.get("post_caption_text") or "")[:100]} for rp in rep_posts[:5]
        ],
        "replies_error": rep_err,
        "has_next_page_threads": threads.get("page_info", {}).get("has_next_page"),
        "next_cursor": threads.get("page_info", {}).get("end_cursor"),
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)
    with open(out_path.replace(".json", "_threads_raw.json"), "w", encoding="utf-8") as f:
        json.dump(threads, f, ensure_ascii=False)
    print(json.dumps({k: summary[k] for k in ("username","name","follower_count_profile","post_count_total","sample_newest","sample_oldest","posts_last_24h","posts_last_7d_in_sample","avg_likes_newest10","avg_likes_oldest10_in_sample","max_likes_in_sample","posts_over_100_likes_in_sample","replies_sample_size")}, ensure_ascii=False))

if __name__ == "__main__":
    main()
