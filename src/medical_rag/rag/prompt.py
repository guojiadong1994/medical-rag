from __future__ import annotations

from pydantic import BaseModel

from medical_rag.rag.context import RAGContext


DEFAULT_GROUNDED_SYSTEM_PROMPT = """你是医疗知识库问答助手。你的任务是严格依据提供的检索证据回答问题。

必须遵守：
1. 只使用给定证据中的信息，不要用记忆或外部知识补全缺失事实。
2. 对关键医学事实、阈值、定义、检查项目等，在对应句末标注证据编号，例如 [S1]。
3. 只能引用本次上下文中真实存在的 [S1]、[S2] 等编号，不得编造来源。
4. 如果多个证据存在差异，明确说明差异并分别引用，不要擅自消解冲突。
5. 如果证据不足以支持答案，明确回答“现有检索证据不足以回答该问题”，不要猜测。
6. 区分指南中的一般性知识与针对具体患者的个体化医疗决策；没有患者资料和临床判断时，不给出个体化诊断、处方或用药调整指令。
7. 回答优先简洁、直接；数值和单位必须忠实于证据。"""


class RAGPrompt(BaseModel):
    system_prompt: str
    user_prompt: str


class GroundedPromptBuilder:
    def __init__(self, system_prompt: str = DEFAULT_GROUNDED_SYSTEM_PROMPT) -> None:
        self.system_prompt = system_prompt.strip()

    def build(self, context: RAGContext) -> RAGPrompt:
        if context.sources:
            evidence = context.context_text
        else:
            evidence = "（没有检索到可用证据）"
        user_prompt = (
            f"用户问题：\n{context.query.strip()}\n\n"
            f"检索证据：\n{evidence}\n\n"
            "请根据以上证据作答，并在相应事实后使用 [Sx] 标注来源。"
        )
        return RAGPrompt(system_prompt=self.system_prompt, user_prompt=user_prompt)
