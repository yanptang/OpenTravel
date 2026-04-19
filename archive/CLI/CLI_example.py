"""一个最小的 Python CLI 示例。

这个示例演示三个基础点：
1. 如何使用 argparse 接收命令行参数
2. 如何把参数交给业务逻辑处理
3. 如何把结果输出到终端
"""

from __future__ import annotations

import argparse


def build_parser() -> argparse.ArgumentParser:
    """创建命令行参数解析器。"""
    parser = argparse.ArgumentParser(
        description="一个简单的个人健康助理 CLI 示例",
        epilog="示例：python3 CLI_example.py --name 小明 --weight 60 --height 170",
    )
    parser.add_argument("-n", "--name", default="朋友", help="你的名字")
    parser.add_argument("--weight", type=float, help="你的体重(kg)")
    parser.add_argument("--height", type=float, help="你的身高(cm)")
    return parser


def calculate_bmi(weight_kg: float, height_cm: float) -> float:
    """根据体重和身高计算 BMI。"""
    height_m = height_cm / 100
    if height_m <= 0:
        raise ValueError("height_cm must be greater than 0.")
    return weight_kg / (height_m**2)


def get_bmi_message(bmi: float) -> str:
    """根据 BMI 返回一条简单建议。"""
    if bmi < 18.5:
        return "建议多吃点营养的食物哦。"
    if bmi < 24:
        return "身材保持得真棒！"
    return "要注意适度运动呀。"


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    print(f"\n你好, {args.name}!")

    if args.weight is None or args.height is None:
        print("如果你提供体重和身高，我可以帮你计算 BMI。")
        return 0

    bmi = calculate_bmi(args.weight, args.height)
    print(f"你的 BMI 指数是: {bmi:.2f}")
    print(get_bmi_message(bmi))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
