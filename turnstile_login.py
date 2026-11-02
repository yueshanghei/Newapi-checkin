#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
带 Turnstile 的 New API 站点登录

背景:
    启用 Turnstile 的站点（/api/status 里 turnstile_check=true），
    POST /api/user/login 必须带有效 turnstile token，纯 HTTP 会被拒绝：
        {"message":"Turnstile token is empty"}
    但真实（未被自动化标记的）Chrome/Edge 能正常拿到 token。
    所以这里用「真实浏览器解 token + requests 提交登录」两段式：
      - 浏览器只负责渲染 Turnstile 组件并取出 token（90s 有效、一次性）
      - 登录本身仍用 requests，拿到 access_token / session 后交给 checkin 用

为什么不用 Playwright 启动浏览器:
    Playwright 自己启动的浏览器带自动化标记，Turnstile 会静默卡死；
    这里复刻 turnstile_solver 的做法——自己拉起带 --remote-debugging-port 的
    真实浏览器，再用 Playwright 通过 CDP 连上去操作，浏览器本身没有自动化标记。
"""
from __future__ import annotations

import json
import sys
import time

import requests

import turnstile_solver as ts

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

USERNAME_SELECTORS = ('input[name="username"]', 'input[name="email"]', 'input[type="text"]')
PASSWORD_SELECTORS = ('input[name="password"]', 'input[type="password"]')
TOKEN_INPUT = 'input[name="cf-turnstile-response"]'


def _first_visible(page, selectors):
    for sel in selectors:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                return el
        except Exception:
            continue
    return None


def _token_value(page) -> str:
    try:
        return page.eval_on_selector(TOKEN_INPUT, "e => e.value") or ""
    except Exception:
        return ""


def _click_widget(page, verbose=True) -> bool:
    try:
        iframe = page.query_selector('iframe[src*="challenges.cloudflare.com"]')
    except Exception:
        return False
    if not iframe:
        return False
    try:
        iframe.scroll_into_view_if_needed()
        time.sleep(0.5)
        box = iframe.bounding_box()
    except Exception:
        return False
    if not box or box["width"] < 50:
        return False
    cx, cy = box["x"] + 30, box["y"] + box["height"] / 2
    if verbose:
        print(f"  [turnstile] 点击组件勾选框 ({cx:.0f}, {cy:.0f})")
    page.mouse.move(cx - 15, cy - 8)
    time.sleep(0.3)
    page.mouse.move(cx - 3, cy)
    time.sleep(0.3)
    page.mouse.click(cx, cy)
    return True


def get_turnstile_token(base_url: str, path: str = "/sign-in", max_wait: int = 90,
                        proxy: str | None = None, verbose: bool = True) -> str | None:
    """在站点页面里渲染并解出 Turnstile token（一次性，90s 内有效）"""
    base_url = base_url.rstrip("/")
    if proxy is None:
        proxy = ts._get_system_proxy()

    proc, dbg_port = ts._launch_chrome(proxy, url=base_url + path)
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = None
            for _ in range(3):
                try:
                    browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{dbg_port}")
                    break
                except Exception:
                    time.sleep(3)
            if browser is None:
                raise RuntimeError("CDP 连接失败")

            ctx = browser.contexts[0]
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.set_default_timeout(30000)
            page.wait_for_load_state("domcontentloaded")
            time.sleep(3)

            # 触发组件渲染：有的站点是登录时才挂载，先随便填一下表单
            user_el = _first_visible(page, USERNAME_SELECTORS)
            pass_el = _first_visible(page, PASSWORD_SELECTORS)
            if user_el:
                user_el.fill("probe")
            if pass_el:
                pass_el.fill("probe")
            # 部分地区站点要求勾选「同意用户协议」才允许校验
            try:
                page.evaluate("() => {const c=document.querySelector('#legal-consent');"
                              " if(c&&!c.checked) c.click();}")
            except Exception:
                pass

            token = ""
            clicked = False
            deadline = time.time() + max_wait
            while time.time() < deadline:
                token = _token_value(page)
                if token:
                    break
                if not clicked:
                    clicked = _click_widget(page, verbose=verbose)
                time.sleep(2)

            try:
                browser.close()
            except Exception:
                pass

            if token:
                if verbose:
                    print(f"  [turnstile] token 获取成功（{len(token)} 字符）")
                return token
            if verbose:
                print("  [turnstile] 等待 token 超时")
            return None
    except Exception as e:
        print(f"  [turnstile] 异常: {e}")
        return None
    finally:
        try:
            proc.terminate()
        except Exception:
            pass


def http_login(base_url: str, username: str, password: str, turnstile: str = "",
               session: requests.Session | None = None):
    """POST /api/user/login，返回 (session_cookie, access_token, user_id, message)"""
    base_url = base_url.rstrip("/")
    s = session or requests.Session()
    s.headers.update({"User-Agent": UA, "Accept": "application/json, text/plain, */*"})
    r = s.post(
        f"{base_url}/api/user/login" + (f"?turnstile={turnstile}" if turnstile else ""),
        json={"username": username, "password": password},
        headers={"Referer": f"{base_url}/sign-in", "Origin": base_url, "new-api-user": "-1"},
        timeout=30,
    )
    try:
        data = r.json()
    except Exception:
        return None, None, None, f"响应非 JSON (HTTP {r.status_code}): {r.text[:120]}"

    if not data.get("success"):
        return None, None, None, data.get("message", "登录失败")

    body = data.get("data") or {}
    access_token = body.get("access_token")
    uid = (body.get("user") or {}).get("id") or body.get("id")
    session_cookie = s.cookies.get("session")
    return session_cookie, access_token, uid, ""


def login(base_url: str, username: str, password: str, verbose: bool = True):
    """
    自动判断站点是否需要 Turnstile，需要就先解 token 再登录。
    返回 dict(session, access_token, user_id) 或 None
    """
    base_url = base_url.rstrip("/")
    need_turnstile = False
    try:
        st = requests.get(f"{base_url}/api/status", timeout=30,
                          headers={"User-Agent": UA}).json()
        need_turnstile = bool((st.get("data") or {}).get("turnstile_check"))
    except Exception as e:
        if verbose:
            print(f"  [login] 读取 /api/status 失败: {e}")

    token = ""
    if need_turnstile:
        if verbose:
            print("  [login] 站点启用了 Turnstile，先用真实浏览器解 token ...")
        token = get_turnstile_token(base_url, verbose=verbose) or ""

    session_cookie, access_token, uid, msg = http_login(base_url, username, password, token)
    if msg and need_turnstile and "turnstile" in msg.lower():
        # token 失效/未就绪，再解一次
        if verbose:
            print(f"  [login] 首次登录失败（{msg}），重试一次 ...")
        token = get_turnstile_token(base_url, verbose=verbose) or ""
        session_cookie, access_token, uid, msg = http_login(base_url, username, password, token)

    # 短时间登录太多次会被站点限流（429），等一会儿再试一次
    if msg and "429" in str(msg):
        wait = 90
        if verbose:
            print(f"  [login] 被限流（{msg}），等待 {wait}s 后重试 ...")
        time.sleep(wait)
        if need_turnstile:
            token = get_turnstile_token(base_url, verbose=verbose) or ""
        session_cookie, access_token, uid, msg = http_login(base_url, username, password, token)

    if msg:
        if verbose:
            print(f"  [login] 登录失败: {msg}")
        return None
    if verbose:
        print(f"  [login] 登录成功 uid={uid}，"
              f"{'access_token' if access_token else 'session cookie'}")
    return {"session": session_cookie, "access_token": access_token, "user_id": uid}


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("用法: python turnstile_login.py <base_url> <username> <password>")
        sys.exit(2)
    result = login(sys.argv[1], sys.argv[2], sys.argv[3])
    if not result:
        sys.exit(1)
    print(json.dumps({k: ("<set>" if v else None) for k, v in result.items()}, ensure_ascii=False))
