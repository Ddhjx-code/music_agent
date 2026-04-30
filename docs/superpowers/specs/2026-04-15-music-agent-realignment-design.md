# Music Agent 重构设计：对齐 plan.md

## 问题陈述

当前实现偏离 plan.md 太远，核心问题：
1. 大量自编算法替代 musicpy 内置函数
2. LLM 参与度太弱（只选 action，不参与音乐内容处理）
3. 没有 musicpy ↔ JSON 双向转换，LLM 看不到完整音乐结构

## 设计原则

1. **LLM 深度参与**：LLM 看到结构化 JSON 音乐表示，直接推理和修改音乐内容
2. **musicpy 优先**：所有工具内部逻辑用 musicpy 内置函数替代自编算法
3. **渐进式重构**：保留工具接口和音频链路，只重构 orchestrator 和核心工具

## 架构

```
MIDI → music_io.load_midi() → musicpy piece
                                    ↓
                        music_to_json() → JSON_SUMMARY
                                    ↓
                    LLM 接收 JSON + 用户指令
                    LLM 输出第一步 action（或完整工具链）
                                    ↓
                    执行工具 → 结果 piece
                                    ↓
                    piece → music_to_json() → JSON_UPDATE（反馈给 LLM）
                                    ↓
                    LLM 根据反馈决定下一步
                                    ↓
                        循环直到 LLM 完成
                                    ↓
                    save_midi(piece) → 输出 MIDI
```

## 组件设计

### 1. core/music_transform.py（新增）

musicpy piece ↔ JSON 双向转换层。

**piece_to_json(piece)**: 输出完整的结构化 JSON，包含：
- 摘要信息（调性、BPM、拍号、曲式）
- 每轨详细音符数据（pitch、duration、velocity、start_time）
- 和弦进行
- 声部角色推断

**json_to_piece(json_data)**: 从 JSON 重建 musicpy piece。

这两者让 LLM 可以：
- 看到完整的音乐内容（不只是摘要）
- 直接修改 JSON 中的音符参数
- 转回 piece 继续处理

### 2. core/orchestrator.py（重写）

从简单的 "LLM 选 action → 执行" 改为 "LLM 循环参与" 模式。

```python
def create_music_agent(llm):
    """创建 LLM 深度参与的音乐 agent。"""
    def agent_fn(piece, instruction):
        # 1. piece → JSON 给 LLM 看
        music_json = piece_to_json(piece)

        # 2. LLM 接收 JSON + 指令，输出第一个 action
        current_json = music_json
        history = []

        while True:
            # 给 LLM 当前音乐状态 + 历史
            response = llm_decide(current_json, instruction, history)

            if response.done:
                break

            # 执行 LLM 选择的 action
            result = execute_command(response.action)
            current_json = piece_to_json(get_piece_context())
            history.append((response.action, result))

        return get_piece_context()

    return agent_fn
```

LLM 决策 prompt：
```
你是一个音乐编辑助手。这是当前音乐的结构化 JSON 表示。

用户的编辑需求是: {instruction}

你可以:
1. 调用一个工具来修改音乐（返回 action JSON）
2. 如果满意，返回 done=true

当前音乐: {music_json}
已完成的操作: {history}

请选择下一步操作。
```

### 3. 工具重构

#### tools/analysis/extract_melody.py
- **删除**: 手写的时间分组、音高筛选、outlier 过滤
- **改用**: musicpy 的多轨操作和内置音高分析

#### tools/analysis/analyze_harmony.py
- **精简**: _simplify_chord_name, _extract_root, _extract_quality 等大量手写解析
- **改用**: 直接用 mp.alg.detect 的结果，少做字符串处理

#### tools/harmony/generate_accompaniment.py
- **删除**: 350 行手写伴奏生成（_parse_chord_name, _make_arpeggio, _make_broken_chord 等）
- **改用**: musicpy 的 chord 生成和节奏处理功能

#### tools/arrangement/arrange_piano.py
- **精简**: 删除手写 gap-filling、dynamics 处理
- **改用**: musicpy 的轨道合并和表现力功能

### 4. 保留不变

- core/music_io.py
- core/llm.py
- core/audio_import.py
- core/audio_render.py
- core/audio_postprocess.py
- tools/arrangement/arrange_strings.py
- tools/arrangement/arrange_winds.py
- tools/validation/*
- tools/expression/*（除非内部也需要 musicpy 替换）

## 验收标准

1. ✅ 所有工具内部无自编算法，全部调用 musicpy 内置函数
2. ✅ LLM 能看到完整 JSON 音乐表示（不只是摘要）
3. ✅ 每步工具执行后，JSON 反馈给 LLM
4. ✅ LLM 能循环参与，直到完成所有编辑
5. ✅ 现有测试通过（或更新后通过）
6. ✅ 音频导入/渲染链路不受影响
