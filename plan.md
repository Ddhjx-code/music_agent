# Music Agent — 项目计划 v2

## 项目定位

```
输入：任意 MIDI 文件 + 自然语言改编需求
输出：改编后的 MIDI 文件
核心：LLM 编排工具链 + musicpy 精确执行
```

**不是从零生成音乐，而是编辑改编已有音乐。** 对标场景：
- "把这首流行歌改成浪漫钢琴曲"
- "做成弦乐四重奏"
- "改成管乐团合奏，注意移调乐器"

---

## 技术选型结论

| 决策 | 选择 | 理由 |
|------|------|------|
| 核心执行引擎 | **musicpy** | 原生多轨/和弦/乐器支持，自带乐理算法模块 |
| 中间表示 | **musicpy JSON**（非 ABC） | musicpy 不支持 ABC，JSON 更结构化 |
| LLM 角色 | **工具链编排者**（非文本编辑器） | LLM 决定参数和步骤，代码保证精确性 |
| 架构模式 | **混合方案**：80% 工具链 + 20% ABC 直接编辑 | 常规改编走工具链，创意需求 fallback 到 LLM 改 ABC |
| MIDI 读写 | **musicpy 内置 mido** | 不需要单独用 mido，musicpy.read()/write() 已封装 |

### 依赖精简

| 项目 | 用途 | 阶段 |
|------|------|------|
| `musicpy` | 核心：音乐解析/编辑/导出/乐理算法 | Phase 1 起 |
| `langchain` | Agent 框架：工具注册/LLM 调度 | Phase 1 起 |
| `mido` | musicpy 内置依赖，不单独使用 | 自动安装 |
| `abc2midi` / `abcm2ps` | ABC ↔ MIDI 互转（fallback 链路） | Phase 3 |
| `music21` | 复杂乐理分析（可选，musicpy 不够用时） | Phase 3 |
| `demucs` | 音频分轨（音频输入场景） | Phase 4 |
| `basic-pitch` | 音频→MIDI 转录 | Phase 4 |
| `fluidsynth` | MIDI→音频渲染 | Phase 4 |

---

## 核心架构

### LLM 工具链编排模型

```
用户: "把小星星改成浪漫的钢琴曲，带点rubato感觉"
         ↓
    LLM 推理并调用工具链:
    1. extract_melody(piece)
    2. analyze_harmony(melody)
    3. generate_piano_accompaniment(harmony, style="romantic_arpeggio")
    4. add_sustain_pedal(piece, mode="harmonic_change")
    5. adjust_velocity(melody_boost=+15, accompaniment_reduce=-20)
    6. apply_timing_variation("rubato", amount=0.08)
         ↓
    输出改编后 MIDI
```

**LLM 不是选预设风格，而是决定每一步的参数。** 工具保证执行正确性，LLM 负责创意组合。

### 工具原子化设计

| 工具类别 | 工具名 | 功能 | LLM 控制参数 |
|---------|--------|------|-------------|
| **分析类** | `extract_melody` | 从多轨 MIDI 提取主旋律 | 置信度阈值 |
| | `analyze_harmony` | 和弦分析（调用 musicpy.alg.detect） | 分析粒度 |
| | `analyze_form` | 曲式结构分析（段落/乐句） | — |
| **和声类** | `generate_accompaniment` | 伴奏织体生成 | style, pattern, voicing, density |
| | `reharmonize` | 重配和声 | style, complexity |
| | `transpose` | 移调 | semitones 或 target_key |
| **编排类** | `arrange_for_piano` | 改编为钢琴独奏 | voicing_style, hand_split |
| | `arrange_string_quartet` | 弦乐四重奏编排 | voice_mapping |
| | `arrange_wind_ensemble` | 管乐团合奏（含移调乐器处理） | instrumentation |
| | `change_instrument` | 单轨换乐器 | gm_program |
| **表现力类** | `add_sustain_pedal` | 钢琴踏板 | mode, frequency |
| | `adjust_velocity` | 力度/音量调整 | melody_delta, accompaniment_delta |
| | `apply_timing_variation` | 节奏微调（rubato/swing） | type, amount |
| | `change_tempo` | 变速 | bpm, rubato_curve |
| **验证类** | `validate_range` | 乐器音域检查 | instrument_name |
| | `validate_theory` | 乐理规则检查 | rules |

### 混合方案：工具链 + ABC fallback

```
常规改编（80%）:
  工具链编排 → 每步可验证 → 输出 MIDI

创意需求（20%）:
  工具链无法满足 → 转 ABC → LLM 直接编辑 ABC → 转回 MIDI
  例: "让第二段听起来像下雨的感觉"
```

---

## Phase 1：核心链路（2 周）

**目标：MIDI → 分析 → LLM 编排工具链 → 改编 MIDI**

### 1.1 项目结构

```
music-agent/
├── core/
│   ├── music_io.py           # MIDI 读写（musicpy 封装）
│   ├── json_schema.py        # 音乐摘要 JSON Schema（给 LLM 看）
│   └── orchestrator.py       # LangChain Agent 调度
├── tools/
│   ├── analysis/
│   │   ├── extract_melody.py
│   │   └── analyze_harmony.py
│   ├── arrangement/
│   │   ├── arrange_piano.py
│   │   └── arrange_strings.py
│   ├── expression/
│   │   ├── add_pedal.py
│   │   ├── adjust_velocity.py
│   │   └── timing_variation.py
│   └── validation/
│       └── theory_check.py
├── agent/
│   ├── tool_registry.py      # 工具注册（LangChain Tool 格式）
│   └── prompt_templates.py   # 提示词模板
├── tests/
│   └── test_phase1.py
└── requirements.txt
```

### 1.2 音乐摘要 JSON（给 LLM 看，不是完整音符数据）

```python
MUSIC_SUMMARY_SCHEMA = {
    "title": "string",
    "key": "C",                    # 调性
    "bpm": 120,
    "time_signature": "4/4",
    "num_measures": 32,
    "num_tracks": 2,
    "tracks": [{
        "name": "Melody",
        "instrument": "Acoustic Grand Piano",
        "role": "melody",          # melody/harmony/bass/percussion
        "pitch_range": "C4-G5",
        "avg_velocity": 80,
    }],
    "chord_progression": [
        {"measure": 1, "chord": "C"},
        {"measure": 2, "chord": "C"},
        {"measure": 3, "chord": "G"},
        {"measure": 4, "chord": "G"},
        # ...
    ],
    "form": [
        {"section": "A", "measures": "1-16"},
        {"section": "B", "measures": "17-32"},
    ]
}
```

**关键：LLM 看到的是摘要，不是每个音符。完整音符数据存在 musicpy piece 对象里，由工具操作。**

### 1.3 第一个核心功能：钢琴改编

```python
# tools/arrangement/arrange_piano.py
import musicpy as mp

class ArrangePianoTool:
    name = "arrange_for_piano"
    description = "将多轨音乐改编为钢琴独奏，合并旋律与和声为双手可演奏的形式"

    def run(self, piece, style: str = "classical",
            voicing: str = "closed", hand_split: str = "auto") -> dict:
        """
        1. 提取主旋律 → 右手
        2. 和弦分析 → 左手伴奏织体
        3. 根据 style 选择伴奏 pattern:
           - classical: 阿尔贝蒂低音/分解和弦
           - romantic: 开放排列琶音
           - pop: 柱式和弦 + 八度低音
        4. 音域限制（钢琴 88 键）
        5. 返回 piece 对象
        """
        ...
```

### 1.4 伴奏生成（核心工具）

```python
# tools/analysis/generate_accompaniment.py
import musicpy as mp

class GenerateAccompanimentTool:
    name = "generate_accompaniment"
    description = "根据和弦进行生成伴奏织体"

    def run(self, harmony, style: str, pattern: str,
            voicing: str = "closed", density: str = "medium") -> mp.chord:
        """
        style: romantic / classical / pop / jazz
        pattern: arpeggio / alberti / block_chord / walking_bass
        voicing: closed / open / drop2
        density: sparse / medium / dense
        """
        ...
```

### 1.5 Agent 工具注册

```python
# agent/tool_registry.py
from langchain.tools import BaseTool

TOOLS = [
    ExtractMelodyTool(),
    AnalyzeHarmonyTool(),
    ArrangePianoTool(),
    ArrangeStringsTool(),
    GenerateAccompanimentTool(),
    AddSustainPedalTool(),
    AdjustVelocityTool(),
    ApplyTimingVariationTool(),
    TransposeTool(),
    ValidateTheoryTool(),
]

# LangChain 自动根据 description 选择工具
agent = create_openai_functions_agent(
    llm=llm,
    tools=TOOLS,
    prompt=prompt
)
```

### Phase 1 验收标准

```
✅ 任意 MIDI → 正确提取和弦进行 + 主旋律摘要
✅ LLM 能理解"改成钢琴曲"并调用正确的工具链
✅ 钢琴改编结果：旋律清晰 + 有伴奏 + 可正常播放
✅ 支持至少 3 种钢琴风格（classical/romantic/pop）
✅ 输出 MIDI 音域在钢琴范围内
```

---

## Phase 2：编排扩展（2 周）

**目标：支持弦乐四重奏、管乐团合奏**

### 2.1 弦乐四重奏

```python
class ArrangeStringsTool:
    def run(self, piece, voice_mapping: dict = None) -> mp.piece:
        """
        1. 分析输入曲目的声部（旋律/和声/内声部/低音）
        2. 映射到 Vln1/Vln2/Vla/Vcl
        3. 每轨音域检查：
           - Violin: G3-A7
           - Viola: C3-E6
           - Cello: C2-A5
        4. 声部进行规则检查（避免平行五度等）
        5. 设置正确的 GM 乐器 program
        """
        ...
```

### 2.2 管乐团合奏（含移调乐器）

```python
class ArrangeWindsTool:
    def run(self, piece, instrumentation: str = "standard") -> mp.piece:
        """
        标准编制: Fl/Cl(Bb)/Sax(Eb)/Tpt(Bb)/Hn/F/Tbn/Tuba
        关键: 移调乐器处理
          - Bb 调乐器（Cl, Tpt）: 记谱比实际音高全音
          - Eb 调乐器（Sax）: 记谱比实际音低小三度
        1. 声部分配
        2. 移调处理（记谱音 vs 实际音）
        3. 各乐器音域检查
        4. 设置 GM program
        """
        ...
```

### Phase 2 验收标准

```
✅ 弦乐四重奏：四声部分配正确，音域无越界
✅ 管乐团合奏：移调乐器记谱正确
✅ LLM 能根据自然语言选择正确的编排工具链
```

---

## Phase 3：表现力 + ABC Fallback（2 周）

### 3.1 表现力工具

```python
# 钢琴踏板
class AddSustainPedalTool:
    def run(self, piece, mode: str = "harmonic_change") -> mp.piece:
        # 按和弦变化位置插入 CC#64 踏板事件
        ...

# 力度调整
class AdjustVelocityTool:
    def run(self, piece, melody_boost: int = 0,
            accompaniment_reduce: int = 0) -> mp.piece:
        # 旋律轨 velocity += boost，伴奏轨 velocity -= reduce
        ...

# 节奏微调（rubato / swing）
class ApplyTimingVariationTool:
    def run(self, piece, type: str = "rubato",
            amount: float = 0.05) -> mp.piece:
        # rubato: 乐句结尾微减速
        # swing: 八分音符不等长
        ...
```

### 3.2 ABC Fallback 链路

```python
# 当工具链无法满足创意需求时
class ABCFallbackTool:
    def run(self, piece, instruction: str) -> mp.piece:
        """
        1. piece → MIDI → abc2midi → ABC 文本
        2. 给 LLM 看 ABC + 用户指令
        3. LLM 直接编辑 ABC 文本
        4. ABC → abcm2ps / abc2midi → MIDI
        5. MIDI → musicpy → piece
        """
        ...
```

### 3.3 验证层 + 自我修正

```python
class TheoryValidateTool:
    def run(self, piece) -> dict:
        issues = []
        # 1. 音域检查
        for track in piece.tracks:
            range_ok = validate_range(track, track.instrument)
            if not range_ok:
                issues.append({"type": "out_of_range", ...})
        # 2. 和声检查
        harmony_ok = check_harmony(piece)
        if not harmony_ok:
            issues.append({"type": "harmony_violation", ...})
        # 3. 声部进行检查
        voice_leading_ok = check_voice_leading(piece)
        ...
        return {"passed": len(issues) == 0, "issues": issues}
```

### Phase 3 验收标准

```
✅ 钢琴改编自带踏板 + 力度层次
✅ rubato/swing 节奏变换可用
✅ ABC fallback 链路跑通（创意需求场景）
✅ 验证层能捕获问题并触发 LLM 修正
```

---

## Phase 4：音频输入输出（1 周）

### 4.1 音频输入

```
MP3/WAV → Demucs 分轨 → Basic Pitch 转录 → MIDI → musicpy piece
```

### 4.2 音频输出

```
MIDI → FluidSynth → WAV（可选 SoundFont 定制音色）
```

---

## 完整时间线

```
Week 1-2      Week 3-4      Week 5-6      Week 7
────────────────────────────────────────────────────
Phase 1       Phase 2       Phase 3       Phase 4
核心链路       编排扩展      表现力+ABC    音频 I/O
  │             │             │             │
MIDI解析      弦乐四重奏    踏板/力度    音频输入
和弦分析      管乐团合奏    rubato/swing  音频输出
钢琴改编      移调乐器      验证闭环     FluidSynth
LLM工具链     音域检查      ABC fallback
```

---

## 最终项目结构

```
music-agent/
├── core/
│   ├── music_io.py              # MIDI 读写封装
│   ├── json_schema.py           # 音乐摘要 Schema
│   └── orchestrator.py          # Agent 调度
├── tools/
│   ├── analysis/
│   │   ├── extract_melody.py    # 主旋律提取
│   │   ├── analyze_harmony.py   # 和弦分析
│   │   └── analyze_form.py      # 曲式分析
│   ├── arrangement/
│   │   ├── arrange_piano.py     # 钢琴改编
│   │   ├── arrange_strings.py   # 弦乐四重奏
│   │   └── arrange_winds.py     # 管乐团合奏
│   ├── harmony/
│   │   ├── generate_accompaniment.py  # 伴奏生成
│   │   └── reharmonize.py       # 重配和声
│   ├── expression/
│   │   ├── add_pedal.py         # 踏板
│   │   ├── adjust_velocity.py   # 力度
│   │   └── timing_variation.py  # rubato/swing
│   ├── basic/
│   │   ├── transpose.py         # 移调
│   │   └── change_tempo.py      # 变速
│   └── validation/
│       ├── range_check.py       # 音域检查
│       └── theory_check.py      # 乐理验证
├── fallback/
│   └── abc_editor.py            # ABC 转换 + LLM 编辑
├── agent/
│   ├── tool_registry.py         # LangChain 工具注册
│   └── prompt_templates.py      # 提示词
├── tests/
├── output/
└── requirements.txt
```

---

## 关键设计原则

1. **LLM 做决策，代码做执行** — LLM 决定参数，musicpy 保证精确性
2. **摘要给 LLM，完整数据给代码** — LLM 看 JSON 摘要，不看逐音符数据
3. **工具原子化** — 每个工具做一件事，LLM 组合工具链
4. **每步可验证** — 验证层检查中间结果，错了反馈 LLM 重试
5. **ABC fallback** — 工具链搞不定的创意需求，LLM 直接编辑 ABC 文本
