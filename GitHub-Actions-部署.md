# 把签到搬到 GitHub Actions

> **状态：已部署并跑通**（2026-11-02 10:20）
>
> - 仓库：<https://github.com/yueshanghei/Newapi-checkin>（**public** fork，如果你想私有可以改）
> - Workflow：[`checkin-local.yml`](../.github/workflows/checkin-local.yml)，定时 `0 1 * * *`（北京 9:00）
> - Secrets：`NEWAPI_ACCOUNTS`、`EMAIL_USER`、`EMAIL_PASS`、`EMAIL_TO`、`EMAIL_SMTP_HOST`、`EMAIL_SMTP_PORT` 均已写入
> - 最近一次运行 **4/5 成功**：catcat ✅、gemai ✅、hkkkj ✅、hcnsec ✅，thousandyuan ❌（站点 530）
> - 本地 Windows 定时任务已 `Disable-ScheduledTask` 停用，避免一天跑两次触发 429
>
> 下面是完整的从零操作步骤（换账号/换仓库时照做）。

本地这套（Windows 任务计划程序）和 GitHub Actions 用的是**同一份代码**，
差别只是「配置从哪来」和「浏览器怎么跑」。仓库里已经放好 workflow：
[`../.github/workflows/checkin-local.yml`](../.github/workflows/checkin-local.yml)。

| | 本地（现在） | GitHub Actions |
| --- | --- | --- |
| 配置来源 | `.env` | Repository Secrets |
| 浏览器 | 真实 Edge（有桌面） | runner 自带 Chrome + `xvfb` 虚拟显示 |
| 定时 | 任务计划程序 09:00 | cron `0 1 * * *`（UTC 1:00 = 北京 9:00） |
| 日志 | `logs\run.log` | Actions 运行日志 + Artifact |
| 电脑要求 | 开机 + 保持登录 | 不需要，云端跑 |

---

## 一、准备仓库

**建议用私有仓库**（里面虽然只有 secrets，但私有更稳）。

### 方案 A：网页上传（不用装 Git，最省事）

1. GitHub → New repository → 名字随意（如 `newapi-checkin`）→ **Private** → Create
2. 进入新仓库 → **Add file → Upload files** → 把 `newapi-checkin-v2` 里**除以下内容外**全部拖进去：
   - 不要上传：`.env`、`.venv\`、`logs\`、`__pycache__\`
3. `.github` 目录网页上传容易漏，**单独建**：
   - **Add file → Create new file** → 文件名填 `.github/workflows/checkin-local.yml`
   - 打开本地 `newapi-checkin-v2\.github\workflows\checkin-local.yml`，全选粘贴 → Commit
4. 确认仓库默认分支（main）上能看到 `.github/workflows/checkin-local.yml`（定时任务只认默认分支）

### 方案 B：装 Git 后命令行推（以后更新方便）

```powershell
winget install --id Git.Git -e
# 重开一个终端，然后：
cd C:\Users\Administrator\Documents\deepseek-harness\default-workspace\newapi-checkin-v2
git init
git add .
git commit -m "newapi checkin"
git branch -M main
git remote add origin https://github.com/<你的用户名>/newapi-checkin.git
git push -u origin main
```

`.env` / `.venv` / `logs` 已在 `.gitignore` 里，不会被推上去。

> 也可以直接 Fork 上游 `Jasonliu-0/Newapi-checkin`，再把自己改过的
> `run_checkin.py`、`turnstile_login.py`、`email_report.py`、`turnstile_solver.py`、`checkin.py`
> 和 `.github/workflows/checkin-local.yml` 覆盖上去。

---

## 二、添加 Secrets

仓库 → **Settings → Secrets and variables → Actions → New repository secret**。

最少这 4 个就能跑通：

| Secret 名 | 值 |
| --- | --- |
| `NEWAPI_ACCOUNTS` | 本地 `.env` 里 `NEWAPI_ACCOUNTS=` 后面**整段 JSON**（一行） |
| `EMAIL_USER` | `你的邮箱@qq.com` |
| `EMAIL_PASS` | QQ 邮箱 SMTP 授权码（就是 `.env` 里那串 16 位） |
| `EMAIL_TO` | `你的邮箱@qq.com` |

可选：

| Secret 名 | 值 | 说明 |
| --- | --- | --- |
| `EMAIL_SMTP_HOST` | `smtp.qq.com` | 不填代码里默认就是它 |
| `EMAIL_SMTP_PORT` | `465` | 不填默认 465 |
| `EMAIL_FROM` | `你的邮箱@qq.com` | 不填等于 EMAIL_USER |

`NEWAPI_ACCOUNTS` 直接用本地这份（把密码换成真实的）：

```json
[{"url":"https://api.catcat.top","name":"catcat.top","session":"","login_username":"你的账号","login_password":"你的密码"},{"url":"https://api.thousandyuan.dpdns.org","name":"thousandyuan","session":"","login_username":"你的账号","login_password":"你的密码"},{"url":"https://gemai.huchan.cn","name":"gemai","session":"","login_username":"你的账号","login_password":"你的密码"},{"url":"https://newapi.hkkkj.qzz.io","name":"hkkkj","session":"","login_username":"你的账号","login_password":"你的密码"},{"url":"https://api.hcnsec.cn","name":"hcnsec","session":"","login_username":"你的账号","login_password":"你的密码"}]
```

> GitHub 会把 secret 值在日志里自动打码（显示成 `***`），不会泄露。

---

## 三、第一次运行

1. 仓库 → **Actions** 标签 → 如果提示，点 **I understand my workflows, go ahead and enable them**
2. 左侧选 **NewAPI 自动签到** → 右侧 **Run workflow**
   - `only` 留空 = 跑全部；想先单独试一个站点就填 `hcnsec`
   - `no_email` 勾上 = 这次不发邮件
3. 点绿色 **Run workflow**，等 2~5 分钟（Turnstile 站点会慢些）
4. 点进这次 run 看日志，成功长这样：

```
✅ catcat.top: Already checked in today
✅ gemai: 签到成功  +$15.83
✅ hkkkj: Check-in successful (Turnstile)  +$0.27
✅ hcnsec: Check-in successful (Turnstile)  +$16.87
❌ thousandyuan: 获取用户信息失败（认证无效）
成功 4/5
[邮件] 已发送至 你的邮箱@qq.com
```

同时会收到邮件；页面底部 **Artifacts** 里还能下载 `checkin-log-N`（保留了 `tee` 出来的完整日志）。

---

## 四、定时

workflow 里已经写好：

```yaml
schedule:
  - cron: '0 1 * * *'   # UTC 1:00 = 北京时间 9:00
```

想换时间就改这一行（**注意是 UTC**，北京时间减 8 小时）：

| 想要的时间（北京） | cron |
| --- | --- |
| 08:10 | `10 0 * * *` |
| 09:00 | `0 1 * * *` |
| 12:30 | `30 4 * * *` |
| 每天两次 8:10 / 20:10 | `10 0,12 * * *` |

注意：
- GitHub 的定时触发**不保证准点**，高峰时可能延后几分钟到半小时
- 仓库连续 **60 天没有任何提交**，定时会被自动停用（上游有 `keepalive.yml`，也可以自己偶尔点一次手动运行唤醒）

---

## 五、和本地定时任务的关系（二选一）

让我确认 GHA 跑通后，建议**关掉本地任务**，避免一天跑两次、重复登录被站点限流：

```powershell
# 停用（保留配置，随时能开回来）
Disable-ScheduledTask -TaskName "newapi-checkin"

# 或者彻底删除
Unregister-ScheduledTask -TaskName "newapi-checkin" -Confirm:$false
```

想两边都留着也行（比如云端挂了当备份），但要注意 429 限流：同一天同一站点登录太多次可能被临时挡。

---

## 六、可能踩的坑

| 现象 | 原因 / 处理 |
| --- | --- |
| 日志里 Turnstile 一直超时 | runner 没有真实显卡/显示，虽然用 xvfb 起了虚拟屏，个别站点仍可能更严格。先把 `only` 设成该站点单独跑几次看稳定性；实在不行就保留本地跑这两个站（hkkkj / hcnsec），其它站上云 |
| `获取用户信息失败` + 页面是 Cloudflare 挑战 | GHA 是数据中心 IP，有的站点对机房 IP 更严格。可以在账号 JSON 里加 `"cf_clearance": "..."` 或给 runner 配代理（workflow 里加 `HTTP_PROXY`/`HTTPS_PROXY` 环境变量） |
| 登录 429 | 登录太频繁。workflow 已加 `concurrency` 防并发，别一天手动点太多次 |
| 收不到邮件 | 先看日志有没有 `[邮件] 已发送`；QQ 可能丢进垃圾箱；确认 4 个 secret 都填了 |
| 定时不触发 | 检查 workflow 文件是否在默认分支；仓库是否 60 天无提交被停用；Actions 是否被禁用 |
| 想改代码后立即生效 | `git push` 到默认分支即可，下次运行用新代码 |

---

## 七、安全性

- 密码/授权码放 **Secrets**，不进代码、日志自动打码
- 仓库设为 **Private**
- 一旦 `.env` 被误提交：立刻改站点密码 + 重置 QQ 授权码，并用 `git filter-repo` 或删库重建
- 比起本地 `.env` 存明文，Secrets 更安全（缺点是不能直接看，要改得去网页）
