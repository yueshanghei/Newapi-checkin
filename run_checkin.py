#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
本地启动器：先自动登录换凭证，再交给上游 checkin 逻辑签到

为什么需要这一层:
    上游 checkin.py 只认「session cookie」或「系统访问令牌(access_token)」，
    不会用账号密码自己换 JWT。而我们手上的站点分三类：
      1. 旧版 new-api：账号密码登录 -> session cookie
      2. 新版 new-api（JWT）：账号密码登录 -> access_token（15 分钟有效，不适合写进配置）
      3. 开启 Turnstile 的站点：登录要先过人机验证
    这里统一处理：能免验证就直接登录，需要 Turnstile 就让真实浏览器解一个 token 再登录，
    拿到 session/access_token 后交给 NewAPICheckin（上游继续负责 PoW / Turnstile 签到 / CF 绕过）。

配置:
    .env 里的 NEWAPI_ACCOUNTS，JSON 数组，每项：
      {"url": "...", "name": "...", "session": "",
       "login_username": "...", "login_password": "..."}
    session / access_token 留空即可，本脚本会自动登录补齐。

用法:
    python run_checkin.py                 # 全部站点
    python run_checkin.py --only hkkkj    # 只跑名字/域名包含 hkkkj 的站点
    python run_checkin.py --verbose
"""
from __future__ import annotations

import os
import sys
import time

import turnstile_login
from checkin import NewAPICheckin, load_env_file, parse_accounts


def resolve_credentials(account: dict, verbose: bool = True) -> dict:
    """补全 session / access_token / user_id；返回新的 account 字典"""
    account = dict(account)
    url = account["url"].rstrip("/")
    name = account.get("name") or url

    has_session = bool(account.get("session"))
    has_token = bool(account.get("access_token"))
    username = account.get("login_username")
    password = account.get("login_password")

    if (has_session or has_token) and account.get("user_id"):
        print(f"  [auth] 使用配置里的 {'access_token' if has_token else 'session'}")
        return account

    if not (username and password):
        print("  [auth] 未配置 session/access_token，也没有账号密码，跳过自动登录")
        return account

    print(f"  [auth] 用账号密码登录 {url} ...")
    result = turnstile_login.login(url, username, password, verbose=verbose)
    if not result:
        print("  [auth] 自动登录失败")
        return account

    if result.get("access_token"):
        account["access_token"] = "Bearer " + result["access_token"]
    if result.get("session"):
        account["session"] = result["session"]
    if result.get("user_id"):
        account["user_id"] = str(result["user_id"])
    return account


def run_one(account: dict, verbose: bool = False) -> dict:
    url = account["url"].rstrip("/")
    name = account.get("name") or url
    print(f"\n{'=' * 50}")
    print(f"站点: {name} ({url})")
    print("=" * 50)

    account = resolve_credentials(account, verbose=True)

    client = NewAPICheckin(
        url,
        account.get("session") or "",
        str(account["user_id"]) if account.get("user_id") else None,
        account.get("cf_clearance"),
        account.get("login_username"),
        account.get("login_password"),
        account.get("access_token"),
    )

    started = time.time()
    info = client.get_user_info(verbose=verbose)
    if not info:
        return {"name": name, "url": url, "success": False, "message": "获取用户信息失败（认证无效）"}

    print(f"  用户: {info.get('username')}  余额: {info.get('quota', 0) / 500000:.2f}  "
          f"已用: {info.get('used_quota', 0) / 500000:.2f}")

    result = client.checkin()
    return {
        "name": name,
        "url": url,
        "success": bool(result.get("success")),
        "message": result.get("message", ""),
        "checkin_date": result.get("checkin_date"),
        "quota_awarded": result.get("quota_awarded"),
        "quota": info.get("quota"),
        "used_quota": info.get("used_quota"),
        "bonus_quota": info.get("bonus_quota"),
        "user": info.get("username"),
        "elapsed": round(time.time() - started, 1),
    }


def main() -> int:
    load_env_file()
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    only = None
    if "--only" in sys.argv:
        idx = sys.argv.index("--only")
        if idx + 1 < len(sys.argv):
            only = sys.argv[idx + 1].lower()

    accounts_str = os.environ.get("NEWAPI_ACCOUNTS", "")
    accounts = parse_accounts(accounts_str)
    if only:
        accounts = [a for a in accounts
                    if only in (a.get("name") or "").lower() or only in a["url"].lower()]
    if not accounts:
        print("未配置任何账号：请在 .env 里设置 NEWAPI_ACCOUNTS")
        return 1

    t0 = time.time()
    started_at = time.strftime("%Y-%m-%d %H:%M:%S")
    print("=" * 50)
    print("NewAPI 自动签到（本地启动器）")
    print(f"执行时间: {started_at}")
    print(f"站点数: {len(accounts)}")
    print("=" * 50)

    results = []
    for account in accounts:
        try:
            results.append(run_one(account, verbose=verbose))
        except Exception as e:
            results.append({"name": account.get("name") or account["url"],
                            "url": account["url"], "success": False,
                            "message": f"异常: {e}"})

    print("\n" + "=" * 50)
    print("汇总")
    print("=" * 50)
    ok = 0
    for r in results:
        flag = "✅" if r["success"] else "❌"
        extra = ""
        if r.get("quota_awarded"):
            extra = f"  +{r['quota_awarded'] / 500000:.2f}"
        print(f"{flag} {r['name']}: {r.get('message', '')}{extra}")
        ok += 1 if r["success"] else 0
    print(f"\n成功 {ok}/{len(results)}")

    # ---- 邮件通知 ----
    if "--no-email" in sys.argv:
        print("[邮件] 已指定 --no-email，跳过发送")
    elif os.environ.get("EMAIL_TO"):
        import email_report

        email_report.send_mail(
            email_report.build_subject(results, started_at),
            email_report.build_text(results, started_at, round(time.time() - t0, 1)),
            email_report.build_html(results, started_at, round(time.time() - t0, 1)),
        )
    else:
        print("[邮件] 未配置 EMAIL_TO，跳过发送")

    return 0 if ok > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
