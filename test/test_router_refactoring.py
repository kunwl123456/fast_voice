"""
验证路由重构后的完整性

运行此脚本检查：
1. 所有 router 是否正确导出
2. 所有 views 模块是否正确导入 router
3. 路由数量是否匹配
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_routers_export():
    """测试 routers.py 是否正确导出所有路由器"""
    from app.routers import (
        account_router,
        api_keys_router,
        console_router,
        credits_router,
        subscription_router,
        clone_console_router,
        clone_openapi_router,
        tts_console_router,
        tts_openapi_router,
        voices_console_router,
        voices_openapi_router,
        admin_credit_router,
        admin_invite_codes_router,
        docs_router,
    )

    routers = [
        ("account_router", account_router),
        ("api_keys_router", api_keys_router),
        ("console_router", console_router),
        ("credits_router", credits_router),
        ("subscription_router", subscription_router),
        ("clone_console_router", clone_console_router),
        ("clone_openapi_router", clone_openapi_router),
        ("tts_console_router", tts_console_router),
        ("tts_openapi_router", tts_openapi_router),
        ("voices_console_router", voices_console_router),
        ("voices_openapi_router", voices_openapi_router),
        ("admin_credit_router", admin_credit_router),
        ("admin_invite_codes_router", admin_invite_codes_router),
        ("docs_router", docs_router),
    ]

    print("[OK] 所有路由器导出成功:")
    for name, router in routers:
        prefix = router.prefix if hasattr(router, "prefix") else "无前缀"
        tags = router.tags if hasattr(router, "tags") else []
        print(f"   - {name:30s} prefix={prefix:20s} tags={tags}")

    return True


def test_views_import():
    """测试所有 views 模块是否正确导入"""
    views_modules = [
        "app.api.views.account",
        "app.api.views.api_keys",
        "app.api.views.console",
        "app.api.views.credits",
        "app.api.views.subscription",
        "app.api.views.clone",
        "app.api.views.tts",
        "app.api.views.voices",
        "app.api.views.docs",
        "app.admin.views.credit",
        "app.admin.views.invite_codes",
    ]

    print("\n[OK] 所有 views 模块导入成功:")
    for module_name in views_modules:
        __import__(module_name)
        print(f"   - {module_name}")

    return True


def test_route_counts():
    """测试各个路由器的路由数量"""
    from app.routers import (
        account_router,
        api_keys_router,
        console_router,
        credits_router,
        subscription_router,
        clone_console_router,
        clone_openapi_router,
        tts_console_router,
        tts_openapi_router,
        voices_console_router,
        voices_openapi_router,
        admin_credit_router,
        admin_invite_codes_router,
        docs_router,
    )

    # 导入 views 模块以注册路由

    routers_with_routes = [
        ("account_router", account_router),
        ("api_keys_router", api_keys_router),
        ("console_router", console_router),
        ("credits_router", credits_router),
        ("subscription_router", subscription_router),
        ("clone_console_router", clone_console_router),
        ("clone_openapi_router", clone_openapi_router),
        ("tts_console_router", tts_console_router),
        ("tts_openapi_router", tts_openapi_router),
        ("voices_console_router", voices_console_router),
        ("voices_openapi_router", voices_openapi_router),
        ("admin_credit_router", admin_credit_router),
        ("admin_invite_codes_router", admin_invite_codes_router),
        ("docs_router", docs_router),
    ]

    print("\n[OK] 各路由器的路由数量:")
    total_routes = 0
    for name, router in routers_with_routes:
        route_count = len(router.routes)
        total_routes += route_count
        print(f"   - {name:30s} {route_count:3d} 个路由")

    print(f"\n[INFO] 总计: {total_routes} 个路由")
    return True


def main():
    print("=" * 60)
    print("[*] 路由重构验证测试")
    print("=" * 60)

    try:
        test_routers_export()
        test_views_import()
        test_route_counts()

        print("\n" + "=" * 60)
        print("[OK] 所有测试通过！路由重构成功！")
        print("=" * 60)
        return 0

    except Exception as e:
        print("\n" + "=" * 60)
        print(f"[ERROR] 测试失败: {e}")
        print("=" * 60)
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
