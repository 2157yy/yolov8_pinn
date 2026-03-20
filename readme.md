#yolov8魔改——融合pinn

# 一、yolo融合
## 1、yolov8载体
- 以yolov8为载体，融合pinn技术，解决光照不同情况下草莓成熟度校准问题
- 本设计主要在yolo的检测头做改进，与监测分类头并行一个pinn感知头

## 2.pinn
- pinn网络主要基于Unet
- 对不同光照下草莓成熟度识别做矫正，传统yolo基于大数据训练，但是由于早晨、中午、傍晚和夜间的光线不同，yolo对草莓成熟度的识别可能会产生一定的误差，pinn可矫正

## 3.数据集
- 所有数据均为真实田间采集，质量高，可信度强

## 4.保密性
- 此代码所有均处于保密，private

# 二、多智能体方案
## 1.总体思路
- 当前方案先实现四类核心智能体：感知 Agent、诊断 Agent、决策 Agent、记忆 Agent
- 暂不接入执行 Agent，优先把检测、分析、建议、历史记忆四步闭环打通
- 整体目标是让改进后的 YOLOv8 + PINN 不仅完成草莓成熟度检测，还能将光照相关细节传递给大模型，最终输出农业建议
- 系统架构采用模块式设计，YOLO/PINN 与智能体之间通过统一接口和标准数据结构通信，便于独立开发与替换

## 2.LLM模型
- 选用 Qwen2.5-3B-Instruct（int8 或 int4 量化）
- 基于农业场景进行 LoRA 微调，形成农业智能助手
- 同一个 Qwen 模型可通过不同 system prompt 扮演不同智能体角色，降低部署成本

## 3.四智能体分工
### 3.1 感知 Agent
- 负责图像输入、目标检测、成熟度识别、光照特征提取
- 底层由改进后的 YOLOv8 + PINN 完成
- 其中 YOLOv8 负责草莓目标检测与基础成熟度判断，PINN 负责在不同光照条件下对成熟度结果进行矫正
- 该智能体不直接生成自然语言，只输出结构化结果，供后续智能体使用

### 3.2 诊断 Agent
- 负责读取感知 Agent 输出的结构化结果
- 分析草莓成熟度是否受到光照、阴影、时间段等因素影响
- 给出诊断结论，例如：当前结果是否可信、是否存在逆光误差、是否建议重新拍摄或人工复核
- 该智能体本质上是农业视觉诊断专家，重点输出“原因”和“证据”

### 3.3 决策 Agent
- 负责根据诊断 Agent 的结论生成最终建议
- 输出内容包括：是否建议采摘、是否建议补光、是否建议调整观测时间、是否建议人工复核
- 该智能体面向用户，输出更加容易理解的农业咨询结果

### 3.4 记忆 Agent
- 负责保存历次检测、诊断和决策结果，形成草莓生长过程的历史档案
- 记录内容可包括：图像编号、时间戳、成熟度原始值、成熟度矫正值、光照特征、诊断结论、最终建议
- 该智能体为后续多轮分析提供上下文，例如比较同一批草莓在早晨、中午、傍晚的成熟度变化
- 记忆 Agent 不直接参与检测，但可为诊断 Agent 和决策 Agent 提供历史参考，提高建议稳定性

## 4.智能体之间的数据流
- 图像首先输入感知 Agent
- 感知 Agent 输出草莓检测框、成熟度原始结果、PINN 矫正结果、光照特征
- 诊断 Agent 接收上述结构化结果，判断误差来源和结果可信度
- 决策 Agent 根据诊断结果给出面向农户或管理者的建议
- 记忆 Agent 负责保存本轮感知、诊断、决策结果，并在下一轮分析时提供历史上下文

流程如下：

```text
图像输入
  -> 感知 Agent（YOLOv8 + PINN）
  -> 结构化检测结果
  -> 诊断 Agent（原因分析）
  -> 决策 Agent（农业建议输出）
  -> 记忆 Agent（历史记录与上下文）
```

## 5.YOLO、PINN 与 Qwen 的融合方式
- 改进后的 YOLOv8 负责目标检测与基础成熟度识别
- PINN 感知头与检测分类头并行，用于建模光照对成熟度识别的影响，并对结果进行矫正
- 感知 Agent 将识别结果整理为结构化信息后传给 Qwen
- Qwen 不只知道“草莓是否成熟”，还需要知道“当前光照条件下该判断是否可靠”
- 因此传给 Qwen 的信息至少包括：检测目标、成熟度原始值、成熟度矫正值、亮度特征、时间段或环境光照描述

## 6.模块式接口设计
- YOLO/PINN 作为独立感知模块开发，只负责输入图像并输出结构化检测结果
- 诊断、决策、记忆分别作为独立智能体模块开发，不直接依赖 YOLO 内部实现
- orchestrator 只依赖接口，不依赖具体模型实现，从而实现松耦合
- 当 YOLO 检测模块升级、Qwen 模型切换、记忆存储方式变化时，只要接口不变，其它模块无需修改

推荐接口关系如下：

```text
image
  -> PerceptionModule.analyze(...)
  -> PerceptionResult
  -> DiagnosisAgent.diagnose(...)
  -> DiagnosisResult
  -> DecisionAgent.decide(...)
  -> DecisionResult
  -> MemoryAgent.save(...)
```

推荐的接口职责如下：
- `PerceptionModule`
  - 输入图像与元数据
  - 输出 `PerceptionResult`
- `DiagnosisAgent`
  - 输入 `PerceptionResult` 与历史记录
  - 输出 `DiagnosisResult`
- `DecisionAgent`
  - 输入 `PerceptionResult`、`DiagnosisResult` 与历史记录
  - 输出 `DecisionResult`
- `MemoryAgent`
  - 提供 `recall(...)` 和 `save(...)` 两类能力

这样设计后，可以实现以下开发方式：
- YOLO/PINN 团队只关注感知模块，独立调试检测头、PINN 感知头和结果输出格式
- 智能体团队只关注诊断、决策、记忆逻辑，独立调试 prompt、LoRA 和规则策略
- 双方只需约定统一 schema，即可并行开发

## 7.建议的数据格式
- 为保证多智能体协作稳定，智能体之间不直接传自然语言，统一传 JSON 结构
- 推荐字段包括：
  - 图像编号
  - 时间戳
  - 草莓目标框坐标
  - maturity_raw
  - maturity_corrected
  - light_features
  - confidence
  - scene_summary
  - diagnosis
  - recommendation
- 其中建议将诊断结果进一步结构化为：
  - reliability
  - confidence_score
  - reason
  - evidence_points
  - risks
  - recommendations
- 建议将决策结果进一步结构化为：
  - harvest
  - fill_light
  - manual_review
  - message
  - rationale
  - actions

示例：

```json
{
  "image_id": "20260321_101500_01",
  "timestamp": "2026-03-21T10:15:00+08:00",
  "strawberries": [
    {
      "bbox": [120, 86, 214, 201],
      "maturity_raw": 0.68,
      "maturity_corrected": 0.81,
      "light_features": {
        "brightness": 0.42,
        "shadow_ratio": 0.31
      },
      "confidence": 0.93
    }
  ],
  "scene_summary": {
    "avg_light": 0.45,
    "time_period": "morning"
  },
  "diagnosis": {
    "reliability": "high",
    "confidence_score": 0.92,
    "reason": "light is stable and correction is consistent",
    "evidence_points": [
      "average confidence=0.93",
      "average correction gap=0.13",
      "scene light=0.42"
    ],
    "risks": [],
    "recommendations": [
      "current observation can be used for harvest judgement"
    ]
  },
  "recommendation": {
    "harvest": true,
    "fill_light": false,
    "manual_review": false,
    "message": "recommended for harvest; corrected maturity=0.81",
    "rationale": "corrected maturity is above the harvest threshold and diagnosis is acceptable",
    "actions": [
      "harvest"
    ]
  }
}
```

## 8.推荐目录结构
- 当前仓库采用外层智能体、内层感知开发的分层结构
- 推荐结构如下：

```text
yolo_dev/
  ultralytics-main/

strawberry_pipeline/
  interfaces.py
  schemas.py
  orchestrator.py
  examples.py
  qwen_client.py
  perception/
    mock_perception.py
    yolo_dev_adapter.py
  agents/
    diagnosis_agent.py
    decision_agent.py
    memory_agent.py
    payload_parsers.py
    qwen_agents.py
    mock_agents.py
```

- `yolo_dev/ultralytics-main/` 作为 YOLO/PINN 独立开发区
- `interfaces.py` 用于定义感知模块和智能体模块的统一接口
- `schemas.py` 用于定义各模块之间共享的数据结构
- `orchestrator.py` 负责串联各模块，但不绑定具体实现
- `examples.py` 提供外层智能体开发阶段的最小运行示例
- `qwen_client.py` 提供 Qwen 的 OpenAI 兼容接口客户端
- `yolo_dev_adapter.py` 负责把 `yolo_dev` 中的真实 YOLO/PINN 能力包装成统一接口
- `mock_perception.py` 用于在 YOLO 尚未联通前模拟感知结果
- `diagnosis_agent.py` 负责诊断 Agent 的外层实现
- `decision_agent.py` 负责决策 Agent 的外层实现
- `memory_agent.py` 负责记忆 Agent 的外层实现
- `payload_parsers.py` 负责未来 Qwen 输出 JSON 的解析与校验
- `qwen_agents.py` 负责 `QwenDiagnosisAgent` 与 `QwenDecisionAgent`
- `mock_agents.py` 保留为简单调试示例

## 9.工程实现建议
- 第一阶段先做串行调用，不做复杂调度系统
- 使用 Python 编写一个 orchestrator，按顺序调用感知 Agent、诊断 Agent、决策 Agent、记忆 Agent
- 感知 Agent 输出标准化 JSON，诊断 Agent 和决策 Agent 可先使用规则引擎实现，后续再切换为 Qwen
- 当前记忆 Agent 已可先采用 JSONL 文件方式实现，后续可升级为本地数据库或 SQLite
- 为接入 Qwen，建议采用统一流程：模型输出 JSON -> `payload_parsers.py` 校验解析 -> 转换为 schema 对象
- Qwen 侧最基本配置包括：
  - `QWEN_BASE_URL`
  - `QWEN_API_KEY`
  - `QWEN_MODEL`
- 推荐协作方式是：
  - `yolo_dev` 负责模型结构、训练、推理和感知结果生成
  - `strawberry_pipeline` 负责接口定义、智能体编排、Prompt 设计和记忆管理
  - 双方通过 `PerceptionResult` 这一统一数据结构对接

## 10.当前已实现功能
- 已完成外层 `strawberry_pipeline` 模块化架构，YOLO/PINN 与智能体通过统一接口解耦
- 已完成 `PerceptionModule`、`DiagnosisAgent`、`DecisionAgent`、`MemoryAgent` 四类接口定义
- 已完成统一 schema 定义，包括 `PerceptionResult`、`DiagnosisResult`、`DecisionResult`、`MemoryRecord`
- 已完成规则版 `DiagnosisAgent` 与 `DecisionAgent`，可在不依赖大模型的情况下跑通流程
- 已完成 `JsonlMemoryAgent`，支持历史结果写入与读取
- 已完成 `QwenChatClient`，支持通过 OpenAI 兼容接口调用 Qwen
- 已完成 `QwenDiagnosisAgent`，可基于感知结果与历史记录生成结构化诊断结论
- 已完成 `QwenDecisionAgent`，可基于感知结果、诊断结果与历史记录生成结构化决策建议
- 已完成 `payload_parsers.py`，可对 Qwen 输出的 JSON 进行解析、校验和标准化
- 已完成 `run_qwen_demo.py`，用于单次结构化联调测试
- 已完成 `run_qwen_chat.py`，用于连续对话式草莓咨询测试
- 当前外层联调阶段仍使用 `MockPerceptionModule` 生成模拟感知结果，后续可替换为真实 YOLO/PINN 适配器

## 11.脚本说明
### 11.1 `run_qwen_demo.py`
- 用于单次调用测试
- 启动后只执行一次完整流程：感知 -> 诊断 -> 决策 -> 记忆
- 输出结果为结构化 JSON
- 适合验证以下内容：
  - Qwen 接口是否连通
  - `QwenDiagnosisAgent` 输出是否合法
  - `QwenDecisionAgent` 输出是否合法
  - 记忆写入是否正常
  - schema 与解析逻辑是否正常

### 11.2 `run_qwen_chat.py`
- 用于连续对话测试
- 启动后会先生成当前草莓状态快照，再进入交互式聊天
- 用户可以围绕当前草莓情况连续追问，例如成熟度、采摘建议、光照影响、后续操作等
- 适合验证以下内容：
  - 草莓咨询助手的连续对话体验
  - Qwen 是否能基于当前上下文持续回答
  - 历史记忆是否会影响后续咨询内容

### 11.3 两个脚本的区别
- `run_qwen_demo.py` 更偏向“结构化联调工具”
- `run_qwen_chat.py` 更偏向“用户咨询体验入口”
- 前者重点验证 agent 输出和接口链路
- 后者重点验证连续对话和农业咨询效果

## 12.后续待实现
- 将 `MockPerceptionModule` 替换为真实 YOLO/PINN 感知适配器，使外层智能体读取真实检测结果
- 将 `yolo_dev/ultralytics-main/` 中的实际推理输出映射到统一 `PerceptionResult`
- 进一步收紧 Qwen 对话 prompt，减少模型自行补充农业阈值或场景设定
- 为 `QwenDiagnosisAgent` 和 `QwenDecisionAgent` 增加更明确的领域规则约束
- 将 `JsonlMemoryAgent` 升级为 SQLite 或正式数据库存储
- 在连续对话模式中支持用户上传真实图片或选择真实样本
- 后续补充执行 Agent，用于对接补光、告警、传感器或设备控制
