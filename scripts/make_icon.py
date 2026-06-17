"""生成应用图标：蓝底圆角 + 白色双音符。
产出 assets/icon.png（1024）与 assets/icon.ico；.icns 由 iconutil 在外部生成。
运行：python scripts/make_icon.py
"""
import os
from PIL import Image, ImageDraw

SZ = 1024
ASSETS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
os.makedirs(ASSETS, exist_ok=True)


def make():
    img = Image.new("RGBA", (SZ, SZ), (0, 0, 0, 0))

    # 竖直渐变背景
    grad = Image.new("RGB", (SZ, SZ))
    gd = ImageDraw.Draw(grad)
    top, bot = (91, 141, 239), (47, 111, 214)
    for y in range(SZ):
        t = y / SZ
        gd.line([(0, y), (SZ, y)], fill=(
            int(top[0] + (bot[0] - top[0]) * t),
            int(top[1] + (bot[1] - top[1]) * t),
            int(top[2] + (bot[2] - top[2]) * t),
        ))
    mask = Image.new("L", (SZ, SZ), 0)
    ImageDraw.Draw(mask).rounded_rectangle([40, 40, SZ - 40, SZ - 40], radius=220, fill=255)
    img.paste(grad, (0, 0), mask)

    # 白色双音符
    d = ImageDraw.Draw(img)
    w = (255, 255, 255, 255)
    d.ellipse([305, 635, 455, 745], fill=w)          # 左符头
    d.ellipse([625, 635, 775, 745], fill=w)          # 右符头
    d.rounded_rectangle([440, 360, 468, 700], radius=14, fill=w)   # 左符干
    d.rounded_rectangle([760, 360, 788, 700], radius=14, fill=w)   # 右符干
    d.rounded_rectangle([440, 330, 788, 398], radius=20, fill=w)   # 横梁

    img.save(os.path.join(ASSETS, "icon.png"))
    img.save(os.path.join(ASSETS, "icon.ico"),
             sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("wrote", os.path.join(ASSETS, "icon.png"), "and icon.ico")


if __name__ == "__main__":
    make()
