```markdown
# 智能知识库（Knowledge Base）

> 一个基于 **LangGraph** 编排、**Milvus** 向量检索、**BGE-M3** 嵌入与重排、**阿里云 DashScope** 大模型的 RAG（Retrieval-Augmented Generation）智能问答知识库系统。
> 支持 PDF 文档入库、商品名识别、混合检索（向量 + 关键词 + Web 搜索 MCP）、RRF 融合、Rerank 重排与 SSE 实时进度推送。

---

## ✨ 核心特性

- 🧩 **双流水线架构**：导入流水线（Import Pipeline）+ 查询流水线（Query Pipeline），均基于 LangGraph 状态机编排
- 📄 **多格式文档解析**：PDF → Markdown（MinerU），图片自动上传至 MinIO 对象存储
- 🔍 **混合检索**：稠密向量检索（BGE-M3）+ HyDE 假设文档增强 + MCP 联网搜索 + RRF 融合 + Cross-Encoder 重排序
- 🏷️ **商品名识别**：基于 LLM 抽取实体，提升垂直领域问答准确率
- 📡 **SSE 实时进度**：长任务全过程可视化，节点级状态推送到前端
- 🖥️ **开箱即用的 Web UI**：FastAPI 提供接口，内置 `chat.html` / `import.html` 演示页面

---

## 🏗️ 系统架构

### 导入流水线（Import Pipeline）

```
Entry → PDF→MD → 图片处理(MinIO) → 文档切片 → 商品名识别 → BGE Embedding → Milvus 入库
```

### 查询流水线（Query Pipeline）

```
用户提问 → 商品名确认 → 向量检索 / HyDE / MCP 联网搜索 → RRF 融合 → Rerank → LLM 生成答案 → SSE 输出
```

---

## 📁 项目结构

```
knowledge_base/
├── config/                       # 全局配置（LLM / Embedding / Milvus / MinIO / Reranker / MCP）
├── processor/
│   ├── import_processor/         # 导入流水线（LangGraph）
│   │   ├── nodes/                # 各处理节点
│   │   ├── main_graph.py         # 图编排入口
│   │   ├── state.py              # 状态定义
│   │   └── base.py               # 节点基类
│   └── query_processor/          # 查询流水线（LangGraph）
│       ├── nodes/                # 检索、重排、答案生成等节点
│       ├── prompt/               # Prompt 模板
│       └── main_graph.py
├── tool/                         # 模型下载、日志等工具
├── utils/                        # 通用工具（Embedding、Milvus、MinIO、Mongo、SSE、Reranker）
├── web/
│   ├── api/                      # FastAPI 路由（query_service / import_service）
│   └── page/                     # 前端页面（chat.html / import.html）
├── test/                         # 单元/集成测试与脚本
├── .env.example                  # 环境变量模板
├── pyproject.toml                # 项目元数据与依赖（uv 管理）
└── README.md
```

---

## 🛠️ 技术栈

| 类别 | 选型 |
|------|------|
| 语言 | Python 3.11+ |
| 包管理 | [uv](https://docs.astral.sh/uv/) |
| Web 框架 | FastAPI |
| 编排框架 | LangGraph / LangChain |
| 大模型 | 阿里云 DashScope（Qwen 系列，OpenAI 兼容协议） |
| 嵌入模型 | BAAI/bge-m3（本地，FlagEmbedding） |
| 重排序 | bge-reranker-large + qwen3-rerank |
| 向量库 | Milvus 2.x |
| 文档库 | MongoDB |
| 对象存储 | MinIO |
| 文档解析 | MinerU（ModelScope 源） |
| 联网搜索 | 阿里云百炼 MCP WebSearch |
| 深度学习 | PyTorch 2.x（CUDA 12.8） |

---

## 🚀 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/Georgejdm/knowledge.git
cd knowledge
```

### 2. 安装依赖（推荐使用 uv）

```bash
# 安装 uv（若未安装）
pip install uv

# 同步依赖（自动按 pyproject.toml + uv.lock 创建 .venv）
uv sync
```

> ⚠️ PyTorch 系列依赖通过 `pytorch-cuda` 索引（CUDA 12.8）安装。如需 CPU 版本，请修改 `pyproject.toml` 中的 `[[tool.uv.index]]`。

### 3. 启动依赖中间件

本项目依赖以下外部服务，请提前部署并启动（推荐 Docker Compose）：

- **Milvus**（向量数据库，默认 `localhost:19530`）
- **MongoDB**（对话历史 / 业务数据，默认 `localhost:27017`）
- **MinIO**（对象存储，默认 `localhost:9000`）

### 4. 下载本地模型

```bash
# BGE-M3 / BGE-Reranker-Large（首次运行会自动从 ModelScope 下载）
python tool/download_bgem3.py
```

下载路径需与 `.env` 中的 `BGE_M3_PATH` 与 `BGE_RERANKER_LARGE` 保持一致。

### 5. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入你自己的 API Key、模型路径、服务地址
```

主要变量说明（完整列表见 `.env.example`）：

| 变量 | 说明 |
|------|------|
| `OPENAI_API_KEY` | DashScope API Key |
| `OPENAI_API_BASE` | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| `LLM_DEFAULT_MODEL` | 默认对话模型，如 `qwen-flash` |
| `MILVUS_URL` / `CHUNKS_COLLECTION` | Milvus 地址与集合名 |
| `MONGO_URL` / `MONGO_DB_NAME` | MongoDB 连接 |
| `MINIO_ENDPOINT` / `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` | MinIO 凭证 |
| `BGE_M3_PATH` / `BGE_DEVICE` / `BGE_FP16` | 本地嵌入模型路径与设备 |
| `MCP_DASHSCOPE_BASE_URL` | 百炼 WebSearch MCP 服务地址 |

### 6. 启动 Web 服务

```bash
uvicorn web.api.query_service:app --reload --host 0.0.0.0 --port 8000
uvicorn web.api.import_service:app --reload --host 0.0.0.0 --port 8001
```

浏览器打开 `web/page/chat.html` 与 `web/page/import.html` 即可体验问答与文档入库。

---

## 🧪 测试

```bash
# 单独运行某个验证脚本
python test/05_bgem3测试向量转换.py
python test/08_MCP测试.py
```

---

## 📌 关键设计说明

- **节点基类 `base.py`**：所有 LangGraph 节点统一继承，内置异常处理与日志埋点，保证节点失败可被全局捕获并通过 SSE 上报。
- **状态机 `state.py`**：导入与查询各自维护 TypedDict 状态，节点之间通过 state 传值，避免隐式全局变量。
- **异常体系 `exceptions.py`**：自定义业务异常（如 `DocumentParseError`、`MilvusInsertError`），上层统一处理。
- **SSE 进度推送**：通过 `utils/sse_utils.py` + `task_utils.py` 将节点状态实时回传前端。
- **MCP 调用容错**：百炼 WebSearch 等外部 MCP 服务调用包含超时与异常降级，避免单点失败导致整图崩溃。

---

## ⚠️ 安全与注意事项

1. **绝对不要提交 `.env` 文件**（仓库已配置 `.gitignore`）。
2. 一旦密钥误泄露，请立刻在 DashScope / 云服务控制台 **吊销并重新生成**。
3. Milvus / MongoDB / MinIO 建议仅在内网开放，公网部署请启用 TLS 与鉴权。
4. CUDA 版本需与本机 NVIDIA 驱动匹配，最低要求支持 cu128。

---

## 📜 License

本项目暂未指定开源协议，二次分发前请先与作者沟通。

---

## 📮 联系方式

- 仓库：<https://github.com/Georgejdm/knowledge>
- Issue / PR 欢迎提交，请注明场景与复现步骤。
```