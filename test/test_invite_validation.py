#!/usr/bin/env python3
"""
测试邀请码验证功能的快速脚本

使用方法:
    python test/test_invite_validation.py
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from datetime import timedelta
from app.core.config import settings
from app.core.db import AsyncSessionLocal
from app.controller.account import validate_invite_code
from app.core.models import InviteCode, format_timezone


async def test_validate_test_invite_code():
    """测试: 使用测试邀请码"""
    print("\n" + "=" * 60)
    print("测试 1: 验证测试邀请码")
    print("=" * 60)

    async with AsyncSessionLocal() as db:
        invite, error = await validate_invite_code(db, settings.test_invite_code)

        print(f"邀请码: {settings.test_invite_code}")
        print(f"验证结果: invite={invite}, error={error}")

        if error == "" and invite == "TEST":
            print("✅ 测试通过: 测试邀请码验证成功")
            return True
        else:
            print("❌ 测试失败: 测试邀请码验证失败")
            return False


async def test_validate_real_invite_code():
    """测试: 使用真实邀请码"""
    print("\n" + "=" * 60)
    print("测试 2: 验证真实邀请码")
    print("=" * 60)

    async with AsyncSessionLocal() as db:
        # 创建一个测试用的真实邀请码
        test_code = "TEST-REAL-CODE-" + format_timezone().strftime("%Y%m%d%H%M%S")
        real_invite = InviteCode(code=test_code)
        db.add(real_invite)
        await db.flush()

        print(f"创建测试邀请码: {test_code}")

        # 验证
        invite, error = await validate_invite_code(db, test_code)

        print(f"验证结果: invite={invite}, error={error}")

        # 清理
        await db.rollback()  # 不保存到数据库

        if error == "" and invite is not None and invite != "TEST":
            print("✅ 测试通过: 真实邀请码验证成功")
            return True
        else:
            print("❌ 测试失败: 真实邀请码验证失败")
            return False


async def test_validate_nonexistent_code():
    """测试: 不存在的邀请码"""
    print("\n" + "=" * 60)
    print("测试 3: 验证不存在的邀请码")
    print("=" * 60)

    async with AsyncSessionLocal() as db:
        fake_code = "NONEXISTENT-CODE-999999"
        invite, error = await validate_invite_code(db, fake_code)

        print(f"邀请码: {fake_code}")
        print(f"验证结果: invite={invite}, error={error}")

        if invite is None and error == "邀请码不存在或已被使用":
            print("✅ 测试通过: 正确识别不存在的邀请码")
            return True
        else:
            print("❌ 测试失败: 未正确识别不存在的邀请码")
            return False


async def test_validate_expired_code():
    """测试: 已过期的邀请码"""
    print("\n" + "=" * 60)
    print("测试 4: 验证已过期的邀请码")
    print("=" * 60)

    async with AsyncSessionLocal() as db:
        # 创建一个已过期的邀请码
        expired_code = "EXPIRED-CODE-" + format_timezone().strftime("%Y%m%d%H%M%S")
        expired_invite = InviteCode(
            code=expired_code,
            expires_at=format_timezone() - timedelta(days=1),  # 昨天过期
        )
        db.add(expired_invite)
        await db.flush()

        print(f"创建过期邀请码: {expired_code}")
        print(f"过期时间: {expired_invite.expires_at}")

        # 验证
        invite, error = await validate_invite_code(db, expired_code)

        print(f"验证结果: invite={invite}, error={error}")

        # 清理
        await db.rollback()

        if invite is None and error == "邀请码已过期":
            print("✅ 测试通过: 正确识别已过期的邀请码")
            return True
        else:
            print("❌ 测试失败: 未正确识别已过期的邀请码")
            return False


async def main():
    """运行所有测试"""
    print("\n" + "🧪" * 30)
    print("开始测试邀请码验证功能")
    print("🧪" * 30)

    print("\n配置信息:")
    print(f"  测试邀请码: {settings.test_invite_code}")
    print(f"  数据库URL: {settings.database_url}")

    results = []

    try:
        # 运行测试
        results.append(await test_validate_test_invite_code())
        results.append(await test_validate_real_invite_code())
        results.append(await test_validate_nonexistent_code())
        results.append(await test_validate_expired_code())

        # 统计结果
        print("\n" + "=" * 60)
        print("测试结果汇总")
        print("=" * 60)

        passed = sum(results)
        total = len(results)

        print(f"通过: {passed}/{total}")
        print(f"失败: {total - passed}/{total}")

        if passed == total:
            print("\n🎉 所有测试通过!")
            return 0
        else:
            print(f"\n⚠️  有 {total - passed} 个测试失败")
            return 1

    except Exception as e:
        print(f"\n❌ 测试过程中出现错误: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
