# src/core/strategy_parser.py

import json
import logging
from pydantic import BaseModel, Field

class FactorWeightConfig(BaseModel):
    """因子权重配置 (标准字典)"""
    momentum: float = Field(default=0.0, description="动量因子: 偏好近期涨幅大的强势股")
    value: float = Field(default=0.0, description="价值因子: 偏好低 PE、低 PB 的资产")
    quality: float = Field(default=0.0, description="质量因子: 偏好高 ROE (高净资产收益率) 的资产")
    volatility: float = Field(default=0.0, description="波动因子: 偏好振幅大、换手率高的弹性票")
    dividend: float = Field(default=0.0, description="红利因子: 偏好防御性")

    def normalize(self):
        """数学归一化：确保所有权重之和严格等于 1.0"""
        total = sum([self.momentum, self.value, self.quality, self.volatility, self.dividend])
        if total > 0:
            self.momentum = round(self.momentum / total, 2)
            self.value = round(self.value / total, 2)
            self.quality = round(self.quality / total, 2)
            self.volatility = round(self.volatility / total, 2)
            self.dividend = round(self.dividend / total, 2)
        return self

class PolicyTranslator:
    """语义映射层：将投资哲学转化为数学因子权重"""
    def __init__(self, client):
        self.client = client

    def translate(self, philosophy: str) -> FactorWeightConfig:
        system_prompt = """
        你是一个量化策略因子映射器。
        请阅读用户的[投资哲学]，将其转化为一组权重总和为 1.0 的 JSON 配置。
        可选因子：
        - momentum (动量): 适合想追击热点、强势股的描述。
        - value (价值): 适合强调低估值、安全边际、捡漏的描述。
        - quality (质量): 适合强调公司基本面好、成长性、业绩有支撑的描述。
        - volatility (波动): 适合不怕风险、想要弹性、打一枪换一个地方的描述。
        - dividend (红利): 适合强调收息、极度防御、稳健的描述。
        
        必须只输出合法的 JSON，不要输出任何 Markdown 标记(如 ```json) 或额外解释。
        例如: {"momentum": 0.4, "value": 0.2, "quality": 0.3, "volatility": 0.1, "dividend": 0.0}
        """
        
        try:
            logging.info("🧠 正在将文字哲学映射为量化因子权重...")
            response = self.client.chat.completions.create(
                model="deepseek-chat", # 请确保与你 main.py 中的模型一致
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"投资哲学: {philosophy}"}
                ],
                temperature=0.1
            )
            raw_text = response.choices[0].message.content.strip()
            
            # 容错：去除可能残留的 markdown 标记
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:-3].strip()
            elif raw_text.startswith("```"):
                raw_text = raw_text[3:-3].strip()
                
            data = json.loads(raw_text)
            config = FactorWeightConfig(**data)
            return config.normalize() # 确保总和为 1
            
        except Exception as e:
            logging.error(f"语义映射失败，采用均值防御策略: {e}")
            # 兜底默认值：均衡偏价值
            return FactorWeightConfig(value=0.4, quality=0.3, dividend=0.3).normalize()