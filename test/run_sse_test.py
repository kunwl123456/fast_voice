#!/usr/bin/env python
"""
快速运行 SSE 测试脚本
无需 pytest，可直接运行

环境变量支持：
- TEST_EMAIL: 测试账号邮箱
- TEST_PASSWORD: 测试账号密码
- TEST_TOKEN: Bearer Token（优先级高于邮箱密码）
- TEST_CLONE_JOB_ID: 克隆任务 UUID（必需）
- API_URL: API 地址（默认 http://localhost:8000）
"""
import asyncio
import json
import os
import time
import sys

try:
    import httpx
except ImportError:
    print("❌ 缺少依赖: httpx")
    print("请运行: pip install httpx")
    sys.exit(1)


def generate_long_text(max_utf8_bytes: int = 3800) -> str:
    """
    生成长文本，但不超过 UTF-8 字节限制
    
    Args:
        max_utf8_bytes: 最大 UTF-8 字节数（默认 3800，留一些余量）
    
    Returns:
        生成的文本（字符数和字节数）
    """
    base_text = """
这是一段用于测试TTS系统的长文本。人工智能技术的发展日新月异，
特别是在自然语言处理和语音合成领域，已经取得了令人瞩目的成就。
文本转语音技术可以将文字内容转换为自然流畅的语音，广泛应用于
有声读物、语音助手、无障碍阅读等多个场景。随着深度学习技术的
进步，现代TTS系统已经能够生成非常接近真人发音的高质量语音，
并且支持多种情感和语调的控制。在实际应用中，高质量的语音合成
不仅要求发音准确，还需要具备自然的韵律和情感表达能力。
深度学习模型通过大量的训练数据学习人类语音的特征和规律，
能够准确地模拟各种发音方式和语音风格。这项技术的应用前景
非常广阔，未来将会在更多领域发挥重要作用。
    """
    
    result = ""
    
    # 不断追加文本，直到接近字节限制
    while True:
        test_text = result + base_text
        utf8_bytes = len(test_text.encode('utf-8'))
        
        if utf8_bytes > max_utf8_bytes:
            # 超过限制，停止追加
            break
        
        result = test_text
    
    # 精确裁剪到字节限制
    while len(result.encode('utf-8')) > max_utf8_bytes:
        result = result[:-1]
    
    return result


async def login_and_get_token(base_url: str, email: str, password: str) -> str:
    """登录并获取 token"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{base_url}/console/auth/login",
            json={"email": email, "password": password},
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code != 200:
            raise Exception(f"登录失败: HTTP {response.status_code}, 响应: {response.text}")
        
        result = response.json()
        
        # 兼容两种响应格式
        if "code" in result and result["code"] != 0:
            raise Exception(f"登录失败: {result.get('msg') or result.get('message')}")
        
        # 检查是否有 data 和 access_token
        if "data" not in result or "access_token" not in result["data"]:
            raise Exception(f"登录响应格式错误: {result}")
        
        return result["data"]["access_token"]


async def test_sse_tts(base_url: str = "http://localhost:8000", clone_job_id: str = None, 
                       token: str = None, email: str = None, password: str = None):
    """测试 SSE TTS 功能"""
    
    print("=" * 70)
    print("🎤 TTS SSE 功能测试 - 长文本（接近 4000 字节限制）")
    print("=" * 70)
    
    # 如果没有 token，尝试登录
    if not token and email and password:
        print(f"\n🔐 正在登录 ({email})...")
        try:
            token = await login_and_get_token(base_url, email, password)
            print("✅ 登录成功")
        except Exception as e:
            print(f"❌ 登录失败: {e}")
            return False
    
    # 生成测试文本（接近但不超过系统限制）
    text = generate_long_text(max_utf8_bytes=3800)  # 留 200 字节余量
    utf8_bytes = len(text.encode('utf-8'))
    char_count = len(text)
    
    print(f"\n📝 生成测试文本:")
    print(f"   - 字符数: {char_count}")
    print(f"   - UTF-8 字节: {utf8_bytes}")
    print(f"   - 系统限制: 4000 字节")
    
    headers = {
        "Content-Type": "application/json",
    }
    
    # 如果有 token，添加到 headers
    if token:
        headers["Authorization"] = f"Bearer {token}"
        print(f"🔑 使用认证 token")
    else:
        print(f"⚠️  未提供认证信息，可能会失败")
    
    async with httpx.AsyncClient(timeout=300.0) as client:
        # 1. 创建任务
        print(f"\n🚀 步骤 1: 创建 TTS 任务...")
        print(f"   - API: {base_url}/console/tts/jobs")
        print(f"   - Clone Job ID: {clone_job_id}")
        
        start_time = time.time()
        
        try:
            create_response = await client.post(
                f"{base_url}/console/tts/jobs",
                json={
                    "clone_job_id": clone_job_id,
                    "text": text,
                },
                headers=headers,
            )
            
            if create_response.status_code != 200:
                print(f"❌ 创建任务失败: HTTP {create_response.status_code}")
                print(f"   响应: {create_response.text}")
                return False
            
            result = create_response.json()
            
            # 兼容两种响应格式
            # 格式1: {"code": 0, "msg": "...", "data": {...}}
            # 格式2: {"message": "...", "data": {...}}
            
            # 检查是否有错误（格式1）
            if "code" in result and result["code"] != 0:
                print(f"❌ 创建任务失败: {result.get('msg') or result.get('message')}")
                print(f"   完整响应: {result}")
                return False
            
            # 检查 data 字段
            if "data" not in result or not result["data"]:
                print(f"❌ 响应缺少 data 字段")
                print(f"   完整响应: {result}")
                return False
            
            if "id" not in result["data"]:
                print(f"❌ data 中缺少 id 字段")
                print(f"   完整响应: {result}")
                return False
            
            job_id = result["data"]["id"]
            print(f"✅ 任务创建成功")
            print(f"   - 任务 ID: {job_id}")
            print(f"   - 状态: {result['data'].get('status', 'unknown')}")
            print(f"   - 创建耗时: {time.time() - start_time:.2f} 秒")
            
        except KeyError as e:
            print(f"❌ 响应格式错误，缺少字段: {e}")
            print(f"   响应内容: {create_response.text if 'create_response' in locals() else 'N/A'}")
            return False
        except Exception as e:
            print(f"❌ 创建任务异常: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        # 2. SSE 监听
        print(f"\n📡 步骤 2: 使用 SSE 监听任务状态...")
        print(f"   - SSE URL: {base_url}/console/tts/jobs/{job_id}/events")
        
        statuses = []
        final_data = None
        event_count = 0
        
        try:
            # 使用 GET 请求建立 SSE 连接
            async with client.stream(
                "GET",
                f"{base_url}/console/tts/jobs/{job_id}/events",
                headers=headers,
                timeout=httpx.Timeout(300.0, connect=10.0, read=None),  # 允许无限读取时间
            ) as response:
                if response.status_code != 200:
                    print(f"❌ SSE 连接失败: HTTP {response.status_code}")
                    return False
                
                print("✅ SSE 连接成功，开始接收事件...\n")
                
                current_event = None
                async for line_bytes in response.aiter_lines():
                    line = line_bytes.strip()
                    
                    if not line:
                        continue
                    
                    if line.startswith('event:'):
                        current_event = line[6:].strip()
                    elif line.startswith('data:'):
                        data_str = line[5:].strip()
                        try:
                            data = json.loads(data_str)
                            event_count += 1
                            elapsed = time.time() - start_time
                            
                            # 状态更新
                            if current_event == 'status':
                                status = data.get('status')
                                statuses.append(status)
                                
                                # 状态图标
                                icon = {
                                    'queued': '⏳',
                                    'running': '🔄',
                                    'succeeded': '✅',
                                    'failed': '❌'
                                }.get(status, '📊')
                                
                                print(f"   [{elapsed:6.1f}s] {icon} 状态: {status}")
                            
                            # 任务完成
                            elif current_event == 'complete':
                                final_status = data.get('status')
                                final_data = data.get('data', {})
                                
                                print(f"\n{'=' * 70}")
                                if final_status == 'succeeded':
                                    print(f"🎉 任务完成成功！")
                                    print(f"   - 总耗时: {elapsed:.2f} 秒")
                                    print(f"   - 音频 URL: {final_data.get('output_audio_url')}")
                                    print(f"   - 消耗积分: {final_data.get('cost_credits')}")
                                    print(f"   - 文本字节: {final_data.get('text_utf8_bytes')}")
                                else:
                                    print(f"❌ 任务失败")
                                    print(f"   - 错误: {final_data.get('error')}")
                                print(f"{'=' * 70}")
                                break
                            
                            # 错误
                            elif current_event == 'error':
                                print(f"\n❌ 错误: {data.get('message')}")
                                break
                            
                            # 超时
                            elif current_event == 'timeout':
                                print(f"\n⏰ 超时: {data.get('elapsed_seconds')} 秒")
                                break
                        
                        except json.JSONDecodeError as e:
                            print(f"   ⚠️  JSON 解析失败: {e}")
                
        except Exception as e:
            print(f"❌ SSE 连接异常: {e}")
            return False
        
        # 3. 结果统计
        print(f"\n📊 测试统计:")
        print(f"   - 总耗时: {time.time() - start_time:.2f} 秒")
        print(f"   - 状态流转: {' → '.join(statuses)}")
        print(f"   - 事件数量: {event_count}")
        
        # 验证
        if final_data and final_data.get('status') == 'succeeded':
            print(f"\n✅ 测试通过！3000 字语音生成成功")
            return True
        else:
            print(f"\n❌ 测试失败")
            return False


async def main():
    """主函数"""
    # 从环境变量获取配置
    BASE_URL = os.getenv("API_URL", "http://localhost:8000")
    
    print("\n" + "=" * 70)
    print("🎤 TTS SSE 测试 - 长文本（接近 4000 字节限制）")
    print("=" * 70)
    
    print("\n💡 前置条件:")
    print("   1. 确保服务已启动: docker-compose up -d")
    print("   2. 先创建克隆任务并等待完成: POST /console/clone/jobs")
    print("   3. 需要有测试账号")
    print("   4. 设置环境变量 TEST_CLONE_JOB_ID（克隆任务的 UUID）\n")
    
    # 检查环境变量
    token = os.getenv("TEST_TOKEN")
    email = os.getenv("TEST_EMAIL")
    password = os.getenv("TEST_PASSWORD")
    clone_job_id = os.getenv("TEST_CLONE_JOB_ID")
    
    # 检查或输入 clone_job_id
    if not clone_job_id:
        clone_job_id = input("\n请输入克隆任务 UUID (Clone Job ID): ").strip()
        if not clone_job_id:
            print("❌ Clone Job ID 不能为空")
            print("\n提示: 先创建克隆任务并等待完成:")
            print("  curl -X POST http://localhost:8000/console/clone/jobs \\")
            print("       -H 'Authorization: Bearer YOUR_TOKEN' \\")
            print("       -F 'voice_name=测试音色' \\")
            print("       -F 'files=@audio.wav'")
            sys.exit(1)
    
    if token:
        print("🔑 使用环境变量 TEST_TOKEN")
    elif email and password:
        print(f"🔐 使用环境变量 TEST_EMAIL ({email})")
    else:
        # 交互式输入
        print("\n🔐 认证方式:")
        print("   1. 使用邮箱密码登录（推荐）")
        print("   2. 使用已有的 Bearer Token")
        print("   3. 跳过认证（仅用于测试无认证端点）\n")
        
        choice = input("请选择 [1/2/3，默认1]: ").strip() or "1"
        
        if choice == "1":
            # 邮箱密码登录
            email = input("邮箱 (默认: admin@autogame.ai): ").strip() or "admin@autogame.ai"
            password = input("密码 (默认: 123456): ").strip() or "123456"
        elif choice == "2":
            # 使用 token
            token = input("请输入 Bearer Token: ").strip()
            if not token:
                print("❌ Token 不能为空")
                sys.exit(1)
        elif choice == "3":
            # 跳过认证
            print("⚠️  跳过认证，可能会失败")
        else:
            print("❌ 无效的选择")
            sys.exit(1)
    
    print("\n" + "-" * 70)
    input("按 Enter 开始测试...")
    print()
    
    # 运行测试
    success = await test_sse_tts(
        base_url=BASE_URL,
        clone_job_id=clone_job_id,
        token=token,
        email=email,
        password=password
    )
    
    # 退出码
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⏹️  测试已取消")
        sys.exit(130)

