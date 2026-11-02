#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
签到结果邮件通知

配置（.env）:
    EMAIL_SMTP_HOST=smtp.qq.com     # 默认 smtp.qq.com
    EMAIL_SMTP_PORT=465             # 465 = SSL，587 = STARTTLS
    EMAIL_USER=xxx@qq.com           # 发件邮箱（登录名）
    EMAIL_PASS=xxxxxxxxxxxx         # QQ 邮箱「授权码」，不是登录密码
    EMAIL_TO=你的邮箱@qq.com       # 收件人，多个用逗号分隔
    EMAIL_FROM=xxx@qq.com           # 可选，默认同 EMAIL_USER
"""
from __future__ import annotations

import os
import smtplib
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr


def _fmt_quota(quota) -> str:
    if quota is None:
        return "-"
    return f"${quota / 500000:,.2f}"


def build_subject(results: list, execution_time: str) -> str:
    ok = sum(1 for r in results if r.get("success"))
    total = len(results)
    date = execution_time.split(" ")[0]
    flag = "✅" if ok == total else ("⚠️" if ok else "❌")
    return f"{flag} NewAPI 签到 {date} ｜ {ok}/{total} 成功"


def build_text(results: list, execution_time: str, elapsed: float) -> str:
    ok = sum(1 for r in results if r.get("success"))
    lines = [
        "NewAPI 每日签到报告",
        f"执行时间: {execution_time}",
        f"总耗时: {elapsed:.0f}s",
        "",
        "-" * 62,
    ]
    for r in results:
        flag = "✅" if r.get("success") else "❌"
        award = f"+{_fmt_quota(r.get('quota_awarded'))}" if r.get("quota_awarded") else ""
        lines.append(f"{flag} {r.get('name', '')}")
        lines.append(f"    状态: {r.get('message', '')} {award}".rstrip())
        if r.get("quota") is not None:
            lines.append(
                f"    余额: {_fmt_quota(r.get('quota'))}    "
                f"已用: {_fmt_quota(r.get('used_quota'))}    "
                f"赠送: {_fmt_quota(r.get('bonus_quota'))}"
            )
        lines.append(f"    地址: {r.get('url', '')}")
    lines.append("-" * 62)
    lines.append(f"汇总: 成功 {ok} / 共 {len(results)}")
    failed = [r.get("name", "") for r in results if not r.get("success")]
    if failed:
        lines.append(f"失败站点: {', '.join(failed)}")
    return "\n".join(lines)


def build_html(results: list, execution_time: str, elapsed: float) -> str:
    ok = sum(1 for r in results if r.get("success"))
    total = len(results)
    rows = []
    for r in results:
        good = r.get("success")
        bg = "#f6ffed" if good else "#fff1f0"
        color = "#237804" if good else "#cf1322"
        status = "✅ 成功" if good else "❌ 失败"
        award = _fmt_quota(r.get("quota_awarded")) if r.get("quota_awarded") else "-"
        quota = _fmt_quota(r.get("quota")) if r.get("quota") is not None else "-"
        used = _fmt_quota(r.get("used_quota")) if r.get("used_quota") is not None else "-"
        rows.append(
            f'<tr style="background:{bg};">'
            f'<td style="padding:8px 10px;border-bottom:1px solid #eee;">'
            f'<b>{r.get("name", "")}</b><br>'
            f'<span style="color:#888;font-size:12px;">{r.get("url", "")}</span></td>'
            f'<td style="padding:8px 10px;border-bottom:1px solid #eee;color:{color};">{status}</td>'
            f'<td style="padding:8px 10px;border-bottom:1px solid #eee;color:{color};">{award}</td>'
            f'<td style="padding:8px 10px;border-bottom:1px solid #eee;">{quota}</td>'
            f'<td style="padding:8px 10px;border-bottom:1px solid #eee;color:#888;">{used}</td>'
            f'<td style="padding:8px 10px;border-bottom:1px solid #eee;font-size:12px;">'
            f'{r.get("message", "")}</td>'
            f"</tr>"
        )

    summary_color = "#237804" if ok == total else ("#d46b08" if ok else "#cf1322")
    return f"""<html><body style="margin:0;padding:20px;background:#f5f5f5;
font-family:-apple-system,'Segoe UI','Microsoft YaHei',sans-serif;">
<div style="max-width:760px;margin:0 auto;background:#fff;border-radius:10px;
overflow:hidden;box-shadow:0 1px 4px rgba(0,0,0,.08);">
  <div style="background:linear-gradient(135deg,#1677ff,#69b1ff);padding:20px 24px;color:#fff;">
    <div style="font-size:19px;font-weight:600;">NewAPI 每日签到报告</div>
    <div style="font-size:13px;opacity:.9;margin-top:6px;">
      {execution_time} ｜ 耗时 {elapsed:.0f}s
    </div>
  </div>
  <div style="padding:16px 24px 4px;">
    <span style="font-size:15px;color:{summary_color};font-weight:600;">
      成功 {ok} / {total}
    </span>
  </div>
  <div style="padding:8px 24px 20px;">
    <table style="width:100%;border-collapse:collapse;font-size:14px;">
      <thead>
        <tr style="text-align:left;color:#888;font-size:12px;">
          <th style="padding:6px 10px;">站点</th>
          <th style="padding:6px 10px;">状态</th>
          <th style="padding:6px 10px;">本次奖励</th>
          <th style="padding:6px 10px;">余额</th>
          <th style="padding:6px 10px;">已用</th>
          <th style="padding:6px 10px;">说明</th>
        </tr>
      </thead>
      <tbody>
        {''.join(rows)}
      </tbody>
    </table>
  </div>
  <div style="padding:12px 24px 20px;color:#999;font-size:12px;border-top:1px solid #f0f0f0;">
    由 newapi-checkin-v2 自动发送 · 余额按 1 美元 = 500000 额度换算
  </div>
</div></body></html>"""


def send_mail(subject: str, text: str, html: str) -> bool:
    host = os.environ.get("EMAIL_SMTP_HOST", "smtp.qq.com").strip() or "smtp.qq.com"
    port = int(os.environ.get("EMAIL_SMTP_PORT", "465") or 465)
    user = os.environ.get("EMAIL_USER", "").strip()
    password = os.environ.get("EMAIL_PASS", "").strip()
    to_raw = os.environ.get("EMAIL_TO", "").strip()
    from_addr = os.environ.get("EMAIL_FROM", "").strip() or user

    if not (user and password and to_raw):
        print("[邮件] 未配置 EMAIL_USER / EMAIL_PASS / EMAIL_TO，跳过发送")
        return False

    to_list = [a.strip() for a in to_raw.replace(";", ",").split(",") if a.strip()]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = formataddr((str(Header("NewAPI 签到机器人", "utf-8")), from_addr))
    msg["To"] = ", ".join(to_list)
    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        if port == 465:
            server = smtplib.SMTP_SSL(host, port, timeout=30)
        else:
            server = smtplib.SMTP(host, port, timeout=30)
            server.starttls()
        server.login(user, password)
        server.sendmail(from_addr, to_list, msg.as_string())
        server.quit()
        print(f"[邮件] 已发送至 {', '.join(to_list)}")
        return True
    except Exception as e:
        print(f"[邮件] 发送失败: {e}")
        return False
