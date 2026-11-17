# Instagram 图片下载工具

一个基于 [instaloader](https://instaloader.github.io/) 的命令行小工具，用来归档公开的
Instagram 账号：抓取每个帖子的全部图片（含多图帖的每一张），同时保存文案、元数据和 CSV 索引。

[English](README.md) | [简体中文](README.zh-CN.md) | [日本語](README.ja.md)

## 功能说明

- 下载一个或多个公开账号的全部图片（整号，或只取某个日期区间）。
- 多图帖的每一张都单独保存，不会漏图。
- 每个帖子旁边保存一个 `.txt` 文案和一个 `.json` 元数据文件。
- 维护 `_index.csv`，用一张表汇总已下载的所有帖子。
- 已存在的文件自动跳过，中断后可从断点继续。
- 遇到限流或断连会退避重试，长时间没有进展时保存断点并干净退出。
- 自动识别 Windows 系统代理，也可以手动指定代理。
- 可选：视频、头像、只预览不下载。

## 环境要求

- Python 3.9 或更高版本
- `instaloader`（随 `requirements.txt` 安装）
- 可选：`browser-cookie3`，用于复用浏览器登录态

## 安装

```bash
git clone https://github.com/PayayaKamo/ins-downloader.git
cd ins-downloader

python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

## 使用方法

```bash
# 下载整个公开账号到 ./downloads
python ins_downloader.py namoridane

# 也可以直接给主页链接
python ins_downloader.py https://www.instagram.com/namoridane/

# 指定输出目录、只下前 50 条、连视频一起下
python ins_downloader.py namoridane -o D:/instagram -n 50 --videos

# 按发帖日期（UTC）限定范围
python ins_downloader.py namoridane --since 2024-01-01 --until 2025-12-31

# 只列出将要下载的内容，不实际下载
python ins_downloader.py namoridane --dry-run

# 走代理
python ins_downloader.py namoridane --proxy http://127.0.0.1:7890
```

常用参数：

| 参数 | 说明 |
| --- | --- |
| `-o, --output` | 输出根目录（默认 `downloads`） |
| `-n, --max-posts` | 每个账号最多下载多少条帖子，`0` 表示全部 |
| `--since` / `--until` | 只下载该 UTC 日期区间内的帖子 |
| `--videos` | 同时下载视频（默认只存图片） |
| `--profile-pic` | 同时下载头像 |
| `--skip-pinned` | 跳过置顶帖子 |
| `--login USER` | 以 `USER` 登录（私密账号或被限流时使用） |
| `--cookies-from-browser BROWSER` | 复用浏览器登录态，如 `chrome`、`edge`、`firefox` |
| `--proxy` / `--no-proxy` | 强制走代理，或强制直连 |
| `--dry-run` | 只打印将要下载的内容 |
| `--post-delay` | 每条帖子之间的间隔秒数（默认 `1`） |

完整参数见 `python ins_downloader.py --help`。

## 登录信息与环境变量

公开账号无需登录即可下载。登录可以缓解 Instagram 对匿名请求的限流，下载私密账号
（需已关注）时则必须登录。

三种登录方式，优先级从高到低：

1. `--login USER` 加密码：
   - 密码可以来自 `--password`、环境变量 `INS_PASSWORD`，或运行时交互输入。
   - 登录后会缓存登录态，之后无需重复输入密码
     （默认 `~/.instaloader/session-USER`，可用 `--session-file` 指定路径）。
2. `--cookies-from-browser chrome`（也支持 `edge`、`firefox`、`brave` 等）复用浏览器里
   已登录的 Cookie，需要先 `pip install browser-cookie3`。
3. 脚本同目录下的本地 `.env` 文件。

支持的环境变量：

| 变量 | 作用 |
| --- | --- |
| `INS_USERNAME` | `--login` 的默认值 |
| `INS_PASSWORD` | 未提供 `--password` 时 `--login` 使用的密码 |
| `HTTP_PROXY`、`HTTPS_PROXY`、`ALL_PROXY` | 所有请求使用的代理 |

已经存在的系统环境变量优先于 `.env` 中的同名配置。

配置步骤：

```bash
cp .env.example .env
# 然后编辑 .env，填入你自己的值
```

> 真实凭据不会进入仓库。`.env`、Cookie 和登录态文件都在 `.gitignore` 里。
> 请不要提交它们，也不要把真实 Cookie 贴到 issue 里。

## 输出结果

默认写入当前目录下的 `downloads/`，每个账号一个子目录：

```text
downloads/
└── namoridane/
    ├── 2025-09-22_09-00-03_DO4jShFklJW.jpg       # 帖子的第 1 张图
    ├── 2025-09-22_09-00-03_DO4jShFklJW_1.jpg     # 多图帖的第 2 张
    ├── 2025-09-22_09-00-03_DO4jShFklJW.txt       # 文案
    ├── 2025-09-22_09-00-03_DO4jShFklJW.json      # 完整元数据
    ├── _index.csv                                # 每条帖子一行
    └── _resume_posts.json                        # 断点续传用的游标
```

输出目录可以用 `-o` 改到别处。文件名格式为
`{date_local:%Y-%m-%d_%H-%M-%S}_{shortcode}`，可用 `--filename-pattern` 自定义。

`_index.csv` 的列：`shortcode`、`date_local`、`date_utc`、`type`、`media_count`、
`likes`、`comments`、`local_file`、`url`、`caption`。

## 断点续传与退出码

如果本次运行被打断（比如网络故障或 Instagram 限流），重新执行同一条命令即可。
已完成的文件会跳过，`_resume_posts.json` 里的断点会告诉工具从哪里接着走。

| 退出码 | 含义 |
| --- | --- |
| `0` | 全部处理完成且每条都下载成功 |
| `1` | 账号不存在，或需要登录但没有登录 |
| `2` | 部分完成：有帖子下载失败，或迭代没走到末尾 |
| `3` | 连续 `--stall-timeout` 秒无进展，已保存断点 |

## 连通性自检

`check_connection.py` 只发一次只读请求，打印账号统计信息和最近几条帖子，不下载任何文件，
适合在正式下载前快速排查网络、代理或登录问题。

```bash
python check_connection.py namoridane
python check_connection.py namoridane --proxy http://127.0.0.1:7890
```

## 使用须知

本工具只读取账号主公开的内容。请用于个人归档或已获授权的用途，遵守 Instagram 的服务条款
以及原作者的著作权，未经许可不要转载下载到的素材。
