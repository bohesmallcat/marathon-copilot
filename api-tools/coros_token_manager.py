#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["requests"]
# ///
"""
coros_token_manager.py — COROS Token 管理器

管理 COROS Training Hub 的 accessToken 生命周期:
  - 邮箱/密码自动登录获取 token
  - 本地文件缓存 token（避免频繁登录）
  - 自动检测 token 过期并刷新
  - 供其他脚本调用的 Python API

Token 存储位置: ~/.config/marathon-copilot/coros_token.json
凭据来源: PB/api-tools/.env (COROS_EMAIL, COROS_PASSWORD)

Usage:
  # 查看当前 token 状态
  python coros_token_manager.py status

  # 用邮箱密码登录并缓存 token
  python coros_token_manager.py login --email <EMAIL> --password <PWD>

  # 用浏览器 token 手动设置
  python coros_token_manager.py set --token <TOKEN>

  # 获取有效 token（自动刷新）
  python coros_token_manager.py get

  # 验证 token 是否有效
  python coros_token_manager.py validate

  # 清除缓存
  python coros_token_manager.py clear
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent

try:
    import requests
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except ImportError:
    print("requests library required", file=sys.stderr)
    sys.exit(1)

# ── Configuration ──────────────────────────────────────────────────

TOKEN_CACHE_DIR = Path.home() / ".config" / "marathon-copilot"
TOKEN_CACHE_FILE = TOKEN_CACHE_DIR / "coros_token.json"

# Token validity: COROS tokens typically last ~30 days
# We'll validate every 24 hours and refresh if needed
TOKEN_CHECK_INTERVAL_HOURS = 24

CN_BASE = "https://teamcnapi.coros.com"
INTL_BASE = "https://teamapi.coros.com"


# ── .env Loader ────────────────────────────────────────────────────

def load_env() -> dict:
    """Load COROS credentials from .env file."""
    env_path = SCRIPT_DIR / ".env"
    env_vars = {}
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env_vars[k.strip()] = v.strip()
    return env_vars


# ── Token Cache ────────────────────────────────────────────────────

def read_cache() -> dict:
    """Read cached token data."""
    if TOKEN_CACHE_FILE.exists():
        try:
            return json.loads(TOKEN_CACHE_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def write_cache(data: dict) -> None:
    """Write token data to cache."""
    TOKEN_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    TOKEN_CACHE_FILE.write_text(json.dumps(data, indent=2))
    # Restrict permissions (owner read/write only)
    try:
        TOKEN_CACHE_FILE.chmod(0o600)
    except OSError:
        pass


def clear_cache() -> None:
    """Remove cached token."""
    if TOKEN_CACHE_FILE.exists():
        TOKEN_CACHE_FILE.unlink()


# ── COROS API Auth ─────────────────────────────────────────────────

def login_coros(email: str, password: str, region: str = "cn") -> dict:
    """Login to COROS and return token data.

    Args:
        email: Account email or phone number.
        password: Account password.
        region: 'cn' or 'intl'.

    Returns:
        Dict with accessToken, userId, login timestamp.
    """
    import hashlib
    base = CN_BASE if region == "cn" else INTL_BASE
    resp = requests.post(
        f"{base}/account/login",
        json={
            "account": email,
            "accountType": 2,
            "pwd": hashlib.md5(password.encode()).hexdigest(),
        },
        timeout=30,
        verify=False,
    )
    resp.raise_for_status()
    result = resp.json()
    if result.get("result") != "0000":
        raise RuntimeError(f"Login failed: {result.get('message', result)}")

    data = result["data"]
    return {
        "access_token": data["accessToken"],
        "user_id": data.get("userId"),
        "region": region,
        "login_time": datetime.now().isoformat(),
        "last_validated": datetime.now().isoformat(),
        "source": "email_login",
    }


def validate_token(token: str, region: str = "cn") -> bool:
    """Check if a token is still valid by making a lightweight API call.

    Args:
        token: COROS accessToken.
        region: 'cn' or 'intl'.

    Returns:
        True if token is valid.
    """
    base = CN_BASE if region == "cn" else INTL_BASE
    try:
        resp = requests.get(
            f"{base}/activity/query",
            params={"size": 1, "pageNumber": 1, "modeList": ""},
            headers={"accesstoken": token},
            timeout=15,
            verify=False,
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("result") == "0000"
    except Exception:
        pass
    return False


# ── Public API ─────────────────────────────────────────────────────

def get_valid_token(region: str = "cn") -> str:
    """Get a valid COROS token, refreshing if necessary.

    Resolution order:
      1. Check cache — if valid and recently validated, return it
      2. Check cache — if exists but stale, re-validate via API call
      3. If cache invalid, try login with .env credentials
      4. If .env has COROS_TOKEN, validate and cache it
      5. Raise RuntimeError if nothing works

    Returns:
        Valid COROS accessToken string.

    Raises:
        RuntimeError: No valid token could be obtained.
    """
    cache = read_cache()

    # Try cached token
    if cache.get("access_token"):
        cached_region = cache.get("region", "cn")
        # Check if recently validated
        last_val = cache.get("last_validated")
        if last_val:
            try:
                last_dt = datetime.fromisoformat(last_val)
                if datetime.now() - last_dt < timedelta(hours=TOKEN_CHECK_INTERVAL_HOURS):
                    return cache["access_token"]
            except ValueError:
                pass

        # Re-validate
        if validate_token(cache["access_token"], cached_region):
            cache["last_validated"] = datetime.now().isoformat()
            write_cache(cache)
            return cache["access_token"]

    # Try .env credentials
    env = load_env()

    # Check for static token in .env
    env_token = env.get("COROS_TOKEN") or os.environ.get("COROS_TOKEN")
    if env_token:
        target_region = env.get("COROS_REGION", region)
        if validate_token(env_token, target_region):
            write_cache({
                "access_token": env_token,
                "region": target_region,
                "login_time": datetime.now().isoformat(),
                "last_validated": datetime.now().isoformat(),
                "source": "env_token",
            })
            return env_token

    # Try email/password login
    email = env.get("COROS_EMAIL") or os.environ.get("COROS_EMAIL")
    password = env.get("COROS_PASSWORD") or os.environ.get("COROS_PASSWORD")
    target_region = env.get("COROS_REGION", region) or region

    if email and password:
        try:
            token_data = login_coros(email, password, target_region)
            write_cache(token_data)
            return token_data["access_token"]
        except Exception as e:
            raise RuntimeError(f"Auto-login failed: {e}") from e

    raise RuntimeError(
        "无法获取有效 COROS token。\n"
        "请选择以下方式之一:\n"
        "  1. 在 .env 中设置 COROS_TOKEN=<token>\n"
        "  2. 在 .env 中设置 COROS_EMAIL 和 COROS_PASSWORD\n"
        "  3. 运行: python coros_token_manager.py set --token <TOKEN>\n"
        "  4. 运行: python coros_token_manager.py login --email <E> --password <P>"
    )


# ── CLI ────────────────────────────────────────────────────────────

def cmd_status():
    """Show current token status."""
    cache = read_cache()
    if not cache.get("access_token"):
        print("状态: 无缓存 token")
        print(f"缓存路径: {TOKEN_CACHE_FILE}")

        env = load_env()
        has_token = bool(env.get("COROS_TOKEN") or os.environ.get("COROS_TOKEN"))
        has_login = bool(env.get("COROS_EMAIL") and env.get("COROS_PASSWORD"))
        print(f".env COROS_TOKEN: {'已设置' if has_token else '未设置'}")
        print(f".env COROS_EMAIL+PASSWORD: {'已设置' if has_login else '未设置'}")
        return

    token = cache["access_token"]
    masked = token[:6] + "..." + token[-4:] if len(token) > 10 else "***"
    print(f"Token: {masked}")
    print(f"来源: {cache.get('source', 'unknown')}")
    print(f"区域: {cache.get('region', 'cn')}")
    print(f"登录时间: {cache.get('login_time', 'N/A')}")
    print(f"上次验证: {cache.get('last_validated', 'N/A')}")
    print(f"缓存路径: {TOKEN_CACHE_FILE}")


def cmd_login(email: str, password: str, region: str = "cn"):
    """Login and cache token."""
    print("正在登录 COROS...", file=sys.stderr)
    token_data = login_coros(email, password, region)
    write_cache(token_data)
    print(f"登录成功! Token 已缓存到 {TOKEN_CACHE_FILE}")
    masked = token_data["access_token"][:6] + "..."
    print(f"Token: {masked}")


def cmd_set(token: str, region: str = "cn"):
    """Set token manually."""
    print("正在验证 token...", file=sys.stderr)
    if validate_token(token, region):
        write_cache({
            "access_token": token,
            "region": region,
            "login_time": datetime.now().isoformat(),
            "last_validated": datetime.now().isoformat(),
            "source": "manual",
        })
        print(f"Token 有效! 已缓存到 {TOKEN_CACHE_FILE}")
    else:
        print("Warning: Token 验证失败，但仍已保存（可能是网络问题）。", file=sys.stderr)
        write_cache({
            "access_token": token,
            "region": region,
            "login_time": datetime.now().isoformat(),
            "last_validated": None,
            "source": "manual_unverified",
        })


def cmd_get(region: str = "cn"):
    """Get valid token (stdout, for script consumption)."""
    try:
        token = get_valid_token(region)
        print(token)
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)


def cmd_validate(region: str = "cn"):
    """Validate cached token."""
    cache = read_cache()
    token = cache.get("access_token")
    if not token:
        print("无缓存 token。")
        sys.exit(1)
    if validate_token(token, cache.get("region", region)):
        cache["last_validated"] = datetime.now().isoformat()
        write_cache(cache)
        print("Token 有效!")
    else:
        print("Token 已过期或无效。")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="COROS Token 管理器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--region", choices=["cn", "intl"], default="cn")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("status", help="查看 token 状态")

    login_p = sub.add_parser("login", help="邮箱密码登录")
    login_p.add_argument("--email", required=True)
    login_p.add_argument("--password", required=True)

    set_p = sub.add_parser("set", help="手动设置 token")
    set_p.add_argument("--token", required=True)

    sub.add_parser("get", help="获取有效 token (stdout)")
    sub.add_parser("validate", help="验证当前 token")
    sub.add_parser("clear", help="清除缓存")

    args = parser.parse_args()

    if args.command == "status":
        cmd_status()
    elif args.command == "login":
        cmd_login(args.email, args.password, args.region)
    elif args.command == "set":
        cmd_set(args.token, args.region)
    elif args.command == "get":
        cmd_get(args.region)
    elif args.command == "validate":
        cmd_validate(args.region)
    elif args.command == "clear":
        clear_cache()
        print(f"缓存已清除: {TOKEN_CACHE_FILE}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
