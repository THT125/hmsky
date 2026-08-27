"""图形验证码:4 位数字 + 干扰线,PIL 生成 base64 图片"""
import base64
import io
import logging
import random

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger("uvicorn.error")

WIDTH, HEIGHT = 120, 40
CODE_LEN = 4
_FONT_PATH = r"backend\assets\font\Arial.ttf"  # 优先英文字体(数字更清晰);不存在则用默认字体


def _font(size: int):
    try:
        return ImageFont.truetype(_FONT_PATH, size)
    except Exception as e:
        logger.warning("验证码字体加载失败,降级默认字体: %s", e)
        return ImageFont.load_default()


def generate_captcha() -> tuple[str, str]:
    """生成验证码,返回 (code, base64图片字符串)"""
    code = "".join(random.choices("0123456789", k=CODE_LEN))
    img = Image.new("RGB", (WIDTH, HEIGHT), (245, 247, 250))
    draw = ImageDraw.Draw(img)

    # 干扰线(2条)
    for _ in range(2):
        draw.line(
            [(random.randint(0, WIDTH), random.randint(0, HEIGHT)),
             (random.randint(0, WIDTH), random.randint(0, HEIGHT))],
            fill=(random.randint(150, 220), random.randint(150, 220), random.randint(150, 220)),
            width=1,
        )
    # 干扰点
    for _ in range(30):
        draw.point((random.randint(0, WIDTH), random.randint(0, HEIGHT)),
                   fill=(random.randint(120, 220), random.randint(120, 220), random.randint(120, 220)))

    # 逐字符绘制,随机颜色/微偏移
    font = _font(28)
    for i, ch in enumerate(code):
        draw.text(
            (10 + i * 26 + random.randint(-2, 2), random.randint(2, 8)),
            ch,
            font=font,
            fill=(random.randint(30, 130), random.randint(30, 130), random.randint(30, 130)),
        )

    buf = io.BytesIO()
    img.save(buf, "PNG")
    return code, base64.b64encode(buf.getvalue()).decode()
