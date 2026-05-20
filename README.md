# 🎨 智能图像修复与校正工作台 (Sustech-Digital-Image-Processing-Project)

一个基于前后端分离架构的数字图像处理与智能修复系统。前端提供直观的串行流水线交互，后端基于 FastAPI 驱动多模块核心图像处理算法，支持多步骤的可选智能协同修复。

---

## 🛠️ 项目目录结构

```text
Sustech-Digital-Image-Processing-Project/
│
├── image-corrector-ui/            # 💻 前端生产力工作台 (Vue 3 + Tailwind CSS + Axios)
│   ├── src/
│   │   ├── App.vue                # 核心页面与流水线调度逻辑
│   │   ├── main.js                # 前端主入口
│   │   └── style.css              # Tailwind CSS 样式配置
│   ├── index.html
│   └── package.json
│
├── image-processing-backend/      # 🐍 核心算法服务端 (Python 3 + FastAPI + OpenCV)
│   ├── main.py                    # 后端服务启动总开关
│   ├── requirements.txt           # 📦 基础依赖清单（OpenCV 滤镜可用）
│   ├── requirements-ai.txt        # 📦 AI 风格化的额外依赖（torch/diffusers，可选）
│   ├── api/
│   │   └── image_routes.py        # 业务路由层：负责接收请求、Base64/OpenCV矩阵互转
│   └── algorithms/                # 核心算法层：独立的图像处理功能模块
│       ├── __init__.py
│       ├── deskew.py              # 1. 歪斜校正模块（输入输出均为 numpy.ndarray）
│       ├── exposure.py            # 2. 曝光校正模块
│       ├── enhance_sharpen.py     # 3. 图像增强与锐化模块
│       ├── filters.py             # 4. 滤镜应用模块
│       └── ai_style.py            # 5. AI 风格化模块（SDXL-Turbo image2image，需 GPU）
│
└── .gitignore                     # Git 忽略规则文件（已自动忽略 node_modules、__pycache__ 等）
```

---

# 🚀 后端与算法环境配置 (Python)

> 💡 **说明**：请确保已安装 Anaconda 或 Miniconda。

## 1. 创建并激活虚拟环境

在终端执行以下命令：

```bash
# 创建 Python 3.9 隔离环境
conda create -n sustech-dip python=3.9 -y

# 激活环境
conda activate sustech-dip
```

---

## 2. 安装核心算法依赖

在激活了 `(sustech-dip)` 环境的终端中执行：

```bash
# 进入后端目录
cd image-processing-backend

# 批量安装依赖
pip install -r requirements.txt
```

---

## 3. 启动后端算法服务器

确保终端路径处于 `image-processing-backend/` 目录下：

```bash
# 启动后端服务
python main.py
```

---

# 💻 启动前端界面

> 💡 **说明**：请确保已安装 Node.js。前端需在新终端窗口中操作，无需与 Conda 环境关联。

```bash
# 1. 进入前端目录
cd image-corrector-ui

# 2. 安装所有依赖包
npm install

# 3. 启动本地开发服务器
npm run dev
```

启动成功后，在浏览器中打开终端输出的地址（通常为 `http://localhost:5173/` 或 `http://localhost:5174/`）即可进入工作台。

---

# 🤖 可选：启用 AI 风格化滤镜（步骤 5）

> 💡 **说明**：AI 滤镜（webtoon / 动漫 / 油画 / 赛博朋克 等 13 种风格）基于 `stabilityai/sdxl-turbo` image-to-image 模型。**强烈建议在装有 NVIDIA GPU（≥8GB VRAM）的机器上运行**；CPU 也能跑但单张 1-3 分钟。前 4 步无需此功能即可正常使用，可跳过本节。

## 1. 安装匹配 CUDA 的 PyTorch

请按 PyTorch 官网（https://pytorch.org/get-started/locally/）选择对应 CUDA 版本的安装命令。例如 CUDA 12.1：

```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
```

## 2. 安装其余 AI 依赖

```bash
pip install -r requirements-ai.txt
```

## 3. 使用

在前端界面"5. AI 滤镜"区域勾选启用，选择风格 → 调强度（0.30-0.90，越高越偏离原图）→ 点击"应用 AI 风格化"。

**首次调用** `/api/ai-style` 时会从 HuggingFace 下载约 7GB 的 SDXL-Turbo 权重到本地缓存（`~/.cache/huggingface/`），后续启动复用缓存无需重复下载。

---

# ☁️ 没有本地 GPU？把后端跑在 Colab 上

如果本机没 NVIDIA GPU，但你想体验"AI 滤镜"，可以**只把后端跑在 Colab 的免费 T4 上**，前端继续本地跑。

## 步骤

1. 在 Colab (https://colab.research.google.com) 上传仓库根目录的 [`colab_run_backend.ipynb`](colab_run_backend.ipynb)
2. `代码执行程序 → 更改运行时类型 → T4 GPU`
3. 第 1 格把 `REPO_URL` 改成你的 GitHub 仓库地址，然后**全部运行**
4. 第 3 格会打印一个 `https://xxx.trycloudflare.com` 公网地址
5. 本地把这个地址写进 `image-corrector-ui/.env.local`（可参考 `.env.local.example`）：

   ```
   VITE_API_BASE_URL=https://xxx.trycloudflare.com/api
   ```

6. 本地重启 `npm run dev`，刷新浏览器，所有处理请求就走 Colab GPU 了

> ⚠️ Colab 公网 URL 每次重启都会变，需重新更新 `.env.local`。Colab 免费版连续运行约 12 小时会自动断。