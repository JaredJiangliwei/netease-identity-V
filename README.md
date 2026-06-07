# 智能图像修复与校正工作台

> 数字图像处理课程项目 — 基于前后端分离架构的交互式图像处理与智能修复系统

本系统采用前后端分离设计：前端提供可视化的串行处理流水线，用户可逐步对图像应用多种处理；后端基于 FastAPI 封装一系列图像处理算法，既包含基于 OpenCV 的经典数字图像处理方法（几何校正、曝光校正、锐化增强、维纳反卷积、空间域滤镜、图像修复等），也集成了若干可选的深度学习模型（人脸修复、人像抠图、AI 风格化）。各处理模块相互独立、可按需启用，处理结果可在前端即时预览并作为下一步处理的输入。

---

## 目录

- [功能概览](#功能概览)
- [技术栈](#技术栈)
- [目录结构](#目录结构)
- [环境要求](#环境要求)
- [快速开始](#快速开始)
  - [一、启动后端服务](#一启动后端服务)
  - [二、启动前端界面](#二启动前端界面)
- [可选功能](#可选功能)
  - [AI 风格化滤镜](#ai-风格化滤镜sdxl-turbo)
  - [失焦人脸恢复](#失焦人脸恢复codeformer)
  - [将后端部署到 Colab](#将后端部署到-colab无本地-gpu-时)
- [REST API 接口](#rest-api-接口)
- [配置说明](#配置说明)
- [常见问题](#常见问题)
- [开源致谢](#开源致谢)

---

## 功能概览

前端工作台将处理流程组织为一条串行流水线，按以下模块顺序排列。每个模块均可单独启用或跳过，处理结果会作为后续模块的输入图像。

| 序号 | 模块 | 核心方法 | 说明 | 额外依赖 |
| :--: | :--- | :--- | :--- | :--: |
| 1 | 歪斜校正 | 透视变换、Canny 边缘检测、霍夫变换 | 自动检测最大四边形轮廓并透视展平；支持自动倾斜检测、任意角度无黑边旋转、镜像与裁剪 | 无 |
| 2 | 曝光校正 | Gamma 校正、线性亮度/对比度调整 | 调整图像整体明暗与对比度 | 无 |
| 3 | 图像增强与锐化 | 非锐化掩蔽、Laplacian、Sobel | 仅在亮度通道上处理以避免色彩失真 | 无 |
| 4 | 运动模糊修复 | 维纳反卷积（Wiener Deconvolution） | 支持自动估计点扩散函数，或手动指定模糊长度、角度与噪声功率 | 无 |
| 5 | 滤镜应用 | 空间域滤镜 | 提供灰度、反色、复古、暖色、冷色、素描、高对比、浮雕、马赛克、暗角、运动模糊共 11 种可参数化滤镜 | 无 |
| 6 | AI 滤镜 | SDXL-Turbo 图生图 | 提供 3 种人像风格（webtoon / 3d_cartoon / cyberpunk_anime），自动检测人数与性别呈现以动态构造提示词 | torch 等（可选） |
| 7 | 失焦恢复 | CodeFormer 人脸修复 | 针对模糊、低分辨率人脸做修复，可按不同保真权重生成多张候选供选择 | CodeFormer（可选） |
| 8 | 一键抠图 | U²-Net 人像分割（rembg） | 自动分离人像与背景，输出透明背景图 | 无（已含 rembg） |
| 9 | 去除水印 | 图像修复（Inpainting，Telea / Navier-Stokes） | 框选矩形区域后基于邻域信息修复，支持浅色/深色水印 | 无 |
| 10 | 涂抹打码 | 交互式画笔 | 前端画笔工具，手动涂抹局部马赛克或擦除，可调笔刷半径 | 无 |

> 模块 1–5、8–10 仅依赖基础环境即可运行；模块 6、7 依赖额外的深度学习库与预训练权重，属于可选增强功能，未安装时不影响其余模块的正常使用。

---

## 技术栈

**前端**

- Vue 3（Composition API）
- Vite 构建工具
- Tailwind CSS
- 原生 Fetch API 进行前后端通信

**后端**

- Python 3.9
- FastAPI + Uvicorn（异步 Web 框架与 ASGI 服务器）
- OpenCV、NumPy（核心图像处理）
- rembg + ONNX Runtime（人像分割）
- 可选：PyTorch、diffusers、transformers（AI 风格化）
- 可选：CodeFormer、BasicSR（人脸修复）

前后端通过 RESTful 接口交互，图像以 Base64 编码的 PNG 在 JSON 中传输。

---

## 目录结构

```text
netease-identity-V/
│
├── image-corrector-ui/                 # 前端工作台 (Vue 3 + Vite + Tailwind CSS)
│   ├── src/
│   │   ├── App.vue                     # 主页面与流水线调度逻辑
│   │   ├── main.js                     # 前端入口
│   │   ├── style.css                   # 全局样式
│   │   ├── assets/
│   │   └── components/
│   ├── index.html
│   ├── vite.config.js
│   ├── tailwind.config.js
│   ├── package.json
│   └── .env.local.example              # 后端地址配置示例
│
├── image-processing-backend/           # 后端算法服务 (Python + FastAPI)
│   ├── main.py                         # 服务入口（注册路由、配置跨域）
│   ├── requirements.txt                # 基础依赖
│   ├── requirements-ai.txt             # AI 风格化的额外依赖（可选）
│   ├── api/
│   │   └── image_routes.py             # 路由层：请求解析、Base64 与图像矩阵互转
│   └── algorithms/                     # 算法层：各处理模块相互独立
│       ├── deskew.py                   # 透视纠偏
│       ├── auto_rotate.py              # 倾斜角度检测
│       ├── rotate.py                   # 无黑边任意角度旋转
│       ├── exposure.py                 # 曝光校正
│       ├── enhance_sharpen.py          # 增强与锐化
│       ├── wiener_deblur.py            # 维纳反卷积去运动模糊
│       ├── filters.py                  # 空间域滤镜集合
│       ├── watermark_remove.py         # 水印区域修复
│       ├── background_remove.py        # 人像抠图
│       ├── defocus_restore.py          # 失焦人脸修复（CodeFormer 封装，可选）
│       └── ai_style.py                 # AI 风格化（SDXL-Turbo，可选）
│
├── colab_run_backend.ipynb             # 在 Colab GPU 上运行后端的辅助脚本
├── test_img/                           # 测试图片
└── .gitignore
```

---

## 环境要求

- **Python** ≥ 3.9（建议使用 Conda 或 venv 创建隔离环境）
- **Node.js** ≥ 18（建议搭配 npm）
- 基础功能无需 GPU；AI 风格化与失焦恢复模块建议使用具备 ≥ 8 GB 显存的 NVIDIA GPU

---

## 快速开始

前端与后端需分别启动，建议使用两个终端窗口。以下命令以项目根目录为起点。

### 一、启动后端服务

1. 创建并激活虚拟环境：

   ```bash
   conda create -n dip-project python=3.9 -y
   conda activate dip-project
   ```

2. 安装基础依赖：

   ```bash
   cd image-processing-backend
   pip install -r requirements.txt
   ```

3. 启动服务（监听 8766 端口，与前端默认地址一致）：

   ```bash
   python -m uvicorn main:app --host 127.0.0.1 --port 8766
   ```

   出现如下输出表示启动成功：

   ```text
   Uvicorn running on http://127.0.0.1:8766
   ```

> 注：`main.py` 直接运行（`python main.py`）时默认监听 8000 端口，与前端默认地址不一致。建议使用上述 `uvicorn ... --port 8766` 命令，或相应修改前端配置（见[配置说明](#配置说明)）。

### 二、启动前端界面

在另一个终端窗口中：

```bash
cd image-corrector-ui
npm install
npm run dev
```

启动后在浏览器打开终端输出的地址（默认 `http://localhost:5173`）即可进入工作台。前端默认请求后端地址为 `http://127.0.0.1:8766/api`。

---

## 可选功能

以下两个模块依赖额外的深度学习库与较大的预训练权重，按需安装即可，不影响其余功能。

### AI 风格化滤镜（SDXL-Turbo）

基于 `stabilityai/sdxl-turbo` 图生图模型，提供 3 种针对人像精调的风格，并通过 OpenCV 人脸检测与 CLIP 零样本分类自动估计人数与性别呈现，据此动态构造提示词。

1. 按 [PyTorch 官网](https://pytorch.org/get-started/locally/) 安装与本机 CUDA 匹配的 PyTorch。以 CUDA 12.1 为例：

   ```bash
   pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
   ```

2. 安装其余依赖：

   ```bash
   pip install -r requirements-ai.txt
   ```

3. 在前端「6. AI 滤镜」面板勾选启用，选择风格并调节强度（0.30–0.90，数值越大越偏离原图）后应用。

> 首次调用 `/api/ai-style` 会从 HuggingFace 下载约 7 GB 的模型权重至本地缓存（`~/.cache/huggingface/`），之后复用缓存。CPU 亦可运行，但单张图通常需要 1–3 分钟。

### 失焦人脸恢复（CodeFormer）

基于腾讯 ARC 开源的 [CodeFormer](https://github.com/sczhou/CodeFormer)，对模糊或低分辨率人脸进行修复。保真权重 `w` 控制画质与保真之间的权衡：`w` 越小重建越激进、越清晰，`w` 越大越接近原貌。前端会对每个 `w` 各生成一张候选供选择。

1. 将 CodeFormer 仓库克隆到指定路径（后端通过子进程调用其推理脚本）：

   ```bash
   cd image-processing-backend
   mkdir -p external && cd external
   git clone https://github.com/sczhou/CodeFormer.git
   cd CodeFormer
   ```

2. 安装依赖并下载预训练权重：

   ```bash
   pip install -r requirements.txt
   python basicsr/setup.py develop
   python scripts/download_pretrained_models.py facelib
   python scripts/download_pretrained_models.py CodeFormer
   ```

3. 启动后端后，前端「7. 失焦恢复」面板可用。默认候选权重为 `0.3, 0.4, 0.5, 0.6`，可自行修改为逗号分隔的若干 0–1 数值，生成候选后点击任意结果即应用为当前图像。

> 若遇到 `from torchvision.transforms.functional_tensor import rgb_to_grayscale` 报错，是因为较新版本的 torchvision 已迁移该函数。将 `basicsr/data/degradations.py` 中对应导入改为 `from torchvision.transforms.functional import rgb_to_grayscale` 即可。
>
> 未安装 CodeFormer 时调用 `/api/defocus-restore` 会返回 503 与安装指引，前端会将该提示展示在面板中。

### 将后端部署到 Colab（无本地 GPU 时）

若本机没有 NVIDIA GPU，可仅将后端运行在 Colab 的免费 GPU 上，前端仍在本地运行：

1. 将根目录的 `colab_run_backend.ipynb` 上传至 [Colab](https://colab.research.google.com)；
2. 在「修改运行时类型」中选择 GPU；
3. 将首个单元格中的 `REPO_URL` 改为本仓库地址后全部运行；
4. 运行后会输出一个形如 `https://xxx.trycloudflare.com` 的公网地址；
5. 将该地址写入 `image-corrector-ui/.env.local`：

   ```text
   VITE_API_BASE_URL=https://xxx.trycloudflare.com/api
   ```

6. 重启前端 `npm run dev` 并刷新浏览器，处理请求即转由 Colab GPU 完成。

> Colab 公网地址在每次重启后都会变化，需同步更新 `.env.local`；免费额度连续运行约 12 小时后会自动断开。

---

## REST API 接口

所有接口均以 `/api` 为前缀，请求与响应主体为 JSON，图像字段为 Base64 编码的 PNG（带 `data:image/png;base64,` 前缀）。

| 方法 | 路径 | 功能 | 主要参数 |
| :--- | :--- | :--- | :--- |
| POST | `/api/deskew` | 透视纠偏 | `image` |
| POST | `/api/rotate` | 无黑边任意角度旋转 | `image`, `angle` |
| POST | `/api/auto-rotate` | 自动检测倾斜角并旋转 | `image` |
| POST | `/api/mirror` | 镜像翻转 | `image`, `mirrorMode`（`horizontal`/`vertical`/`both`） |
| POST | `/api/exposure` | 曝光校正 | `image`, `gamma`, `alpha`, `beta` |
| POST | `/api/sharpen` | 增强与锐化 | `image`, `intensity`, `sharpenMode` |
| POST | `/api/wiener-deblur` | 运动模糊维纳复原 | `image`, `wienerAuto`, `motionLength`, `motionAngle`, `noisePower` |
| POST | `/api/filter` | 应用空间域滤镜 | `image`, `filterType`, `filterParams` |
| POST | `/api/watermark-remove` | 水印区域修复 | `image`, `x`, `y`, `w`, `h`, `watermarkType`, `radius` |
| POST | `/api/background-remove` | 人像抠图 | `image` |
| GET  | `/api/defocus-restore/status` | 查询 CodeFormer 是否可用 | — |
| POST | `/api/defocus-restore` | 失焦人脸恢复 | `image`, `defocusWeights`, `defocusUpscale` |
| GET  | `/api/ai-style/list` | 获取可用风格列表 | — |
| POST | `/api/ai-style` | AI 风格化 | `image`, `aiStyle`, `aiStrength`, `aiSeed` |

服务启动后可访问 `http://127.0.0.1:8766/docs` 查看 FastAPI 自动生成的交互式接口文档。

---

## 配置说明

**后端端口**

后端默认建议监听 `8766` 端口。如需更改，启动时调整 `--port` 参数，并同步更新前端的后端地址。

**前端后端地址**

前端在 `image-corrector-ui/src/App.vue` 中读取后端地址，优先使用环境变量 `VITE_API_BASE_URL`，默认值为 `http://127.0.0.1:8766/api`。可复制 `.env.local.example` 为 `.env.local` 并填写：

```text
VITE_API_BASE_URL=http://127.0.0.1:8766/api
```

修改 `.env.local` 后需重启前端开发服务器使其生效。

---

## 常见问题

**端口被占用（`address already in use` / `WinError 10048`）**

查找占用端口的进程并结束（以 Windows 为例）：

```bat
netstat -ano | findstr :8766
taskkill /PID <对应的PID> /F
```

**前端无法连接后端**

确认后端已启动，且前端 `VITE_API_BASE_URL`（或 `App.vue` 中默认值）与后端实际监听的地址、端口一致。

**确认 PyTorch 与 GPU 是否可用**

```bash
python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
```

**AI 模块首次调用较慢**

模型权重需先下载再加载到内存与显存，首次调用耗时较长属正常现象，后续调用会复用已加载的模型。

---

## 开源致谢

本项目在实现过程中使用了以下开源模型与工具：

- [SDXL-Turbo](https://huggingface.co/stabilityai/sdxl-turbo) — 图生图风格化
- [CLIP](https://github.com/openai/CLIP) — 零样本图像分类
- [CodeFormer](https://github.com/sczhou/CodeFormer) — 人脸修复
- [rembg](https://github.com/danielgatis/rembg)（U²-Net） — 人像分割
- [OpenCV](https://opencv.org/)、[FastAPI](https://fastapi.tiangolo.com/)、[Vue](https://vuejs.org/)
