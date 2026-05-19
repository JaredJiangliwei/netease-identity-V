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
│   ├── requirements.txt           # 📦 环境依赖清单
│   ├── api/
│   │   └── image_routes.py        # 业务路由层：负责接收请求、Base64/OpenCV矩阵互转
│   └── algorithms/                # 核心算法层：独立的图像处理功能模块
│       ├── __init__.py
│       ├── deskew.py              # 1. 歪斜校正模块（输入输出均为 numpy.ndarray）
│       ├── exposure.py            # 2. 曝光校正模块
│       ├── sharpen.py             # 3. 图像增强与锐化模块
│       └── filters.py             # 4. 滤镜应用模块
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