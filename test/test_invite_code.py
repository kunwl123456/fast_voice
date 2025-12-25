"""邀请码系统测试脚本

使用说明：
1. 确保服务正在运行
2. 修改下面的配置（BASE_URL、ADMIN_EMAIL、ADMIN_PASSWORD）
3. 运行此脚本: python test_invite_code.py
"""

import requests
import json

# 配置
BASE_URL = "http://localhost:8000"
ADMIN_EMAIL = "admin@autogame.com"  # 修改为你的管理员邮箱
ADMIN_PASSWORD = "admin123"  # 修改为你的管理员密码


def print_section(title):
    """打印分隔线"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_result(response, success_msg, error_msg):
    """打印请求结果"""
    if response.status_code in [200, 201]:
        print(f"✅ {success_msg}")
        if response.json():
            print(json.dumps(response.json(), indent=2, ensure_ascii=False))
    else:
        print(f"❌ {error_msg}")
        print(f"状态码: {response.status_code}")
        print(f"响应: {response.text}")
    return response


def main():
    print_section("邀请码系统测试")

    # 1. 管理员登录
    print_section("1. 管理员登录")
    login_response = requests.post(
        f"{BASE_URL}/console/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    print_result(login_response, "管理员登录成功", "管理员登录失败")

    if login_response.status_code != 200:
        print("\n⚠️ 请检查管理员账号和密码是否正确")
        return

    admin_token = login_response.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 2. 生成邀请码（3个永久有效）
    print_section("2. 生成邀请码（3个永久有效）")
    create_codes_response = requests.post(
        f"{BASE_URL}/console/invite-codes/",
        json={"count": 3, "note": "测试邀请码"},
        headers=headers,
    )
    print_result(create_codes_response, "邀请码生成成功", "邀请码生成失败")

    if create_codes_response.status_code != 201:
        return

    invite_codes = create_codes_response.json()["data"]["codes"]
    test_code = invite_codes[0] if invite_codes else None

    # 3. 获取邀请码列表
    print_section("3. 获取所有邀请码")
    list_codes_response = requests.get(
        f"{BASE_URL}/console/invite-codes/", headers=headers
    )
    print_result(list_codes_response, "获取邀请码列表成功", "获取邀请码列表失败")

    # 4. 获取未使用的邀请码
    print_section("4. 获取未使用的邀请码")
    unused_codes_response = requests.get(
        f"{BASE_URL}/console/invite-codes/?only_unused=true", headers=headers
    )
    print_result(unused_codes_response, "获取未使用邀请码成功", "获取未使用邀请码失败")

    # 5. 使用邀请码注册新用户
    if test_code:
        print_section("5. 使用邀请码注册新用户")
        register_response = requests.post(
            f"{BASE_URL}/console/auth/register",
            json={
                "email": "testuser@example.com",
                "password": "test123456",
                "display_name": "测试用户",
                "invite_code": test_code,
            },
        )
        print_result(register_response, "用户注册成功", "用户注册失败")

        # 6. 尝试重复使用同一个邀请码（应该失败）
        print_section("6. 尝试重复使用同一个邀请码（预期失败）")
        duplicate_register_response = requests.post(
            f"{BASE_URL}/console/auth/register",
            json={
                "email": "testuser2@example.com",
                "password": "test123456",
                "display_name": "测试用户2",
                "invite_code": test_code,
            },
        )
        if duplicate_register_response.status_code == 409:
            print("✅ 正确拒绝了重复使用的邀请码")
            print(
                json.dumps(
                    duplicate_register_response.json(), indent=2, ensure_ascii=False
                )
            )
        else:
            print("❌ 未能正确拒绝重复使用的邀请码")
            print(f"状态码: {duplicate_register_response.status_code}")

        # 7. 再次查看邀请码列表（检查使用状态）
        print_section("7. 查看邀请码使用状态")
        final_list_response = requests.get(
            f"{BASE_URL}/console/invite-codes/", headers=headers
        )
        print_result(
            final_list_response, "获取最终邀请码列表成功", "获取最终邀请码列表失败"
        )

    # 8. 生成带过期时间的邀请码
    print_section("8. 生成 7 天有效期的邀请码")
    expire_codes_response = requests.post(
        f"{BASE_URL}/console/invite-codes/",
        json={"count": 2, "expires_days": 7, "note": "7天有效期测试"},
        headers=headers,
    )
    print_result(expire_codes_response, "有效期邀请码生成成功", "有效期邀请码生成失败")

    print_section("测试完成")
    print("所有测试已完成！请检查上面的结果。")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ 测试过程中发生错误: {e}")
        import traceback

        traceback.print_exc()
