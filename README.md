# ptop —— 截图到梗图(反 PUA 回怼)

一张聊天截图进,一张回怼梗图出。用 **LangGraph** 编排,单一状态贯穿全流程,
带安全拦截分支和重写回环。

## 流程

```
S0 预处理/脱敏 → S1 视觉理解 → S2 输入安全 ─(越界)→ END
                                    │
                                    ▼
                              S3 选风格 → S4 文案生成 → S5 输出安全
                                              ▲              │
                                              └──(重写)──────┤(通过)
                                                             ▼
                                                        S6 合成 → END
```

| 阶段 | 职责 | 打磨时替换为 |
|---|---|---|
| S0 | 隐私脱敏 + 缩放 + base64 | 客户端处理 |
| S1 | 看懂截图 → Context JSON | **Claude Opus 4.8** vision + structured output |
| S2 | 越界拦截 | 规则 / 可与 S1 合并 |
| S3 | pua_type → 风格(纯规则) | 扩展映射表 |
| S4 | 回怼文案 + 模板 + 贴字 → Generation JSON | **Claude** structured output |
| S5 | 输出审核 → 通过/重写/放弃 | 规则 + 模型双保险 |
| S6 | 贴字合成出图 | Pillow / Canvas + 素材库 |

## 目录

```
ptop/
├── main.py              # 本地入口:python main.py <截图>
├── requirements.txt
├── src/
│   ├── state.py         # MemeState(全局状态)+ 两个 JSON 契约
│   ├── graph.py         # LangGraph 编排:节点、条件边、回环、interrupt
│   └── nodes/           # 7 个节点桩,逐个打磨
│       ├── s0_preprocess.py
│       ├── s1_understand.py    # 含 CONTEXT_SCHEMA
│       ├── s2_input_safety.py
│       ├── s3_pick_style.py
│       ├── s4_generate.py      # 含 GENERATION_SCHEMA
│       ├── s5_output_safety.py
│       └── s6_compose.py
```

## 运行

```bash
pip install -r requirements.txt
python main.py path/to/screenshot.png   # 不传图也能跑通(桩数据)
```

## 关键设计

- **单一 State 贯穿**:`Context JSON`(S1)与 `Generation JSON`(S4)是与上下游的接口契约,已在 `state.py` / schema 里定死。
- **S5→S4 重写回环带计数器**:`MAX_REWRITE` 防止 Claude 反复被拒时死循环。
- **人机回环(可选)**:`build_graph(interrupt_for_role_fix=True)` 会在 S1 后中断,用户改完角色再 resume,不重跑视觉调用。
- **checkpointer**:已挂 `MemorySaver`,支持断点续跑与 interrupt 回放。

## TODO(打磨顺序建议)

1. S1:接 Claude Opus 4.8 vision,产出真实 Context JSON(注意处理 `stop_reason == "refusal"`)。
2. S4:接 Claude 生成回怼文案。
3. S6:Pillow 贴字 + 素材库。
4. S2/S5:真实安全审核。
5. S0:客户端脱敏。
