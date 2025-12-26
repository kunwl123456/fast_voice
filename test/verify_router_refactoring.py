"""
简单验证路由重构 - 只检查 routers.py 的导出

不需要环境配置，直接验证路由器定义
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_routers_module():
    """测试 routers.py 模块的完整性"""
    print("=" * 70)
    print("[*] 路由模块验证测试")
    print("=" * 70)

    try:
        # 导入 routers 模块
        from app import routers

        # 检查所有应该导出的路由器
        expected_routers = [
            # Console 路由
            "account_router",
            "api_keys_router",
            "console_router",
            "credits_router",
            "subscription_router",
            "clone_console_router",
            "tts_console_router",
            "voices_console_router",
            # OpenAPI 路由
            "clone_openapi_router",
            "tts_openapi_router",
            "voices_openapi_router",
            # Admin 路由
            "admin_credit_router",
            "admin_invite_codes_router",
            # 文档路由
            "docs_router",
        ]

        print("\n[*] 检查路由器导出...")
        missing = []
        for router_name in expected_routers:
            if hasattr(routers, router_name):
                router = getattr(routers, router_name)
                prefix = router.prefix if hasattr(router, "prefix") else "无前缀"
                tags = router.tags if hasattr(router, "tags") else []
                print(f"  [OK] {router_name:30s} prefix={prefix:20s} tags={tags}")
            else:
                print(f"  [FAIL] {router_name:30s} - 未找到")
                missing.append(router_name)

        if missing:
            print(f"\n[ERROR] 缺少 {len(missing)} 个路由器: {', '.join(missing)}")
            return False

        # 检查 __all__ 导出列表
        print("\n[*] 检查 __all__ 导出列表...")
        if hasattr(routers, "__all__"):
            exported = set(routers.__all__)
            expected = set(expected_routers)

            if exported == expected:
                print(f"  [OK] __all__ 完整导出 {len(exported)} 个路由器")
            else:
                missing_in_all = expected - exported
                extra_in_all = exported - expected
                if missing_in_all:
                    print(f"  [WARN] __all__ 缺少: {missing_in_all}")
                if extra_in_all:
                    print(f"  [WARN] __all__ 多余: {extra_in_all}")
        else:
            print("  [WARN] 未定义 __all__ 导出列表")

        # 统计信息
        print("\n" + "=" * 70)
        print(f"[OK] 验证通过！共 {len(expected_routers)} 个路由器全部正确导出")
        print("=" * 70)

        # 详细分类统计
        print("\n[INFO] 路由器分类统计:")
        print(
            "  - Console 路由:  8 个 (账户、API Key、控制台、积分、订阅、克隆、TTS、声音)"
        )
        print("  - OpenAPI 路由:  3 个 (克隆、TTS、声音)")
        print("  - Admin 路由:    2 个 (积分、邀请码)")
        print("  - 文档路由:      1 个 (docs)")
        print(f"  - 总计:         {len(expected_routers)} 个")

        return True

    except Exception as e:
        print("\n" + "=" * 70)
        print(f"[ERROR] 验证失败: {e}")
        print("=" * 70)
        import traceback

        traceback.print_exc()
        return False


def test_import_paths():
    """测试各个 views 文件的导入路径是否正确"""
    print("\n" + "=" * 70)
    print("[*] 检查 views 文件的导入路径")
    print("=" * 70)

    views_files = {
        "app/api/views/account.py": "from app.routers import account_router as router",
        "app/api/views/api_keys.py": "from app.routers import api_keys_router as router",
        "app/api/views/console.py": "from app.routers import console_router as router",
        "app/api/views/credits.py": "from app.routers import credits_router as router",
        "app/api/views/subscription.py": "from app.routers import subscription_router as router",
        "app/api/views/clone.py": [
            "from app.routers import clone_console_router as console_router",
            "from app.routers import clone_openapi_router as openapi_router",
        ],
        "app/api/views/tts.py": [
            "from app.routers import tts_console_router as console_router",
            "from app.routers import tts_openapi_router as openapi_router",
        ],
        "app/api/views/voices.py": [
            "from app.routers import voices_console_router as console_router",
            "from app.routers import voices_openapi_router as openapi_router",
        ],
        "app/api/views/docs.py": "from app.routers import docs_router as router",
        "app/admin/views/credits.py": "from app.routers import admin_credit_router as router",
        "app/admin/views/invite_codes.py": "from app.routers import admin_invite_codes_router as router",
    }

    project_root = Path(__file__).parent.parent
    all_correct = True

    for file_path, expected_imports in views_files.items():
        full_path = project_root / file_path
        if not full_path.exists():
            print(f"  [WARN] 文件不存在: {file_path}")
            continue

        content = full_path.read_text(encoding="utf-8")

        # 转换为列表以统一处理
        if isinstance(expected_imports, str):
            expected_imports = [expected_imports]

        # 检查每个导入语句
        file_ok = True
        for expected_import in expected_imports:
            if expected_import in content:
                pass  # 正确
            else:
                if file_ok:  # 第一次发现错误时打印文件名
                    print(f"  [FAIL] {file_path}")
                print(f"         缺少导入: {expected_import}")
                file_ok = False
                all_correct = False

        if file_ok:
            print(f"  [OK] {file_path}")

    return all_correct


def main():
    success = True

    # 测试 routers 模块
    if not test_routers_module():
        success = False

    # 测试导入路径
    if not test_import_paths():
        success = False

    if success:
        print("\n" + "=" * 70)
        print("[SUCCESS] 所有验证通过！路由重构成功！")
        print("=" * 70)
        return 0
    else:
        print("\n" + "=" * 70)
        print("[FAILED] 部分验证未通过，请检查上述错误")
        print("=" * 70)
        return 1


if __name__ == "__main__":
    sys.exit(main())
