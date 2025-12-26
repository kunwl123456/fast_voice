"""
音色标签预设配置
"""

# 音色标签分类 (Voice Tag Categories)
# 基于Vocu.ai标签体系，使用英文字段
VOICE_TAG_CATEGORIES = {
    "language": [
        "zh_standard",  # 标准中文
        "yue_hk",  # 粤语（香港）
        "ja_standard",  # 日语
        "ko_standard",  # 韩语
        "en_standard",  # 英语
    ],
    "gender": [
        "female",  # 女性
        "male",  # 男性
    ],
    "age_group": [
        "child",  # 儿童
        "teen",  # 少年
        "youth",  # 青年
        "middle_aged",  # 中年
        "senior",  # 老年
    ],
    "emotion": [
        "neutral",  # 中性
        "gentle",  # 温柔
        "calm",  # 平静
        "melancholy",  # 忧郁
        "sad",  # 悲伤
        "excited",  # 兴奋
        "happy",  # 快乐
        "angry",  # 愤怒
        "fearful",  # 恐惧
        "surprised",  # 惊讶
        "anxious",  # 焦虑
        "nervous",  # 紧张
        "curious",  # 好奇
        "determined",  # 坚定
        "frustrated",  # 沮丧
        "indifferent",  # 冷漠
        "inspiring",  # 鼓舞人心
        "irritated",  # 恼怒
        "nostalgic",  # 怀旧
        "proud",  # 自豪
        "serious",  # 严肃
        "shy",  # 害羞
        "sleepy",  # 困倦
        "sympathetic",  # 同情
    ],
    "style": [
        "ancient_style",  # 古风韵味
        "anime_style",  # 二次元风格
        "classic_literary",  # 古典文艺
        "cute",  # 萌系可爱
        "fashionable",  # 时尚潮流
        "formal",  # 正式严肃
        "informal",  # 轻松随意
        "mysterious_dark",  # 神秘阴郁
        "sci_fi",  # 科幻感
        "sexy",  # 性感撩人
        "warm",  # 深情温暖
    ],
    "voice_feature": [
        "anime_imitation",  # 动漫拟声
        "asmr_healing",  # ASMR治愈型
        "clear_pure",  # 清新纯净
        "girl_sweet",  # 少女清甜
        "hoarse_textured",  # 沙哑有质感
        "magnetic_deep",  # 磁性厚重
        "mature_warm",  # 温厚老成
        "sweet_gentle",  # 娇柔甜美
        "teen_energetic",  # 少年元气
    ],
    "scenario": [
        "advertisement",  # 广告
        "animation_character",  # 动画角色
        "asmr_relaxation",  # ASMR放松
        "audio_drama",  # 广播剧
        "audiobook",  # 有声书
        "bedtime_story",  # 睡前故事
        "corporate_promo",  # 企业宣传
        "documentary_narration",  # 纪录片解说
        "education",  # 教育培训
        "experience_sharing",  # 经验分享
        "game_character",  # 游戏角色
        "gaming",  # 游戏
        "interview",  # 访谈
        "ivr",  # 电话语音（IVR）
        "meditation",  # 冥想引导
        "military_history",  # 军事历史
        "movie_character",  # 电影角色
        "movie_narration",  # 电影解说
        "movie_trailer",  # 电影预告
        "museum_tour",  # 博物馆导览
        "news",  # 新闻播报
        "promotional_video",  # 宣传片
        "public_announcement",  # 公共广播
        "public_service_announcement",  # 公益广告
        "public_transport",  # 公共交通
        "radio_host",  # 电台主播
        "short_video",  # 短视频
        "social_media",  # 社交媒体
        "speech",  # 演讲
        "theater_play",  # 戏剧表演
        "transportation",  # 交通运输
        "virtual_streamer",  # 虚拟主播
    ],
    "professional_field": [
        "aerospace",  # 航空航天
        "anime_acg",  # 动漫二次元
        "automotive",  # 汽车
        "environment_ecology",  # 环境生态
        "fashion_beauty",  # 时尚美妆
        "finance",  # 金融
        "legal",  # 法律
        "parenting",  # 育儿
        "religion_philosophy",  # 宗教哲学
        "technology",  # 科技
        "travel",  # 旅游
    ],
    "speed": [
        "slow",  # 较慢
        "medium",  # 中等
        "fast",  # 较快
        "very_fast",  # 非常快
    ],
    "rhythm": [
        "lively",  # 活泼
        "lyrical",  # 抒情
        "natural",  # 自然
        "passionate",  # 激昂
        "paused",  # 停顿感
        "rhythmic",  # 有节奏感
        "smooth",  # 流畅
    ],
    "tone": [
        "affirmative",  # 肯定
        "authoritative",  # 威严
        "confident",  # 自信
        "coquettish",  # 娇嗔
        "encouraging_tone",  # 鼓励
        "exclamatory",  # 感叹
        "happy",  # 愉快
        "humble",  # 谦逊
        "humorous",  # 幽默
        "provocative",  # 挑逗
        "questioning",  # 疑问
        "requesting",  # 请求
        "sarcastic",  # 讽刺
    ],
    "effect": [
        "dry",  # 干音
        "indoor_echo",  # 室内回声
        "sci_fi_robot_alien",  # 科幻机器人/外星人
        "vintage_recording",  # 复古录音
    ],
}


def get_all_tags() -> list[str]:
    """获取所有可用标签的扁平列表"""
    all_tags = []
    for tags in VOICE_TAG_CATEGORIES.values():
        all_tags.extend(tags)
    return all_tags


def validate_tags(tags: list[str]) -> tuple[bool, str]:
    """
    验证标签是否都在预设列表中

    Returns:
        (is_valid, error_message)
    """
    if not tags:
        return True, ""

    all_valid_tags = get_all_tags()
    invalid_tags = [tag for tag in tags if tag not in all_valid_tags]

    if invalid_tags:
        return False, f"无效的标签: {', '.join(invalid_tags)}"

    return True, ""


def get_tag_categories() -> dict[str, list[str]]:
    """获取标签分类字典"""
    return VOICE_TAG_CATEGORIES.copy()
