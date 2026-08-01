"""Adversarial teaching-plan evaluator — multi-agent debate (TradingAgents /
Vibe @edu-analyst borrowing).

After the coach drafts a teaching plan (module concepts + tasks + targets),
an INDEPENDENT evaluator LLM call attacks it from a counter-perspective —
questioning cognitive load, ZPD fit, theory/practice ratio, motivation, and
assessment design. The coach then revises before presenting to the learner.
This gives multi-agent debate value without a heavyweight orchestration
framework: one authoritative coach role + one independent adversary.
"""

from __future__ import annotations

from typing import Any

from deeptutor.core.tool_protocol import BaseTool, ToolDefinition, ToolParameter, ToolResult
from deeptutor.tools.prompting import load_prompt_hints

_EVALUATOR_SYSTEM_PROMPT = """\
你是一位资深教学评估员（独立于授课教练的第二视角）。你的职责是对一份教学方案进行对抗性审查——不是礼貌地挑错，而是像最严格的督学一样质疑它的每一个假设。

必须从以下维度逐项质疑：
1. 认知负荷：一次引入的概念是否太多？顺序是否会造成过载？
2. ZPD：起点是否正好在学生能力边缘外一步？太简单=无聊，太难=挫败。
3. 理论/实践比：该教学模式（Zero-Base 4:6 / Standard 3:7 / Advanced 2:8）是否落实？
4. 动机：有没有让学生在每一阶段都能看到进步？会不会中途失去动力？
5. 评估手段：任务是否真的能检验所宣称的能力？F1 阈值是否合理？
6. 未覆盖风险：方案忽略了这个学生什么样的可能情况？

输出格式（严格）：
## 质疑点
- [严重度: 高/中/低] 具体质疑…（说明可能后果）
## 修正建议
- 针对每个质疑给出一个可操作修改。
## 结论
- 一句话：方案是否可用，或必须先改哪里。

不要美化。质疑必须具体到方案的条目，不是泛泛而谈。"""


class EvaluateTeachingPlanTool(BaseTool):
    """Adversarially review a teaching plan from an independent evaluator role."""

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="evaluate_teaching_plan",
            description=(
                "Adversarially review a teaching plan through an INDEPENDENT evaluator "
                "LLM call (multi-agent debate). The evaluator questions cognitive load, "
                "ZPD fit, theory/practice ratio, motivation, and assessment design. "
                "Call AFTER drafting a module/route plan and BEFORE presenting it to the "
                "student — revise based on the critique. Returns structured challenges + "
                "fixes. Never skip for complex multi-concept plans."
            ),
            parameters=[
                ToolParameter(
                    name="plan",
                    type="string",
                    description=(
                        "The teaching plan to review: module name, concepts, tasks, "
                        "targets, teaching mode. Plain text or JSON."
                    ),
                ),
                ToolParameter(
                    name="student_profile",
                    type="string",
                    description=(
                        "Learner context: diagnosed level, teaching mode, goal, "
                        "known weak points. Optional but improves the critique."
                    ),
                    required=False,
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        plan = str(kwargs.get("plan") or "").strip()
        student_profile = str(kwargs.get("student_profile") or "").strip()
        if not plan:
            return ToolResult(content="Error: plan is required.", success=False)

        try:
            answer = await self._evaluate(plan, student_profile)
        except Exception as exc:
            return ToolResult(
                content=f"评估员调用失败: {exc}",
                success=False,
                metadata={"error": str(exc)},
            )

        # Mirror the critique into the decision audit trail + store the full
        # evaluation for the progress "evaluation" panel.
        try:
            from deeptutor.services.learning_records import LearningRecordStore

            store = LearningRecordStore()
            await store.append_decision(
                {
                    "kind": "route_choice",
                    "target": "teaching_plan_review",
                    "rationale": "独立评估员对抗性审查教学方案",
                    "evidence": {"plan": plan, "evaluation": answer[:500]},
                }
            )
            await store.append_evaluation(
                {
                    "target": "teaching_plan_review",
                    "plan": plan,
                    "student_profile": student_profile,
                    "evaluation": answer,
                }
            )
        except Exception:
            pass

        return ToolResult(
            content=(
                "## 独立评估员审查结果\n\n"
                f"{answer}\n\n"
                "根据质疑点修正方案后再展示给学生。"
            ),
            metadata={"evaluator": "independent", "char_count": len(answer)},
        )

    async def _evaluate(self, plan: str, student_profile: str) -> str:
        from deeptutor.services.config import get_agent_params
        from deeptutor.services.llm import get_token_limit_kwargs
        from deeptutor.services.llm import stream as llm_stream
        from deeptutor.services.llm.config import get_llm_config

        llm_cfg = get_llm_config()
        agent_params = get_agent_params("chat")
        max_tokens = agent_params.get("max_tokens", 4096)
        temperature = 0.4

        parts: list[str] = []
        if student_profile:
            parts.append(f"## 学习者画像\n{student_profile}")
        parts.append(f"## 待审查的教学方案\n{plan}")
        user_prompt = "\n\n".join(parts)

        kwargs: dict[str, Any] = {"temperature": temperature}
        if max_tokens:
            kwargs.update(get_token_limit_kwargs(llm_cfg.model, max_tokens))

        chunks: list[str] = []
        async for chunk in llm_stream(
            prompt=user_prompt,
            system_prompt=_EVALUATOR_SYSTEM_PROMPT,
            model=llm_cfg.model,
            api_key=llm_cfg.api_key,
            base_url=llm_cfg.base_url,
            **kwargs,
        ):
            chunks.append(chunk)
        return "".join(chunks).strip()

    def get_prompt_hints(self, language: str = "en") -> Any:
        hints = load_prompt_hints(self.name, language=language)
        if hints.short_description:
            return hints
        return super().get_prompt_hints(language=language)


__all__ = ["EvaluateTeachingPlanTool"]
