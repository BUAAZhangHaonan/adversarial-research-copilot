"""arc-arena 管理员 CLI：用户管理。

用法：
  python manage.py adduser <name> [--admin]     # 交互式输入密码
  python manage.py passwd <name>
  python manage.py deactivate <name>
  python manage.py activate <name>
  python manage.py list
"""
from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from arc_arena.auth import AuthError, AuthManager  # noqa: E402
from arc_arena.config import load_config  # noqa: E402
from arc_arena.db import init_db  # noqa: E402


def _ask_password() -> str:
    first = getpass.getpass("密码（>=6 位）: ")
    if len(first) < 6:
        print("密码至少 6 位")
        sys.exit(1)
    second = getpass.getpass("再输一遍: ")
    if first != second:
        print("两次输入不一致")
        sys.exit(1)
    return first


def main() -> None:
    parser = argparse.ArgumentParser(description="arc-arena 用户管理")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("adduser", help="创建用户")
    p_add.add_argument("username")
    p_add.add_argument("--admin", action="store_true")

    p_pw = sub.add_parser("passwd", help="重置密码")
    p_pw.add_argument("username")

    p_off = sub.add_parser("deactivate", help="停用用户")
    p_off.add_argument("username")

    p_on = sub.add_parser("activate", help="启用用户")
    p_on.add_argument("username")

    sub.add_parser("list", help="列出用户")

    args = parser.parse_args()

    cfg = load_config()
    init_db(cfg.db_path)
    auth = AuthManager(cfg.db_path, session_days=cfg.session_days)

    try:
        if args.cmd == "adduser":
            user = auth.create_user(args.username, _ask_password(), is_admin=args.admin)
            print(f"created: {user.username} (admin={user.is_admin})")
        elif args.cmd == "passwd":
            auth.set_password(args.username, _ask_password())
            print(f"password updated: {args.username}（其所有会话已注销）")
        elif args.cmd == "deactivate":
            auth.set_active(args.username, False)
            print(f"deactivated: {args.username}")
        elif args.cmd == "activate":
            auth.set_active(args.username, True)
            print(f"activated: {args.username}")
        elif args.cmd == "list":
            for u in auth.list_users():
                flag = "admin" if u["is_admin"] else "     "
                state = "" if u["active"] else " [已停用]"
                print(f"{flag}  {u['username']}{state}  (created {u['created_at'][:10]})")
    except AuthError as exc:
        print(f"error: {exc.message}")
        sys.exit(1)


if __name__ == "__main__":
    main()
