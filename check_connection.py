#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""连通性自检：确认 instaloader 能访问目标账号，并列出最近几条帖子的概要。

用法:
    python check_connection.py namoridane
    python check_connection.py namoridane --proxy http://127.0.0.1:7890
    python check_connection.py https://www.instagram.com/namoridane/

只读取公开信息，不下载任何文件，适合在正式下载前排查网络 / 代理 / 限流问题。
"""

import argparse
import itertools
import os
from pathlib import Path

import instaloader

from ins_downloader import load_env_file, normalize_proxy, parse_target


def main() -> int:
    load_env_file(Path(__file__).with_name(".env"))

    parser = argparse.ArgumentParser(description="检查能否正常访问指定 Instagram 账号。")
    parser.add_argument("target", help="账号名或主页链接")
    parser.add_argument("--proxy", help="代理地址，如 http://127.0.0.1:7890")
    parser.add_argument("--limit", type=int, default=3, help="列出的帖子条数")
    args = parser.parse_args()

    if args.proxy:
        proxy = normalize_proxy(args.proxy)
        for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"):
            os.environ[name] = proxy
        print(f"[i] 使用代理: {proxy}")

    username = parse_target(args.target)
    loader = instaloader.Instaloader(quiet=True)
    profile = instaloader.Profile.from_username(loader.context, username)
    print(
        f"账号: {profile.username} | 昵称: {profile.full_name} | "
        f"粉丝: {profile.followers} | 帖子: {profile.mediacount} | 私密: {profile.is_private}"
    )
    for index, post in enumerate(itertools.islice(profile.get_posts(), args.limit), 1):
        frames = len(post.get_sidecar_nodes()) if post.typename == "GraphSidecar" else 1
        caption = (post.caption or "").replace("\n", " ")[:60]
        print(f"{index}. {post.date_utc:%Y-%m-%d %H:%M} {post.shortcode} {post.typename} "
              f"frames={frames} {caption}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
