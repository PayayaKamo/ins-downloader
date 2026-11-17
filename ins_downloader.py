#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Instagram 公开账号图片批量下载工具（基于 instaloader）。

依赖:
    pip install instaloader

用法示例:
    python ins_downloader.py namoridane
    python ins_downloader.py https://www.instagram.com/namoridane/
    python ins_downloader.py namoridane -o D:/instagram -n 50
    python ins_downloader.py namoridane --since 2024-01-01 --until 2025-12-31
    python ins_downloader.py namoridane --videos          # 连同视频一起下
    python ins_downloader.py namoridane --login myuser    # 登录（私密账号/被限流时用）
    python ins_downloader.py namoridane --cookies-from-browser chrome   # 复用浏览器登录态
    python ins_downloader.py namoridane --proxy http://127.0.0.1:7890
    python ins_downloader.py namoridane --dry-run         # 只看会下载什么

凭据:
    不要把账号密码写进脚本或提交到仓库。可复制 .env.example 为 .env（已被 .gitignore 忽略），
    在其中填写 INS_USERNAME / INS_PASSWORD / HTTP(S)_PROXY，脚本会自动读取。

输出结构:
    <output>/<username>/2025-09-22_09-00-03_DO4jShFklJW.jpg
    <output>/<username>/2025-09-22_09-00-03_DO4jShFklJW_1.jpg   # 多图帖的第 2 张
    <output>/<username>/2025-09-22_09-00-03_DO4jShFklJW.txt     # 文案
    <output>/<username>/2025-09-22_09-00-03_DO4jShFklJW.json    # 完整元数据
    <output>/<username>/_index.csv                              # 所有帖子的汇总索引
"""

import argparse
import csv
import getpass
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import instaloader
from instaloader.nodeiterator import FrozenNodeIterator, resumable_iteration

INDEX_NAME = "_index.csv"
INDEX_FIELDS = [
    "shortcode", "date_local", "date_utc", "type", "media_count",
    "likes", "comments", "local_file", "url", "caption",
]
DEFAULT_FILENAME_PATTERN = "{date_local:%Y-%m-%d_%H-%M-%S}_{shortcode}"


def load_env_file(path: Path) -> None:
    """读取脚本目录下的 .env（每行 KEY=VALUE），不覆盖已存在的环境变量。"""
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and value and key not in os.environ:
            os.environ[key] = value


def parse_target(value: str) -> str:
    """把 instagram.com/xxx/ 之类的链接或 @用户名 统一成用户名。"""
    value = value.strip().lstrip("@")
    if "instagram.com" in value:
        path = urlparse(value if "://" in value else "https://" + value).path
        # /p/<shortcode>/ 之类的帖子链接不支持
        parts = [p for p in path.split("/") if p]
        if len(parts) >= 2 and parts[0] in ("p", "reel", "reels", "tv", "stories"):
            raise SystemExit(f"不支持帖子/快拍链接，请传入账号主页: {value}")
        if parts:
            return parts[0]
        raise SystemExit(f"无法解析账号名: {value}")
    return value


def normalize_proxy(proxy: str) -> str:
    """补全协议头，例如 127.0.0.1:7890 -> http://127.0.0.1:7890。"""
    if "://" not in proxy:
        proxy = "http://" + proxy
    return proxy


def detect_proxy() -> str:
    """依次从环境变量、Windows 系统设置中猜测可用代理。"""
    for name in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy", "ALL_PROXY", "all_proxy"):
        value = os.environ.get(name)
        if value:
            return normalize_proxy(value)
    if os.name == "nt":
        try:
            import winreg

            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
            )
            enabled = winreg.QueryValueEx(key, "ProxyEnable")[0]
            server = winreg.QueryValueEx(key, "ProxyServer")[0]
            if enabled and server:
                if "=" in server:  # 形如 http=host:port;https=host:port
                    protocols = dict(
                        part.split("=", 1) for part in server.split(";") if "=" in part
                    )
                    server = protocols.get("https") or protocols.get("http") or ""
                if server:
                    return normalize_proxy(server)
        except Exception:
            pass
    return ""


def build_loader(args, proxy: str) -> instaloader.Instaloader:
    outdir = Path(args.output).expanduser().resolve()
    loader = instaloader.Instaloader(
        quiet=not args.verbose,
        dirname_pattern=str(outdir / "{target}"),
        filename_pattern=args.filename_pattern,
        download_pictures=True,
        download_videos=args.videos,
        download_video_thumbnails=args.videos,
        save_metadata=not args.no_metadata,
        compress_json=False,
        post_metadata_txt_pattern="" if args.no_captions else "{caption}",
        request_timeout=args.timeout,
        resume_prefix=None,
        max_connection_attempts=3,
    )
    if proxy:
        # instaloader 内部会不断新建 requests.Session，只有环境变量能贯穿所有会话
        for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"):
            os.environ[name] = proxy
    return loader


def apply_browser_cookies(loader: instaloader.Instaloader, browser: str, cookie_file=None) -> None:
    """复用浏览器里已登录的 Instagram Cookie（需要 pip install browser-cookie3）。"""
    try:
        import browser_cookie3
    except ImportError:
        raise SystemExit("读取浏览器 Cookie 需要先安装: pip install browser-cookie3")
    browsers = {
        "brave": browser_cookie3.brave, "chrome": browser_cookie3.chrome,
        "chromium": browser_cookie3.chromium, "edge": browser_cookie3.edge,
        "firefox": browser_cookie3.firefox, "librewolf": browser_cookie3.librewolf,
        "opera": browser_cookie3.opera, "opera_gx": browser_cookie3.opera_gx,
        "safari": browser_cookie3.safari, "vivaldi": browser_cookie3.vivaldi,
    }
    if browser not in browsers:
        raise SystemExit(f"不支持的浏览器: {browser}，可选: {', '.join(browsers)}")
    try:
        jar = list(browsers[browser](cookie_file=cookie_file))
    except Exception as exc:
        raise SystemExit(f"读取 {browser} 的 Cookie 失败: {exc}")
    cookies = {c.name: c.value for c in jar if "instagram" in c.domain}
    if not cookies:
        raise SystemExit(f"{browser} 中没有找到 Instagram 登录 Cookie，请先在浏览器登录 Instagram")
    loader.context.update_cookies(cookies)
    user = loader.test_login()
    if not user:
        raise SystemExit("Cookie 无效（可能已过期），请在浏览器重新登录 Instagram")
    loader.context.username = user
    print(f"[+] 已从 {browser} 读取登录态: {user}")


def load_resume(context, path: str) -> FrozenNodeIterator:
    with open(path, "r", encoding="utf-8") as fh:
        return FrozenNodeIterator(**json.load(fh))


def save_resume(frozen: FrozenNodeIterator, path: str) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(frozen._asdict(), fh)


def do_login(loader: instaloader.Instaloader, args) -> None:
    if not args.login:
        return
    user = args.login
    loaded = False
    try:
        loader.load_session_from_file(user, args.session_file)
        # 有限流风险时 test_login 的 GraphQL 校验本身会返回 429；
        # 会话文件能加载即视为可用，真正的鉴权问题会在下载时暴露。
        loaded = True
    except FileNotFoundError:
        pass
    except Exception as exc:
        print(f"[!] 读取已保存的登录态失败: {exc}")

    if not loaded:
        password = args.password or os.environ.get("INS_PASSWORD")
        if not password:
            if not sys.stdin.isatty():
                raise SystemExit(
                    f"[x] 没有可用的登录态文件: {args.session_file or '默认路径'}；"
                    "非交互运行请先准备 session 文件并用 --session-file 指定。"
                )
            password = getpass.getpass(f"{user} 的 Instagram 密码: ")
        try:
            loader.login(user, password)
        except instaloader.TwoFactorAuthRequiredException:
            code = input("请输入两步验证码: ").strip()
            loader.two_factor_login(code)
        loader.save_session_to_file(args.session_file)
        print(f"[+] 已登录: {user}（登录态已保存，下次免密）")
    else:
        print(f"[+] 使用已保存的登录态: {user}")


def apply_web_headers(loader: instaloader.Instaloader, referer: str = "https://www.instagram.com/") -> None:
    """伪装成浏览器 Web 请求，规避 GraphQL 接口的 feedback_required 拦截。"""
    version = "143.0.3650.139"
    loader.context._session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            f"(KHTML, like Gecko) Chrome/{version} Safari/537.36 Edg/{version}"
        ),
        "x-ig-www-claim": "0",
        "x-asbd-id": "129477",
        "sec-ch-ua": '"Microsoft Edge";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "Referer": referer,
        "Origin": "https://www.instagram.com",
    })


def parse_day(value: str, opt: str) -> datetime:
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        raise SystemExit(f"{opt} 需要 YYYY-MM-DD 格式，收到: {value}")


def safe(getter, default=None):
    try:
        return getter()
    except Exception:
        return default


def caption_of(post) -> str:
    text = safe(lambda: post.caption, "") or ""
    return text.replace("\r\n", "\n").strip()


def make_row(loader, post, username: str) -> dict:
    base_name = ""
    try:
        base_name = os.path.basename(loader.format_filename(post, target=username))
    except Exception:
        pass
    cover_url = safe(lambda: post.url, "") or ""
    return {
        "shortcode": post.shortcode,
        "date_local": post.date_local.strftime("%Y-%m-%d %H:%M:%S"),
        "date_utc": post.date_utc.strftime("%Y-%m-%d %H:%M:%S"),
        "type": post.typename.replace("Graph", ""),
        "media_count": safe(lambda: post.mediacount, 1),
        "likes": safe(lambda: post.likes, -1),
        "comments": safe(lambda: post.comments, -1),
        "local_file": base_name,
        "url": cover_url,
        "caption": caption_of(post),
    }


def load_index(path: Path) -> dict:
    rows = {}
    if not path.is_file():
        return rows
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                if row.get("shortcode"):
                    rows[row["shortcode"]] = {k: row.get(k, "") for k in INDEX_FIELDS}
    except Exception as exc:
        print(f"[!] 读取旧索引失败，将重建: {exc}")
    return rows


def save_index(path: Path, rows: dict) -> None:
    ordered = sorted(rows.values(), key=lambda r: r.get("date_utc", ""), reverse=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=INDEX_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(ordered)


def download_profile(args, loader, username: str) -> int:
    print(f"\n=== @{username} ===")
    if args.login:
        apply_web_headers(loader, f"https://www.instagram.com/{username}/")
    try:
        profile = instaloader.Profile.from_username(loader.context, username)
    except instaloader.ProfileNotExistsException:
        print(f"[x] 账号不存在: {username}")
        return 1
    except instaloader.ConnectionException as exc:
        print(f"[x] 连接失败: {exc}")
        print("    如果你的网络需要代理，试试 --proxy http://127.0.0.1:7890")
        return 1

    print(f"昵称: {profile.full_name}")
    media_count = safe(lambda: profile.mediacount)
    followers = safe(lambda: profile.followers)
    is_private = safe(lambda: profile.is_private, False)
    total_posts = media_count if media_count is not None else "未知"
    print(f"粉丝: {followers if followers is not None else '未知'} | 帖子: {total_posts} | 私密: {is_private}")

    if is_private and not loader.test_login():
        print("[x] 这是私密账号，需要用 --login 登录已关注的账号后再下载。")
        return 1

    # 头像/计数这类元数据走 graphql/query，容易被 feedback_required 拦截；
    # 帖子列表走 api/graphql，通常仍可用。用最小元数据兜底，避免整轮下载被计数接口拖垮。
    if not getattr(profile, "_has_full_metadata", False):
        node = dict(getattr(profile, "_node", None) or {})
        node.setdefault("username", profile.username)
        node.setdefault("is_private", False)
        node.setdefault("id", node.get("pk") or node.get("userid"))
        node.setdefault("pk", node.get("id"))
        node.setdefault("friendship_status", {"following": True})
        profile._node = node
        profile._has_full_metadata = True
        print("[i] 元数据接口受限，已改用页面数据继续。")

    outdir = Path(args.output).expanduser().resolve() / username
    outdir.mkdir(parents=True, exist_ok=True)

    if args.profile_pic and not args.dry_run:
        loader.download_profilepic(profile)
        print("[+] 已下载头像")

    since = parse_day(args.since, "--since") if args.since else None
    until = parse_day(args.until, "--until") if args.until else None

    index = load_index(outdir / INDEX_NAME)
    resume_path = outdir / "_resume_posts.json"
    processed = failed = 0
    total_media = 0
    failed_codes = []

    attempt = 0
    finished = False
    stalled = False
    last_progress = time.time()
    while not finished:
        attempt += 1
        try:
            iterator = profile.get_posts()
            # resumable_iteration 会把翻页游标（含出错的那一条）存到 resume_path，
            # 下次重试时从断点接着走，已下载的文件由 instaloader 自动跳过。
            with resumable_iteration(
                context=loader.context,
                iterator=iterator,
                load=load_resume,
                save=save_resume,
                format_path=lambda _magic: str(resume_path),
            ) as (is_resuming, start_index):
                if is_resuming:
                    processed = start_index
                    print(f"[i] 从断点继续（前面已完成 {start_index} 条）")
                for post in iterator:
                    day = post.date_utc.date()
                    if since and day < since.date():
                        continue
                    if until and day > until.date():
                        continue
                    if args.max_posts and processed >= args.max_posts:
                        finished = True
                        break
                    if args.skip_pinned and safe(lambda: post.is_pinned, False):
                        continue

                    processed += 1
                    last_progress = time.time()
                    total_media += safe(lambda: post.mediacount, 1)
                    row = make_row(loader, post, username)
                    index[post.shortcode] = row

                    name = f"{row['date_local']}  {post.shortcode}  [{row['type']}]"
                    if args.dry_run:
                        print(f"[{processed}] {name}  -> {row['local_file']}")
                        continue

                    print(f"[{processed}] {name}")
                    for dl_attempt in range(3):
                        try:
                            loader.download_post(post, target=profile.username)
                            break
                        except Exception as exc:
                            if dl_attempt == 2:
                                failed += 1
                                failed_codes.append(post.shortcode)
                                print(f"    [!] 下载失败（已重试 3 次）: {str(exc)[:120]}")
                            else:
                                time.sleep(5)
                    if processed % 25 == 0:  # 定期落盘索引，避免中断后丢失进度
                        save_index(outdir / INDEX_NAME, index)
                    if args.post_delay:
                        time.sleep(args.post_delay)
            finished = True
        except (instaloader.LoginRequiredException, instaloader.PrivateProfileNotFollowedException) as exc:
            print(f"[x] 需要登录才能继续: {exc}")
            return 1
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            if attempt >= args.max_retries:
                print(f"[x] 连续 {attempt} 次中断，已停止: {type(exc).__name__}: {str(exc)[:160]}")
                print("    断点已保存，重新运行同一命令即可继续补齐。")
                break
            wait = min(args.retry_wait * attempt, 300)
            print(f"[!] 第 {attempt} 次中断: {type(exc).__name__}: {str(exc)[:160]}")
            print(f"    {wait} 秒后自动重试（断点已保存，已完成文件不会重复下载）")
            deadline = time.time() + wait
            while time.time() < deadline:  # 分段等待，顺便检测是否长时间无进展
                time.sleep(min(5, max(0.2, deadline - time.time())))
                if args.stall_timeout and time.time() - last_progress > args.stall_timeout:
                    stalled = True
                    break
            if stalled:
                print(f"[x] 已 {int(time.time() - last_progress)} 秒无新进展，判定为卡住；"
                      f"断点已保存，退出以便重开（重开会从断点继续）。")
                break

    if not args.dry_run:
        save_index(outdir / INDEX_NAME, index)
        unique = len(index)
        print(f"\n[✓] @{username}: 本轮处理 {processed} 条，索引内共 {unique} 条帖子（约 {total_media} 张图片/视频）")
        if failed_codes:
            print(f"    [!] 有 {len(failed_codes)} 条下载失败，重跑同一命令会自动补下: {', '.join(failed_codes[:10])}"
                  f"{' ...' if len(failed_codes) > 10 else ''}")
        print(f"    保存目录: {outdir}")
        print(f"    索引文件: {outdir / INDEX_NAME}")
        if not finished:
            print("    [!] 迭代未走到末尾，本次未完成，请重新运行以继续。")
    if stalled:
        return 3
    return 0 if (finished and not failed) else 2


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="批量下载 Instagram 公开账号的全部图片（含文案、元数据和索引）。",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("targets", nargs="+", help="账号名或主页链接，可传多个")
    parser.add_argument("-o", "--output", default="downloads", help="保存根目录")
    parser.add_argument("-n", "--max-posts", type=int, default=0, help="每个账号最多下载的帖子数，0 表示全部")
    parser.add_argument("--since", help="只下载该日期之后的帖子（UTC，YYYY-MM-DD）")
    parser.add_argument("--until", help="只下载该日期之前的帖子（UTC，YYYY-MM-DD）")
    parser.add_argument("--videos", action="store_true", help="同时下载视频（默认只保存图片）")
    parser.add_argument("--profile-pic", action="store_true", help="同时下载头像")
    parser.add_argument("--skip-pinned", action="store_true", help="跳过置顶帖子")
    parser.add_argument("--no-captions", action="store_true", help="不保存文案 txt")
    parser.add_argument("--no-metadata", action="store_true", help="不保存 json 元数据")
    parser.add_argument("--login", metavar="USER", help="登录的 Instagram 用户名（私密账号/被限流时使用）")
    parser.add_argument("--password", help="登录密码，不填则交互输入或用环境变量 INS_PASSWORD")
    parser.add_argument("--session-file", help="登录态文件路径，默认 ~/.instaloader/session-<user>")
    parser.add_argument("--proxy", help="代理地址，如 http://127.0.0.1:7890；默认自动读取系统代理")
    parser.add_argument("--no-proxy", action="store_true", help="强制直连，不走代理")
    parser.add_argument("--cookies-from-browser", metavar="BROWSER",
                        help="复用浏览器登录态（chrome/edge/firefox 等），需要 pip install browser-cookie3")
    parser.add_argument("--cookie-file", help="配合 --cookies-from-browser 指定 Cookie 文件")
    parser.add_argument("--max-retries", type=int, default=12, help="遇到限流/断连时的最大重试次数")
    parser.add_argument("--retry-wait", type=float, default=15, help="重试等待基数（秒），按次数递增，最长 300 秒")
    parser.add_argument("--post-delay", type=float, default=1.0, help="每条帖子之间的间隔秒数，放慢节奏避免限流")
    parser.add_argument("--stall-timeout", type=float, default=600, help="连续无进展超过该秒数则保存断点并退出，0 表示不限")
    parser.add_argument("--timeout", type=float, default=60, help="单次请求超时（秒）")
    parser.add_argument("--filename-pattern", default=DEFAULT_FILENAME_PATTERN,
                        help="文件名模板，可用 {date_local} {date_utc} {shortcode} {mediaid} {typename}")
    parser.add_argument("--dry-run", action="store_true", help="只列出将要下载的内容，不实际下载")
    parser.add_argument("-v", "--verbose", action="store_true", help="显示 instaloader 详细日志")
    return parser


def main() -> int:
    load_env_file(Path(__file__).with_name(".env"))
    parser = make_parser()
    args = parser.parse_args()

    if not args.login and os.environ.get("INS_USERNAME"):
        args.login = os.environ["INS_USERNAME"]

    try:
        targets = [parse_target(t) for t in args.targets]
    except SystemExit as exc:
        print(exc, file=sys.stderr)
        return 2

    proxy = "" if args.no_proxy else normalize_proxy(args.proxy) if args.proxy else detect_proxy()
    if proxy:
        print(f"[i] 使用代理: {proxy}")
    else:
        print("[i] 未检测到代理，直连 Instagram")

    loader = build_loader(args, proxy)
    try:
        if args.cookies_from_browser:
            apply_browser_cookies(loader, args.cookies_from_browser, args.cookie_file)
        do_login(loader, args)
        if args.login:
            apply_web_headers(loader)
    except instaloader.BadCredentialsException:
        print("[x] 密码错误。")
        return 1
    except instaloader.LoginException as exc:
        print(f"[x] 登录失败: {exc}")
        return 1
    except Exception as exc:
        print(f"[x] 登录异常: {exc}")
        return 1
    results = []
    for username in targets:
        results.append(download_profile(args, loader, username))
    return max(results) if results else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n已中断。")
        sys.exit(130)
