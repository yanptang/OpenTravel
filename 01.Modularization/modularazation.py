import json
import pandas as pd
from litellm import completion

# 1. 模拟你的系统提示词 (简单版)
# 注意：一定要告诉模型返回 JSON
TEST_SYSTEM_PROMPT = """
你是一个行程规划专家。请根据用户需求，输出一个 JSON 格式的 2 天行程。
输出格式必须严格如下：
{
  "itinerary": [
    {
      "day": 1,
      "date": "2026-05-01",
      "slots": [
        {"time_range": "09:00-10:00", "type": "activity", "title": "景点A", "location": "地点A", "details": "详情A", "logic_check": "逻辑A"}
      ]
    }
  ]
}
"""

def quick_smoke_test():
    print("🎬 开始快速冒烟测试...")

    try:
        # 2. 调用本地 Ollama (确保你已经 pull 了 qwen3.5)
        print("🔗 正在连接 Ollama (qwen3.5)...")
        response = completion(
            model="ollama/qwen3.5",
            messages=[
                {"role": "system", "content": TEST_SYSTEM_PROMPT},
                {"role": "user", "content": "我要去冰岛玩2天"}
            ],
            api_base="http://localhost:11434",
            response_format={"type": "json_object"}
        )

        # 3. 提取结果
        content = response.choices[0].message.content
        print("📥 AI 成功返回了内容！")
        
        # 4. 解析 JSON
        data = json.loads(content)
        
        # 5. 展平数据并用 Pandas 导出
        all_slots = []
        for day in data['itinerary']:
            for slot in day['slots']:
                slot['day'] = day['day']
                slot['date'] = day['date']
                all_slots.append(slot)
        
        df = pd.DataFrame(all_slots)
        output_file = "test_output.xlsx"
        df.to_excel(output_file, index=False)

        print(f"\n✅ 测试完全成功！")
        print(f"📂 已生成测试文件: {output_file}")
        print("--- 预览数据 ---")
        print(df[['day', 'title', 'location']].to_string(index=False))

    except Exception as e:
        print(f"\n❌ 测试失败，错误原因: {e}")
        print("\n💡 排查建议：")
        print("1. 终端输入 'ollama list' 看看有没有 qwen3.5")
        print("2. 确保 Ollama 软件已经在后台运行")

if __name__ == "__main__":
    quick_smoke_test()