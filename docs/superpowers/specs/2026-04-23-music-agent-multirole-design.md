# 多角色协作音乐 Agent 架构设计

## 1. 背景与动机

### 1.1 当前架构问题

现有 `core/orchestrator.py` 采用单 LLM 扁平循环模式：
- LLM 只能从 10 个 action 中选择一个执行，无法直接参与音乐创作决策
- 没有分析→编排→表达的阶段概念，所有 action 同等开放
- 工具间没有依赖关系感知（如 `generate_accompaniment` 依赖和声分析但 LLM 不知道）
- 产出质量没有 Critic 把关，音高、和声、伴奏、力度都可能不达标
- 工具返回的结果只有一行字符串，大量信息丢失
- 循环终止依赖 LLM 主动返回 `{"done": true}`，经常出现重复调用同一 action 的循环卡死

### 1.2 目标

将单 LLM 扁平循环重构为 6 个角色的协作流水线：
- 每个角色独立 LLM 调用，有专用 prompt 和工具子集
- 角色间通过结构化 JSON 报告通信
- Critic 质量评审，不通过则打回对应角色重做（最多 2 次）
- Planner 只做路由和参数传递，不参与音乐创作

## 2. 角色定义

### 2.1 Planner — 计划控制器

| 字段 | 值 |
|------|-----|
| 职责 | 解析用户指令，决定走哪些阶段、传什么参数 |
| LLM 调用 | 1 次（不循环） |
| 输入 | 用户指令 + Analyst 预分析报告 |
| 工具 | 无 — 纯决策 |
| 输出 | `JSON {phases: [...], params: {arrange_style, ...}}` |
| prompt | `prompts/planner.md` |

**工作流程：**
1. Analyst 执行分析工具（只读），产出基础报告
2. Planner 读取用户指令 + Analyst 报告，决定执行计划
3. 计划是有序的阶段列表，每个阶段附带参数

**示例输出：**
```json
{
  "phases": ["analysis", "arrangement", "expression"],
  "params": {
    "arrangement": {"instrument": "piano", "style": "classical"},
    "expression": {"melody_boost": 10, "timing": "rubato"}
  }
}
```

### 2.2 Analyst — 音乐分析师

| 字段 | 值 |
|------|-----|
| 职责 | 提取旋律、检测和声、识别声部角色、音域诊断 |
| LLM 调用 | 1 次（读取工具分析结果后做诊断总结） |
| 输入 | musicpy piece |
| 工具 | `extract_melody`, `analyze_harmony`, `range_check`, `voice_detection` |
| 输出 | `JSON {melody, harmony, voice_roles, range_issues}` |
| prompt | `prompts/analyst.md` |

**关键约束：**
- 只读不写，不修改 piece
- 产出结构化报告供下游角色使用
- 附加 ABC notation 作为全局音乐上下文

**示例输出：**
```json
{
  "melody": {"track": 0, "notes": 142, "range": "C4-G5"},
  "harmony": [{"measure": 1, "chord": "Cmaj7"}, ...],
  "voice_roles": {"melody": [0], "harmony": [1], "bass": [2]},
  "range_issues": []
}
```

### 2.3 Arranger — 编排师

| 字段 | 值 |
|------|-----|
| 职责 | 根据计划和分析报告，编排乐器布局、声部映射 |
| LLM 调用 | 最多 2 次循环 |
| 输入 | piece + Analyst 报告 + Planner 参数 |
| 工具 | `arrange_for_piano`, `arrange_for_strings`, `arrange_for_winds` |
| 输出 | 修改后的 piece + 编排报告 |
| prompt | `prompts/arranger.md` |

**关键约束：**
- 循环最多 2 次，每次必须有明确的调整目标
- 不再隐式调用 Analysis 工具（解耦后由上游 Analyst 提供）
- 每次循环后产出结构化报告供 Critic 评审

### 2.4 Harmonist — 和声师

| 字段 | 值 |
|------|-----|
| 职责 | 生成伴奏、调整和弦走向 |
| LLM 调用 | 最多 2 次循环 |
| 输入 | piece + Analyst 和声报告 + Planner 参数 |
| 工具 | `generate_accompaniment` |
| 输出 | 追加的伴奏 track + 和声报告 |
| prompt | `prompts/harmonist.md` |

**关键约束：**
- 可选角色，Planner 计划中不包含则跳过
- 依赖 Analyst 的和声分析报告，不再自行检测和声

### 2.5 Expression — 表情工程师

| 字段 | 值 |
|------|-----|
| 职责 | 力度调整、时序变化、踏板事件 |
| LLM 调用 | 最多 2 次循环 |
| 输入 | piece + 前序角色报告 |
| 工具 | `adjust_velocity`, `apply_timing_variation`, `add_sustain_pedal` |
| 输出 | 最终 piece + 表情报告 |
| prompt | `prompts/expression.md` |

**关键约束：**
- 只在编排完成后执行，不改变音符结构
- 循环最多 2 次

### 2.6 Critic — 质量评审

| 字段 | 值 |
|------|-----|
| 职责 | 最终质量把关，检查音域、和声合理性、力度平衡、整体连贯性 |
| LLM 调用 | 1 次 |
| 输入 | 最终 piece + 所有角色报告 |
| 工具 | `range_check`（只读验证） |
| 输出 | `JSON {passed, issues: [{role, severity, description, fix_instruction}]}` |
| prompt | `prompts/critic.md` |

**打回规则：**
- 有 high severity issue → 打回对应角色重做
- 同一角色最多被打回 2 次
- 2 次打回后自动降级：记录问题但继续流程

## 3. 数据流

```
MIDI + 指令
    ↓
[Analyst] 预分析（只读）→ 基础报告
    ↓
[Planner] 读取报告 + 指令 → 生成执行计划
    ↓
  按计划依次执行：
    [Arranger] → 编排后的 piece（≤2次循环）
    [Harmonist] → 追加伴奏（可选，≤2次循环）
    [Expression] → 表情处理（≤2次循环）
    ↓
[Critic] 质量评审
    ↓ (不通过且有 high issue)
  打回对应角色 → 重做（最多 2 次）
    ↓ (通过)
输出 MIDI
```

## 4. 工具解耦

### 4.1 ArrangePianoTool 解耦

**当前问题：** `ArrangePianoTool.run()` 内部调用 `ExtractMelodyTool` + `AnalyzeHarmonyTool` + `GenerateAccompanimentTool`，LLM 无法独立控制各步骤。

**解耦后：**
- `ArrangePianoTool` 只接收已经提取好的旋律和和声数据（来自 Analyst 报告）
- 不再内部调用 Analysis 工具
- 专注于旋律分配到右手 + 伴奏分配到左手的布局工作

### 4.2 GenerateAccompanimentTool 解耦

**当前问题：** 在 `execute_command` 中隐式调用 `AnalyzeHarmonyTool`。

**解耦后：**
- 直接接收 Analyst 产出的和声数据
- 只负责根据和弦和 pattern 生成伴奏音符

### 4.3 AdjustVelocityTool 改进

- 不再依赖 `detect_voice_roles` 全局检测
- 接收 Analyst 的 `voice_roles` 报告作为参数
- 只调整指定的 melody/accompaniment tracks

## 5. 文件变更清单

| 文件 | 改动 |
|------|------|
| `core/orchestrator.py` | 重写为 `RoleOrchestrator`，管理角色调度和打回循环 |
| `core/roles/` (新目录) | 6 个角色模块，每个有独立 `run()` 方法和 prompt 加载 |
| `prompts/planner.md` | 新建 |
| `prompts/analyst.md` | 新建 |
| `prompts/arranger.md` | 新建 |
| `prompts/harmonist.md` | 新建 |
| `prompts/expression.md` | 新建 |
| `prompts/critic.md` | 新建 |
| `prompts/orchestrator.md` | 删除（被上述 6 个 prompt 替代） |
| `agent/tool_registry.py` | 增加角色工具子集映射 |
| `tools/arrangement/arrange_piano.py` | 解耦：移除内部 Analysis 调用 |
| `tools/harmony/generate_accompaniment.py` | 解耦：移除隐式和声分析调用 |
| `tools/expression/adjust_velocity.py` | 接收 voice_roles 参数而非自动检测 |

## 6. 接口约定

### 6.1 角色基类

```python
class Role(ABC):
    name: str
    prompt_template: str
    max_iterations: int
    tools: list[Tool]

    @abstractmethod
    def run(self, piece: mp.P, context: dict) -> dict:
        """执行角色任务，返回结构化报告。"""
        ...
```

### 6.2 上下文传递

角色间通过 `context: dict` 传递信息：
```python
context = {
    "instruction": str,          # 用户原始指令
    "plan": dict,                # Planner 输出
    "analyst_report": dict,      # Analyst 输出
    "arrangement_report": dict,  # Arranger 输出
    "harmony_report": dict,      # Harmonist 输出
    "expression_report": dict,   # Expression 输出
    "critic_issues": list,       # Critic 打回的问题（如有）
}
```

## 7. 向后兼容

- 保留 `run_pipeline()` 函数签名，内部改用新架构
- `--melody-extract` CLI flag 仍然可用，走 Analyst 路径
- 旧的 `create_music_agent()` 函数保留但标记 deprecated
