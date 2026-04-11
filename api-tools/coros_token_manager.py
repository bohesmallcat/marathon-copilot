#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["requests"]
# ///
"""
coros_token_manager.py — COROS Token 管理器 (多用户版)

管理 COROS Training Hub 的 accessToken 生命周期:
  - 支持多用户 token 管理（通过 --user 参数切换）
  - 邮箱/密码自动登录获取 token
  - 本地文件缓存 token（避免频繁登录）
  - 自动检测 token 过期并刷新
  - 供其他脚本调用的 Python API

Token 存储位置: ~/.config/marathon-copilot/coros_tokens.json
凭据来源: api-tools/.env (COROS_TOKEN_<USER>, COROS_EMAIL_<USER>, ...)

Multi-user .env 配置:
  COROS_DEFAULT_USER=runner_a
  COROS_TOKEN_RUNNER_A=<token>
  COROS_REGION_RUNNER_A=cn
  COROS_TOKEN_RUNNER_B=<token>
  COROS_REGION_RUNNER_B=cn

Usage:
  # 查看所有用户 token 状态
  python coros_token_manager.py status

  # 查看指定用户 token 状态
  python coros_token_manager.py --user runner_a status

  # 用邮箱密码登录并缓存 token
  python coros_token_manager.py --user runner_a login --email <EMAIL> --password <PWD>

  # 用浏览器 token 手动设置
  python coros_token_manager.py --user runner_a set --token <TOKEN>

  # 获取有效 token（自动刷新）
  python coros_token_manager.py --user runner_a get

  # 验证 token 是否有效
  python coros_token_manager.py --user runner_a validate

  # 列出所有已配置的用户
  python coros_token_manager.py list

  # 清除指定用户缓存
  python coros_token_manager.py --user runner_a clear
"""

from __future__ import annotations

import argparse
import json
import os
import re
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
TOKEN_CACHE_FILE = TOKEN_CACHE_DIR / "coros_tokens.json"
# Legacy single-user cache (for migration)
LEGACY_CACHE_FILE = TOKEN_CACHE_DIR / "coros_token.json"

# Token validity: COROS tokens typically last ~30 days
# We'll validate every 24 hours and refresh if needed
TOKEN_CHECK_INTERVAL_HOURS = 24

CN_BASE = "https://teamcnapi.coros.com"
INTL_BASE = "https://teamapi.coros.com"


# ── .env Loader ────────────────────────────────────────────────────

def load_env() -> dict:
    """Load credentials from .env file."""
    env_path = SCRIPT_DIR / ".env"
    env_vars = {}
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env_vars[k.strip()] = v.strip()
    return env_vars


def get_env_for_user(user: str | None) -> dict:
    """Get COROS credentials for a specific user from .env.

    Looks up COROS_TOKEN_{USER}, COROS_EMAIL_{USER}, etc.
    Falls back to legacy COROS_TOKEN, COROS_EMAIL if user is None.

    Returns:
        Dict with keys: token, email, password, region.
    """
    env = load_env()
    suffix = f"_{user.upper()}" if user else ""

    token = (env.get(f"COROS_TOKEN{suffix}")
             or os.environ.get(f"COROS_TOKEN{suffix}"))
    email = (env.get(f"COROS_EMAIL{suffix}")
             or os.environ.get(f"COROS_EMAIL{suffix}"))
    password = (env.get(f"COROS_PASSWORD{suffix}")
                or os.environ.get(f"COROS_PASSWORD{suffix}"))
    region = (env.get(f"COROS_REGION{suffix}")
              or os.environ.get(f"COROS_REGION{suffix}")
              or env.get("COROS_REGION")
              or "cn")

    # If user-specific lookup failed, try legacy (no suffix) as fallback
    if user and not token and not email:
        token = token or env.get("COROS_TOKEN") or os.environ.get("COROS_TOKEN")
        email = email or env.get("COROS_EMAIL") or os.environ.get("COROS_EMAIL")
        password = password or env.get("COROS_PASSWORD") or os.environ.get("COROS_PASSWORD")

    return {"token": token, "email": email, "password": password, "region": region}


def get_default_user() -> str | None:
    """Get default user from .env or environment."""
    env = load_env()
    return (env.get("COROS_DEFAULT_USER")
            or os.environ.get("COROS_DEFAULT_USER")
            or None)


def list_configured_users() -> list[str]:
    """Discover all user IDs configured in .env.

    Scans for COROS_TOKEN_<USER> patterns.
    """
    env = load_env()
    users = set()
    pattern = re.compile(r"^COROS_TOKEN_(\w+)$")
    for key in env:
        m = pattern.match(key)
        if m:
            users.add(m.group(1).lower())
    # Also check environment variables
    for key in os.environ:
        m = pattern.match(key)
        if m:
            users.add(m.group(1).lower())
    return sorted(users)


def resolve_user(user_arg: str | None) -> str | None:
    """Resolve the effective user ID.

    Priority: --user arg > COROS_DEFAULT_USER > None (legacy single-user).
    """
    if user_arg:
        return user_arg.lower()
    return get_default_user()


# ── Token Cache (Multi-user) ──────────────────────────────────────

def _read_raw_cache() -> dict:
    """Read the raw cache file."""
    if TOKEN_CACHE_FILE.exists():
        try:
            return json.loads(TOKEN_CACHE_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {"users": {}}


def _migrate_legacy_cache() -> None:
    """Migrate legacy single-user cache to multi-user format."""
    if not LEGACY_CACHE_FILE.exists():
        return
    if TOKEN_CACHE_FILE.exists():
        return  # Already migrated

    try:
        legacy = json.loads(LEGACY_CACHE_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return

    if legacy.get("access_token"):
        default_user = get_default_user() or "default"
        new_cache = {
            "users": {
                default_user: legacy,
            },
        }
        _write_raw_cache(new_cache)


def _write_raw_cache(data: dict) -> None:
    """Write the raw cache file."""
    TOKEN_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    TOKEN_CACHE_FILE.write_text(json.dumps(data, indent=2))
    try:
        TOKEN_CACHE_FILE.chmod(0o600)
    except OSError:
        pass


def read_cache(user: str | None = None) -> dict:
    """Read cached token data for a specific user."""
    _migrate_legacy_cache()
    raw = _read_raw_cache()

    if user:
        return raw.get("users", {}).get(user, {})

    # Legacy compatibility: if "users" key exists, return default user's data
    default = get_default_user()
    if default:
        return raw.get("users", {}).get(default, {})

    # Fallback: check for legacy flat format
    if "access_token" in raw:
        return raw
    return {}


def write_cache(data: dict, user: str | None = None) -> None:
    """Write token data to cache for a specific user."""
    _migrate_legacy_cache()
    raw = _read_raw_cache()
    if "users" not in raw:
        raw = {"users": {}}

    key = user or get_default_user() or "default"
    raw["users"][key] = data
    _write_raw_cache(raw)


def clear_cache(user: str | None = None) -> None:
    """Remove cached token for a specific user (or all if user is None)."""
    if not user:
        if TOKEN_CACHE_FILE.exists():
            TOKEN_CACHE_FILE.unlink()
        return

    raw = _read_raw_cache()
    raw.get("users", {}).pop(user, None)
    _write_raw_cache(raw)


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

def get_valid_token(region: str = "cn", user: str | None = None) -> str:
    """Get a valid COROS token for a user, refreshing if necessary.

    Args:
        region: 'cn' or 'intl' (fallback if not in env/cache).
        user: User identifier (e.g. 'runner_a', 'runner_b'). None = default user.

    Resolution order:
      1. Check cache — if valid and recently validated, return it
      2. Check cache — if exists but stale, re-validate via API call
      3. If cache invalid, try .env COROS_TOKEN_{USER}
      4. If .env has COROS_EMAIL_{USER}, try auto-login
      5. Fall back to legacy single-user config
      6. Raise RuntimeError if nothing works

    Returns:
        Valid COROS accessToken string.

    Raises:
        RuntimeError: No valid token could be obtained.
    """
    effective_user = resolve_user(user)
    cache = read_cache(effective_user)

    # Try cached token
    if cache.get("access_token"):
        cached_region = cache.get("region", "cn")
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
            write_cache(cache, effective_user)
            return cache["access_token"]

    # Try .env credentials for this user
    user_env = get_env_for_user(effective_user)
    target_region = user_env["region"] or region

    # Check for static token
    if user_env["token"]:
        if validate_token(user_env["token"], target_region):
            write_cache({
                "access_token": user_env["token"],
                "region": target_region,
                "login_time": datetime.now().isoformat(),
                "last_validated": datetime.now().isoformat(),
                "source": "env_token",
            }, effective_user)
            return user_env["token"]

    # Try email/password login
    if user_env["email"] and user_env["password"]:
        try:
            token_data = login_coros(user_env["email"], user_env["password"],
                                    target_region)
            write_cache(token_data, effective_user)
            return token_data["access_token"]
        except Exception as e:
            raise RuntimeError(f"Auto-login failed: {e}") from e

    user_label = f" (user={effective_user})" if effective_user else ""
    raise RuntimeError(
        f"无法获取有效 COROS token{user_label}。\n"
        "请选择以下方式之一:\n"
        f"  1. 在 .env 中设置 COROS_TOKEN_{(effective_user or 'USER').upper()}=<token>\n"
        f"  2. 在 .env 中设置 COROS_EMAIL_{(effective_user or 'USER').upper()} + PASSWORD\n"
        "  3. 运行: python coros_token_manager.py --user <USER> set --token <TOKEN>\n"
        "  4. 运行: python coros_token_manager.py --user <USER> login --email <E> --password <P>"
    )


# ── CLI ────────────────────────────────────────────────────────────

def cmd_status(user: str | None = None):
    """Show token status for a user or all users."""
    if user:
        _print_user_status(user)
    else:
        # Show all users
        users = list_configured_users()
        default = get_default_user()

        # Also check cache for users not in .env
        raw = _read_raw_cache()
        cached_users = set(raw.get("users", {}).keys())
        all_users = sorted(set(u.lower() for u in users) | cached_users)

        if not all_users:
            print("未找到任何用户配置。")
            print(f"请在 .env 中配置 COROS_TOKEN_<USER>=<token>")
            print(f"缓存路径: {TOKEN_CACHE_FILE}")
            return

        print(f"=== COROS 多用户 Token 状态 ===\n")
        for u in all_users:
            tag = " [默认]" if u == default else ""
            print(f"── {u}{tag} ──")
            _print_user_status(u)
            print()

        print(f"缓存路径: {TOKEN_CACHE_FILE}")


def _print_user_status(user: str):
    """Print status for a single user."""
    cache = read_cache(user)
    user_env = get_env_for_user(user)

    if cache.get("access_token"):
        token = cache["access_token"]
        masked = token[:6] + "..." + token[-4:] if len(token) > 10 else "***"
        print(f"  Token: {masked}")
        print(f"  来源: {cache.get('source', 'unknown')}")
        print(f"  区域: {cache.get('region', 'cn')}")
        print(f"  登录时间: {cache.get('login_time', 'N/A')}")
        print(f"  上次验证: {cache.get('last_validated', 'N/A')}")
    else:
        print(f"  Token: 无缓存")
        has_token = bool(user_env.get("token"))
        has_login = bool(user_env.get("email") and user_env.get("password"))
        suffix = user.upper() if user else ""
        print(f"  .env COROS_TOKEN_{suffix}: {'已设置' if has_token else '未设置'}")
        print(f"  .env COROS_EMAIL_{suffix}: {'已设置' if has_login else '未设置'}")


def cmd_list():
    """List all configured users."""
    users = list_configured_users()
    default = get_default_user()

    if not users:
        print("未找到任何用户配置。")
        print("在 .env 中添加 COROS_TOKEN_<USER>=<token> 来配置用户。")
        return

    print("已配置的 COROS 用户:")
    for u in users:
        tag = " [默认]" if u == default else ""
        user_env = get_env_for_user(u)
        auth_type = "token" if user_env["token"] else "email" if user_env["email"] else "无"
        print(f"  {u}{tag}  (认证: {auth_type}, 区域: {user_env['region']})")


def cmd_login(user: str | None, email: str, password: str, region: str = "cn"):
    """Login and cache token for a user."""
    effective_user = resolve_user(user)
    print(f"正在登录 COROS (user={effective_user})...", file=sys.stderr)
    token_data = login_coros(email, password, region)
    write_cache(token_data, effective_user)
    print(f"登录成功! Token 已缓存 (user={effective_user})")
    masked = token_data["access_token"][:6] + "..."
    print(f"Token: {masked}")


def cmd_set(user: str | None, token: str, region: str = "cn"):
    """Set token manually for a user."""
    effective_user = resolve_user(user)
    print(f"正在验证 token (user={effective_user})...", file=sys.stderr)
    if validate_token(token, region):
        write_cache({
            "access_token": token,
            "region": region,
            "login_time": datetime.now().isoformat(),
            "last_validated": datetime.now().isoformat(),
            "source": "manual",
        }, effective_user)
        print(f"Token 有效! 已缓存 (user={effective_user})")
    else:
        print("Warning: Token 验证失败，但仍已保存（可能是网络问题）。",
              file=sys.stderr)
        write_cache({
            "access_token": token,
            "region": region,
            "login_time": datetime.now().isoformat(),
            "last_validated": None,
            "source": "manual_unverified",
        }, effective_user)


def cmd_get(user: str | None, region: str = "cn"):
    """Get valid token (stdout, for script consumption)."""
    effective_user = resolve_user(user)
    try:
        token = get_valid_token(region, effective_user)
        print(token)
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)


def cmd_validate(user: str | None, region: str = "cn"):
    """Validate cached token for a user."""
    effective_user = resolve_user(user)
    cache = read_cache(effective_user)
    token = cache.get("access_token")
    if not token:
        print(f"无缓存 token (user={effective_user})。")
        sys.exit(1)
    if validate_token(token, cache.get("region", region)):
        cache["last_validated"] = datetime.now().isoformat()
        write_cache(cache, effective_user)
        print(f"Token 有效! (user={effective_user})")
    else:
        print(f"Token 已过期或无效 (user={effective_user})。")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="COROS Token 管理器 (多用户版)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--user", "-u",
                        help="用户标识 (如 runner_a, runner_b)。不指定则使用默认用户。")
    parser.add_argument("--region", choices=["cn", "intl"], default="cn")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("status", help="查看 token 状态")
    sub.add_parser("list", help="列出所有已配置用户")

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
        cmd_status(args.user)
    elif args.command == "list":
        cmd_list()
    elif args.command == "login":
        cmd_login(args.user, args.email, args.password, args.region)
    elif args.command == "set":
        cmd_set(args.user, args.token, args.region)
    elif args.command == "get":
        cmd_get(args.user, args.region)
    elif args.command == "validate":
        cmd_validate(args.user, args.region)
    elif args.command == "clear":
        effective_user = resolve_user(args.user)
        clear_cache(effective_user)
        label = f"user={effective_user}" if effective_user else "全部"
        print(f"缓存已清除 ({label}): {TOKEN_CACHE_FILE}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
