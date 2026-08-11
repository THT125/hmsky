# -*- coding: utf-8 -*-
"""为 dish/setmeal 生成本地占位图片,并更新数据库 image 字段。
原项目图片存阿里云 OSS(sky-itcast.oss-cn-beijing.aliyuncs.com),现已 403 失效,
此脚本将图片本地化到 backend/static/demo_images/。
运行: python gen_images.py
"""
import os
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import DATABASE_URL_SYNC, STATIC_DIR
from app.models import Dish, Setmeal

FONT_PATH = r"C:\Windows\Fonts\msyh.ttc"  # 微软雅黑
OUT_DIR = STATIC_DIR / "demo_images"

# 美食主题渐变配色
PALETTES = [
    ((255, 138, 101), (255, 82, 82)),    # 橙红
    ((255, 171, 64), (255, 111, 0)),     # 橘黄
    ((174, 213, 129), (85, 139, 47)),    # 青绿
    ((255, 213, 79), (255, 152, 0)),     # 金黄
    ((128, 222, 234), (0, 172, 193)),    # 天蓝
    ((206, 147, 216), (156, 39, 176)),   # 紫
    ((239, 154, 154), (211, 47, 47)),    # 番茄红
    ((255, 204, 128), (230, 81, 0)),     # 深橙
]


def draw_placeholder(name: str, idx: int, path: Path):
    w = h = 300
    img = Image.new("RGB", (w, h))
    c1, c2 = PALETTES[idx % len(PALETTES)]
    for y in range(h):
        ratio = y / h
        r = int(c1[0] + (c2[0] - c1[0]) * ratio)
        g = int(c1[1] + (c2[1] - c1[1]) * ratio)
        b = int(c1[2] + (c2[2] - c1[2]) * ratio)
        for x in range(w):
            img.putpixel((x, y), (r, g, b))

    draw = ImageDraw.Draw(img)
    # 居中写菜品名
    font_size = 36
    font = ImageFont.truetype(FONT_PATH, font_size)
    # 自动缩小字号直至放得下
    while draw.textbbox((0, 0), name, font=font)[2] > w - 40 and font_size > 18:
        font_size -= 4
        font = ImageFont.truetype(FONT_PATH, font_size)
    bbox = draw.textbbox((0, 0), name, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((w - tw) / 2, (h - th) / 2 - 10), name, font=font, fill=(255, 255, 255))
    # 底部提示文字
    font_small = ImageFont.truetype(FONT_PATH, 20)
    tip = "演示图片"
    tb = draw.textbbox((0, 0), tip, font=font_small)
    draw.text(((w - (tb[2] - tb[0])) / 2, h - 60), tip, font=font_small, fill=(255, 255, 255, 180))
    img.save(path, "JPEG", quality=85)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    # 独立脚本:使用同步驱动引擎(与应用异步引擎互不影响)
    engine = create_engine(DATABASE_URL_SYNC, pool_pre_ping=True)
    db = sessionmaker(bind=engine)()
    try:
        idx = 0
        dishes = db.query(Dish).all()
        for d in dishes:
            idx += 1
            path = OUT_DIR / f"dish_{d.id}.jpg"
            draw_placeholder(d.name, idx, path)
            if d.image != f"/static/demo_images/dish_{d.id}.jpg":
                d.image = f"/static/demo_images/dish_{d.id}.jpg"
        setmeals = db.query(Setmeal).all()
        for s in setmeals:
            idx += 1
            path = OUT_DIR / f"setmeal_{s.id}.jpg"
            draw_placeholder(s.name, idx, path)
            if s.image != f"/static/demo_images/setmeal_{s.id}.jpg":
                s.image = f"/static/demo_images/setmeal_{s.id}.jpg"
        db.commit()
        print(f"完成: {len(dishes)} 道菜品 + {len(setmeals)} 个套餐, 图片目录: {OUT_DIR}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
