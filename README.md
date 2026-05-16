# 🎨 智能图像修复与校正工作台 (Sustech-Digital-Image-Processing-Project)

一个基于前后端分离架构的数字图像处理与智能修复系统。前端提供直观的串行流水线交互，后端基于 FastAPI 驱动多模块核心图像处理算法，支持多步骤的可选智能协同修复。

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
├── image-processing-backend/       # 🐍 核心算法服务端 (Python 3 + FastAPI + OpenCV)
│   ├── main.py                    # 后端服务启动总开关
│   ├── api/
│   │   └── image_routes.py        # 业务路由层：负责接收请求、Base64/OpenCV矩阵互转
│   └── algorithms/                # 核心算法层：独立的图像处理功能模块
│       ├── __init__.py
│       ├── deskew.py              # 1. 歪斜校正模块
│       ├── exposure.py            # 2. 曝光校正模块
│       ├── sharpen.py             # 3. 图像增强与锐化模块
│       └── filters.py             # 4. 滤镜应用模块
│
└── .gitignore                     # Git 忽略规则文件（已自动忽略 node_modules、__pycache__ 等）
