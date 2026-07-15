# YOLOv8 + PINN 草莓温室智能监测系统

## 项目概述

基于 YOLOv8 的草莓病害检测与成熟度评估系统，融合 PINN（物理信息神经网络）进行光照矫正，结合 Qwen 大模型实现多智能体农业决策，通过 Vue.js 仪表盘提供可视化监控界面。

## 快速启动

```bash
# 1. 安装 Python 依赖（推荐清华镜像）
pip3 install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 2. 安装前端依赖并构建
cd smart-greenhouse-dashboard && npm install && npm run build

# 3. 配置 Qwen API
cp qwen_demo.env.example qwen_demo.env
# 编辑 qwen_demo.env，填入 QWEN_API_KEY 等

# 4. 下载预训练模型（或使用自己的训练权重）
python3 -c "from ultralytics import YOLO; YOLO('yolov8s-seg.pt')"
cp yolov8s-seg.pt models/

# 5. 启动服务
cd smart-greenhouse-dashboard && npm start
# 访问 http://localhost:3000
```

## 目录结构

```text
├── strawberry_pipeline/          # 核心管道：多智能体 + Qwen 客户端
│   ├── interfaces.py             # 四类智能体接口定义
│   ├── schemas.py                # 统一数据结构（PerceptionResult 等）
│   ├── orchestrator.py           # 管道编排器
│   ├── examples.py               # 工厂函数（demo / qwen 管道）
│   ├── qwen_client.py            # Qwen OpenAI 兼容客户端
│   ├── perception/
│   │   ├── yolo_adapter.py       # YOLOv8-seg 病害检测适配器
│   │   ├── yolo_dev_adapter.py   # YOLO 开发适配器
│   │   └── mock_perception.py    # Mock 感知（测试用）
│   └── agents/
│       ├── diagnosis_agent.py    # 规则版诊断 Agent
│       ├── decision_agent.py     # 规则版决策 Agent
│       ├── memory_agent.py       # JSONL 记忆 Agent
│       ├── qwen_agents.py        # Qwen 版诊断 + 决策 Agent
│       ├── payload_parsers.py    # Qwen JSON 输出解析
│       └── mock_agents.py        # Mock Agent
├── smart-greenhouse-dashboard/   # Web 仪表盘
│   ├── server.js                 # Express API 服务（端口 3000）
│   ├── src/views/Dashboard.vue   # Vue 仪表盘主组件
│   └── dist/                     # Vite 构建输出
├── models/                       # 模型权重文件
│   └── yolov8s-seg.pt            # YOLOv8-seg 预训练模型
├── strawberry_diseases/          # 草莓病害数据集（7 类，4.6 GB，已 gitignore）
├── yolo_dev/ultralytics-main/    # YOLOv8 框架源码
├── detect_bridge.py              # Express ↔ YOLO 检测桥接
├── detect_chat_bridge.py         # Express ↔ YOLO + Qwen 联合桥接
├── train_yolo.py                 # YOLOv8-seg 训练脚本
├── qwen_web_chat.py              # Web 端 Qwen 对话桥接
├── run_qwen_demo.py              # CLI 单次多智能体测试
├── run_qwen_chat.py              # CLI 交互式对话测试
└── requirements.txt              # Python 依赖
```

## 一、YOLO 融合方案

### 1. YOLOv8 载体
- 以 YOLOv8 为载体，融合 PINN 技术，解决光照不同情况下草莓成熟度校准问题
- 在 YOLO 的检测头做改进，与检测分类头并行一个 PINN 感知头

### 2. PINN
- PINN 网络基于 UNet，对不同光照下草莓成熟度识别做矫正
- 传统 YOLO 基于大数据训练，但早晨、中午、傍晚和夜间光线不同，识别可能产生误差

### 3. 数据集
- 所有数据均为真实田间采集

## 二、多智能体方案

### 1. 四智能体分工

| Agent | 职责 | 输入 | 输出 |
|-------|------|------|------|
| 感知 | 图像输入、目标检测、成熟度识别、病害检测、光照特征提取 | 图像 | PerceptionResult |
| 诊断 | 分析成熟度可信度、光照/阴影影响、风险识别 | PerceptionResult + 历史 | DiagnosisResult |
| 决策 | 生成农业建议（采摘/补光/人工复核） | PerceptionResult + DiagnosisResult + 历史 | DecisionResult |
| 记忆 | 保存历次结果，提供历史上下文 | 本轮所有结果 | JSONL 写入/读取 |

### 2. 数据流

```
图像输入 → 感知 Agent（YOLOv8 + PINN）→ 诊断 Agent → 决策 Agent → 记忆 Agent
                         ↕ Qwen LLM（诊断 + 决策）
```

### 3. 接口设计

```text
PerceptionModule.analyze(image) → PerceptionResult
  → DiagnosisAgent.diagnose(perception, history) → DiagnosisResult
    → DecisionAgent.decide(perception, diagnosis, history) → DecisionResult
      → MemoryAgent.save(record)
```

### 4. LLM 模型
- 选用 Qwen3-max（通过 DashScope API，OpenAI 兼容协议）
- 同一个 Qwen 模型通过不同 system prompt 扮演不同智能体角色

## 三、病害检测

### 支持的病害类别（7 类）

| ID | 病害 | 英文 |
|----|------|------|
| 0 | 角斑病 | Angular Leafspot |
| 1 | 炭疽病（果腐） | Anthracnose Fruit Rot |
| 2 | 花枯病 | Blossom Blight |
| 3 | 灰霉病 | Gray Mold |
| 4 | 叶斑病 | Leaf Spot |
| 5 | 白粉病（果实） | Powdery Mildew Fruit |
| 6 | 白粉病（叶片） | Powdery Mildew Leaf |

### 使用方式
1. 用 `train_yolo.py` 在草莓病害数据集上训练自定义模型
2. 将训练好的权重放入 `models/` 目录
3. 通过 Web 仪表盘上传图片即可进行病害检测 + Qwen 分析

## 四、Web 仪表盘

- **技术栈**：Vue 3 + Element Plus + ECharts 6 + Express 5
- **核心功能**：环境传感器监控、设备控制、Qwen 流式对话（SSE）、图片上传 + YOLO 病害检测

### API 路由

| 路由 | 功能 |
|------|------|
| `/api/health` | 健康检查 |
| `/api/sensors` | 传感器数据（温度/湿度/光照/CO2） |
| `/api/devices` | 设备状态与控制 |
| `/api/alerts` | 告警通知 |
| `/api/qwen/chat` | Qwen 多智能体对话（非流式） |
| `/api/qwen/chat/stream` | Qwen 对话（SSE 流式） |
| `/api/detect` | YOLO 病害检测 |
| `/api/detect/chat/stream` | 上传图片 + YOLO + Qwen 流式分析 |

## 五、脚本说明

| 脚本 | 用途 |
|------|------|
| `run_qwen_demo.py` | CLI 单次多智能体流程测试（输出 JSON） |
| `run_qwen_chat.py` | CLI 交互式 Qwen 草莓咨询对话 |
| `qwen_web_chat.py` | Express 调用的 Qwen 对话桥接（stdin JSON） |
| `detect_bridge.py` | Express 调用的 YOLO 检测桥接 |
| `detect_chat_bridge.py` | Express 调用的 YOLO + Qwen 联合桥接（支持 SSE） |
| `train_yolo.py` | YOLOv8-seg 病害检测训练脚本 |

## 六、已实现功能

- 模块化多智能体架构（4 类 Agent 完整接口+实现）
- 规则版 + Qwen 版诊断/决策 Agent（可通过工厂函数切换）
- JSONL 文件记忆 Agent
- Qwen OpenAI 兼容客户端（支持流式/非流式/JSON 模式）
- YOLOv8-seg 病害检测适配器（7 类草莓病害）
- Web 仪表盘（传感器/设备/告警/Qwen 对话/图片上传）
- SSE 流式输出（检测进度 + 推理过程 + 最终回复）
- Express ↔ Python 桥接协议（stdin/stdout JSON）

## 七、后续待实现

- 将 Mock 感知替换为真实 YOLO + PINN 感知适配器
- 在病害数据集上训练自定义模型（替代 COCO 预训练权重）
- 将 `JsonlMemoryAgent` 升级为 SQLite
- 补充执行 Agent（对接补光、告警、传感器或设备控制）
